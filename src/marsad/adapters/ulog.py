"""PX4 ULog reader: ULog -> NavSample stream (+ inspection metadata).

IMPORTANT -- UNVERIFIED FIELD NAMES. Every PX4 topic/field name below comes from public PX4 documentation
and memory and has NOT been checked against a real flight log. The reader is therefore driven by alias
lists and field presence; what it actually found is reported in UlogInfo.mapping / .warnings. See
docs/ADAPTERS.md ("known unknowns") and run `marsad inspect <log>` on the first real log.

pyulog is imported lazily.
"""
from __future__ import annotations
import math
import warnings
from dataclasses import dataclass, field, asdict
from typing import Iterator, Optional

from ..types import GnssFix, NavSample, RefMotion
from ._common import (CONTAMINATED_WARNING, ContaminatedReferenceWarning, mean_std, normalise_agc)

GPS_TOPICS = ("sensor_gps", "vehicle_gps_position")      # the latter is the pre-v1.13 name
SAT_TOPICS = ("satellite_info",)
# reference candidates, in priority order: (topic, kind, independent?)
REF_CANDIDATES = (
    ("vehicle_visual_odometry", "odom", True),
    ("vehicle_mocap_odometry", "odom", True),
    ("vehicle_optical_flow_vel", "flowvel", True),
    ("vehicle_optical_flow", "flow", True),
    ("vehicle_local_position", "localpos", False),
    ("vehicle_odometry", "odom", False),
)

ALIASES = {
    "timestamp": ("timestamp",),
    "lat": ("lat", "latitude"),
    "lon": ("lon", "longitude"),
    "alt": ("alt", "altitude"),
    "vel_n": ("vel_n_m_s", "vel_n", "vn"),
    "vel_e": ("vel_e_m_s", "vel_e", "ve"),
    "fix_type": ("fix_type",),
    "n_sats": ("satellites_used", "satellites_visible", "n_sats"),
    "hdop": ("hdop",),
    "eph": ("eph",),
    "agc": ("automatic_gain_control", "agc"),
    "jamming_indicator": ("jamming_indicator",),
    "jamming_state": ("jamming_state",),
    "spoofing_state": ("spoofing_state",),
    "noise_per_ms": ("noise_per_ms",),
    "time_utc": ("time_utc_usec", "time_utc"),
}


@dataclass
class Px4Flag:
    """PX4/receiver's own jamming/spoofing indicators at time t (side-series, never fed to the engine)."""
    t: float
    jamming_state: Optional[int] = None
    spoofing_state: Optional[int] = None
    jamming_indicator: Optional[float] = None

    @property
    def jam_flag(self) -> bool:
        return (self.jamming_state or 0) >= 2     # UNVERIFIED enum: 0 unknown, 1 ok, 2 warning, 3 critical

    @property
    def spoof_flag(self) -> bool:
        return (self.spoofing_state or 0) >= 2    # UNVERIFIED enum: 0 unknown, 1 ok, 2 indicated, 3 multiple


@dataclass
class UlogInfo:
    path: str = ""
    duration_s: float = 0.0
    synthetic: bool = False
    synthetic_note: str = ""
    topics: dict = field(default_factory=dict)        # name -> {"n": rows, "multi_ids": [...], "fields": [...]}
    gps_topic: Optional[str] = None
    gps_instance: Optional[int] = None
    mapping: dict = field(default_factory=dict)       # logical field -> how it was obtained
    warnings: list = field(default_factory=list)
    reference_topic: Optional[str] = None
    reference_source: Optional[str] = None
    reference_contaminated: bool = False
    n_gnss: int = 0
    n_ref: int = 0
    gps_rate_hz: Optional[float] = None
    has_cn0: bool = False
    has_agc: bool = False
    has_px4_flags: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UlogData:
    samples: list
    info: UlogInfo
    px4_flags: list = field(default_factory=list)


# ------------------------------------------------------------------------------------------ helpers
def _import_pyulog():
    try:
        from pyulog import ULog
    except ImportError as e:        # pragma: no cover
        raise ImportError("ULog support needs pyulog: pip install pyulog  (or marsad[adapters])") from e
    return ULog


def _first(fields: dict, names):
    for n in names:
        if n in fields:
            return n, fields[n]
    return None, None


def _is_int(arr) -> bool:
    return arr.dtype.kind in "iu"


def _yaw_from_q(w, x, y, z):
    import numpy as np
    return np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _datasets(ulog, names):
    return [d for d in ulog.data_list if d.name in names]


def _pick_dataset(ulog, names, info: UlogInfo, what: str):
    """Pick the instance with the most rows among topics in `names` (earlier name wins ties)."""
    best = None
    for nm in names:
        for d in _datasets(ulog, (nm,)):
            n = len(d.data["timestamp"])
            if best is None or n > len(best.data["timestamp"]):
                best = d
        if best is not None and best.name == nm:
            break
    if best is None:
        return None
    n_inst = len(_datasets(ulog, (best.name,)))
    if n_inst > 1:
        info.warnings.append(f"{what}: {n_inst} instances of {best.name}; using multi_id={best.multi_id} "
                             f"(most rows)")
    return best


# ------------------------------------------------------------------------------------- reference
def _odom_velocity(d, info: UlogInfo, topic: str):
    """vehicle_(visual|mocap_)odometry-style dataset -> (t, ve, vn, sigma) numpy arrays or None."""
    import numpy as np
    f = d.data
    t = f["timestamp"] / 1e6
    _, vx = _first(f, ("velocity[0]", "vx"))
    _, vy = _first(f, ("velocity[1]", "vy"))
    qn = [f.get(f"q[{i}]") for i in range(4)]
    have_q = all(q is not None for q in qn)
    sig = None
    _, vv = _first(f, ("velocity_variance[0]",))
    if vv is not None:
        with np.errstate(invalid="ignore"):
            s = np.sqrt(np.where(vv > 0, vv, np.nan))
        sig = s
    ve = vn = None
    how = ""
    if vx is not None and vy is not None:
        ok = np.isfinite(vx) & np.isfinite(vy)
        if ok.mean() >= 0.5:
            fr = f.get("velocity_frame")
            frame = int(np.bincount(fr.astype(int)).argmax()) if fr is not None and len(fr) else None
            if frame in (None, 0, 1):
                if frame in (None, 0):
                    info.warnings.append(f"{topic}: velocity_frame {'missing' if frame is None else 'UNKNOWN(0)'};"
                                         f" assuming NED (x=north, y=east)")
                vn, ve, how = vx, vy, "velocity[0..1] as NED (N,E)"
            elif frame in (2, 3) and have_q:
                yaw = _yaw_from_q(*qn)
                vn = vx * np.cos(yaw) - vy * np.sin(yaw)
                ve = vx * np.sin(yaw) + vy * np.cos(yaw)
                how = f"velocity[0..1] in frame {frame} (FRD) rotated to NED by yaw from q (ignores roll/pitch)"
            else:
                info.warnings.append(f"{topic}: velocity_frame={frame} needs attitude q which is missing; "
                                     f"velocity unusable, trying position differencing")
    if ve is None:
        _, px = _first(f, ("position[0]", "x"))
        _, py = _first(f, ("position[1]", "y"))
        if px is not None and py is not None:
            pf = f.get("pose_frame")
            pframe = int(np.bincount(pf.astype(int)).argmax()) if pf is not None and len(pf) else None
            if pframe not in (None, 0, 1):
                info.warnings.append(f"{topic}: pose_frame={pframe} is not NED; position differencing unusable")
                return None
            if pframe in (None, 0):
                info.warnings.append(f"{topic}: pose_frame unknown; assuming NED for position differencing")
            ok = np.isfinite(px) & np.isfinite(py)
            idx = np.nonzero(ok)[0]
            if len(idx) < 3:
                return None
            tt, xx, yy = t[idx], px[idx], py[idx]
            dt = np.diff(tt)
            good = (dt > 0.005) & (dt < 1.0)
            vn_ = np.where(good, np.diff(xx) / np.where(good, dt, 1), np.nan)
            ve_ = np.where(good, np.diff(yy) / np.where(good, dt, 1), np.nan)
            t, vn, ve = tt[1:], vn_, ve_
            sig = None
            how = "position[0..1] differenced as NED (noisy)"
            keep = np.isfinite(vn) & np.isfinite(ve)
            t, vn, ve = t[keep], vn[keep], ve[keep]
            info.mapping[f"ref.{topic}"] = how
            return t, ve, vn, sig
    if ve is None:
        return None
    ok = np.isfinite(ve) & np.isfinite(vn)
    info.mapping[f"ref.{topic}"] = how
    return t[ok], ve[ok], vn[ok], (sig[ok] if sig is not None else None)


def _attitude_yaw(ulog):
    import numpy as np
    for d in _datasets(ulog, ("vehicle_attitude",)):
        f = d.data
        if all(f"q[{i}]" in f for i in range(4)):
            return f["timestamp"] / 1e6, _yaw_from_q(*(f[f"q[{i}]"] for i in range(4)))
    return None


def _flowvel(d, info: UlogInfo, topic: str):
    import numpy as np
    f = d.data
    t = f["timestamp"] / 1e6
    if "vel_ne[0]" in f and "vel_ne[1]" in f:
        vn, ve = f["vel_ne[0]"], f["vel_ne[1]"]
        ok = np.isfinite(vn) & np.isfinite(ve)
        info.mapping[f"ref.{topic}"] = "vel_ne[0]=north, vel_ne[1]=east (UNVERIFIED order)"
        return t[ok], ve[ok], vn[ok], None
    info.warnings.append(f"{topic}: no vel_ne[]; body-frame velocity not used")
    return None


def _flow(d, info: UlogInfo, topic: str, ulog):
    """vehicle_optical_flow (integrated flow + range) -> NE velocity using attitude yaw. UNVERIFIED conventions."""
    import numpy as np
    f = d.data
    need = ("pixel_flow[0]", "pixel_flow[1]", "integration_timespan_us", "distance_m")
    if not all(k in f for k in need):
        info.warnings.append(f"{topic}: missing one of {need}; unusable")
        return None
    att = _attitude_yaw(ulog)
    if att is None:
        info.warnings.append(f"{topic}: needs vehicle_attitude q for heading; unusable")
        return None
    t = f["timestamp"] / 1e6
    dt = f["integration_timespan_us"] / 1e6
    dist = f["distance_m"]
    fx = f["pixel_flow[0]"] - (f["delta_angle[0]"] if "delta_angle[0]" in f else 0.0)
    fy = f["pixel_flow[1]"] - (f["delta_angle[1]"] if "delta_angle[1]" in f else 0.0)
    q = f.get("quality")
    with np.errstate(invalid="ignore", divide="ignore"):
        vbx = fy * dist / dt
        vby = -fx * dist / dt
    ok = np.isfinite(vbx) & np.isfinite(vby) & (dt > 0) & (dist > 0)
    if q is not None:
        ok &= q > 0
    yaw = np.interp(t, att[0], att[1])
    vn = vbx * np.cos(yaw) - vby * np.sin(yaw)
    ve = vbx * np.sin(yaw) + vby * np.cos(yaw)
    info.mapping[f"ref.{topic}"] = ("vx_b=pixel_flow[1]*dist/dt, vy_b=-pixel_flow[0]*dist/dt, gyro-compensated by "
                                    "delta_angle if present, rotated by vehicle_attitude yaw (UNVERIFIED axes/signs)")
    return t[ok], ve[ok], vn[ok], None


def _localpos(d, info: UlogInfo, topic: str):
    import numpy as np
    f = d.data
    if "vx" not in f or "vy" not in f:
        return None
    t = f["timestamp"] / 1e6
    ok = np.isfinite(f["vx"]) & np.isfinite(f["vy"])
    if "v_xy_valid" in f:
        ok &= f["v_xy_valid"].astype(bool)
    info.mapping[f"ref.{topic}"] = "vx=north, vy=east (NED) [EKF-fused]"
    return t[ok], f["vy"][ok], f["vx"][ok], None


def _select_reference(ulog, info: UlogInfo, reference: str, allow_contaminated: bool):
    cands = REF_CANDIDATES if reference == "auto" else tuple(c for c in REF_CANDIDATES if c[0] == reference)
    if not cands:
        raise ValueError(f"unknown reference topic {reference!r}; choose 'auto' or one of "
                         f"{[c[0] for c in REF_CANDIDATES]}")
    for topic, kind, independent in cands:
        if not independent and not allow_contaminated:
            continue
        for d in _datasets(ulog, (topic,)):
            if len(d.data["timestamp"]) < 3:
                continue
            res = {"odom": lambda: _odom_velocity(d, info, topic),
                   "flowvel": lambda: _flowvel(d, info, topic),
                   "flow": lambda: _flow(d, info, topic, ulog),
                   "localpos": lambda: _localpos(d, info, topic)}[kind]()
            if res is None or len(res[0]) < 3:
                continue
            info.reference_topic = topic
            info.reference_contaminated = not independent
            info.reference_source = f"px4:{topic}" + ("" if independent else "[EKF-FUSED,CONTAMINATED]")
            if not independent:
                info.warnings.insert(0, CONTAMINATED_WARNING + f" (source: {topic})")
            return res, info.reference_source
    if reference == "auto":
        info.warnings.insert(0, "NO velocity reference found (looked for " +
                             ", ".join(c[0] for c in cands if c[2] or allow_contaminated) +
                             "): slow carry-off spoofing cannot be detected without an independent reference.")
    else:
        info.warnings.insert(0, f"requested reference topic {reference!r} absent or unusable")
    return None, None


# ------------------------------------------------------------------------------------------- GPS
def _sat_cn0(ulog, info: UlogInfo):
    """satellite_info -> (t[], mean[], std[]) or None."""
    import numpy as np
    d = _pick_dataset(ulog, SAT_TOPICS, info, "satellites")
    if d is None:
        return None
    f = d.data
    cols = sorted((k for k in f if k.startswith("snr[")), key=lambda k: int(k[4:-1]))
    if not cols:
        info.warnings.append("satellite_info present but has no snr[] fields; no C/N0")
        return None
    snr = np.stack([f[c] for c in cols], axis=1).astype(float)
    cnt = f["count"].astype(int) if "count" in f else np.full(len(snr), snr.shape[1])
    t = f["timestamp"] / 1e6
    mean = np.full(len(t), np.nan)
    std = np.full(len(t), np.nan)
    for i in range(len(t)):
        row = snr[i, :min(cnt[i], snr.shape[1])]
        row = row[row > 0]
        if row.size:
            mean[i], std[i] = row.mean(), row.std()
    ok = np.isfinite(mean)
    if not ok.any():
        return None
    info.mapping["cn0"] = "satellite_info.snr[0..count) >0: mean/std (population) over tracked satellites"
    return t[ok], mean[ok], std[ok]


def _gps_fixes(ulog, info: UlogInfo, max_cn0_age: float):
    import numpy as np
    d = _pick_dataset(ulog, GPS_TOPICS, info, "GPS")
    if d is None:
        info.warnings.append(f"no GPS topic found (looked for {GPS_TOPICS}); nothing to score")
        return [], []
    info.gps_topic, info.gps_instance = d.name, d.multi_id
    f = d.data
    n = len(f["timestamp"])
    t = f["timestamp"] / 1e6
    m = info.mapping

    def col(key, required=False):
        nm, a = _first(f, ALIASES[key])
        if a is None and required:
            raise ValueError(f"{d.name}: required field {ALIASES[key]} not found; fields: {sorted(f)}")
        if a is not None:
            m[f"gps.{key}"] = nm
        return a

    lat, lon = col("lat", True), col("lon", True)
    if _is_int(lat) or np.nanmax(np.abs(lat)) > 180.0:
        lat, lon = lat / 1e7, lon / 1e7
        m["gps.lat/lon units"] = "1e-7 deg (autodetected from integer type / magnitude)"
    else:
        m["gps.lat/lon units"] = "degrees (autodetected)"
    alt = col("alt")
    alt_int = alt is not None and _is_int(alt)
    if alt is not None:
        alt = alt / 1e3 if alt_int else alt
        m["gps.alt units"] = "mm -> m (integer field)" if alt_int else "m (float field)"
    vn_, ve_ = col("vel_n"), col("vel_e")
    if vn_ is None or ve_ is None:
        info.warnings.append("GPS velocity fields missing; velocity-based checks degraded")
    fix = col("fix_type")
    if fix is None:
        info.warnings.append("fix_type missing; assuming 3D fix for every row")
    ns = col("n_sats")
    hdop = col("hdop")
    if hdop is None:
        info.warnings.append("hdop missing (hdop left unset)")
    agc_raw = col("agc")
    jind = col("jamming_indicator")
    if agc_raw is not None:
        agc, why = normalise_agc(agc_raw)
        m["gps.agc normalisation"] = why
    elif jind is not None:
        agc, why = normalise_agc(jind)
        m["gps.agc"] = "PROXY: jamming_indicator (not a true AGC reading)"
        m["gps.agc normalisation"] = why
        info.warnings.append("no AGC field; using jamming_indicator as an AGC proxy (different quantity, "
                             "scale unverified). Jamming sensitivity may differ from true AGC.")
    else:
        agc = [None] * n
    info.has_agc = agc_raw is not None or jind is not None
    tutc = col("time_utc")
    jam_s, spoof_s = col("jamming_state"), col("spoofing_state")
    col("noise_per_ms")
    info.has_px4_flags = jam_s is not None or spoof_s is not None

    sat = _sat_cn0(ulog, info)
    info.has_cn0 = sat is not None
    if sat is None:
        info.warnings.append("no satellite_info C/N0: signal-quality detector runs without C/N0 "
                             "(spoof-by-uniform-power and jamming-by-C/N0-drop evidence unavailable)")

    fixes, flags = [], []
    sj = 0
    for i in range(n):
        lat_i, lon_i = float(lat[i]), float(lon[i])
        if not (math.isfinite(lat_i) and math.isfinite(lon_i)):
            continue
        cm = cs = None
        if sat is not None:
            while sj + 1 < len(sat[0]) and sat[0][sj + 1] <= t[i] + 1e-3:
                sj += 1
            if sat[0][sj] <= t[i] + 1e-3 and t[i] - sat[0][sj] <= max_cn0_age:
                cm, cs = float(sat[1][sj]), float(sat[2][sj])
        tg = None
        if tutc is not None and tutc[i] > 0:
            tg = float(tutc[i]) / 1e6
        fixes.append(GnssFix(
            t=float(t[i]), lat=lat_i, lon=lon_i,
            alt=float(alt[i]) if alt is not None else 0.0,
            ve=_fin(ve_[i]) if ve_ is not None else None,
            vn=_fin(vn_[i]) if vn_ is not None else None,
            cn0_mean=cm, cn0_std=cs,
            n_sats=int(ns[i]) if ns is not None else None,
            agc=agc[i], hdop=_fin(hdop[i]) if hdop is not None else None,
            fix_type=int(fix[i]) if fix is not None else 3, t_gnss=tg))
        if info.has_px4_flags:
            flags.append(Px4Flag(t=float(t[i]),
                                 jamming_state=int(jam_s[i]) if jam_s is not None else None,
                                 spoofing_state=int(spoof_s[i]) if spoof_s is not None else None,
                                 jamming_indicator=_fin(jind[i]) if jind is not None else None))
    if len(t) > 1:
        info.gps_rate_hz = float((len(t) - 1) / max(t[-1] - t[0], 1e-9))
    return fixes, flags


def _fin(x) -> Optional[float]:
    x = float(x)
    return x if math.isfinite(x) else None


# --------------------------------------------------------------------------------------- public
def load_ulog(path: str, *, reference: str = "auto", allow_contaminated: bool = True,
              merge_tol: float = 0.002, max_cn0_age: float = 5.0, warn: bool = True) -> UlogData:
    """Parse a ULog into NavSamples (time ordered) + UlogInfo + PX4 flag side-series.

    reference: 'auto' (priority: visual odometry, mocap, optical-flow velocity, optical flow, then the
               CONTAMINATED EKF fallbacks vehicle_local_position / vehicle_odometry) or a topic name.
    allow_contaminated: if False, EKF-derived references are never used (no reference => no carry-off check).
    merge_tol: GNSS and reference rows closer than this (s) are put in one NavSample.
    """
    ULog = _import_pyulog()
    ulog = ULog(path, disable_str_exceptions=True)
    info = UlogInfo(path=str(path))
    info.duration_s = (ulog.last_timestamp - ulog.start_timestamp) / 1e6
    for d in ulog.data_list:
        e = info.topics.setdefault(d.name, {"n": 0, "multi_ids": [], "fields": sorted(d.data)})
        e["n"] += len(d.data.get("timestamp", []))
        e["multi_ids"].append(d.multi_id)
    syn = ulog.msg_info_dict.get("marsad_synthetic")
    if syn:
        info.synthetic, info.synthetic_note = True, str(syn)
    if ulog.file_corruption:
        info.warnings.append("pyulog reported file corruption / truncation; data may be incomplete")

    fixes, flags = _gps_fixes(ulog, info, max_cn0_age)
    ref, src = _select_reference(ulog, info, reference, allow_contaminated)
    refs = []
    if ref is not None:
        rt, rve, rvn, rsig = ref
        for i in range(len(rt)):
            s = None if rsig is None or not math.isfinite(rsig[i]) else float(rsig[i])
            refs.append(RefMotion(t=float(rt[i]), ve=float(rve[i]), vn=float(rvn[i]), sigma=s, source=src))
    info.n_gnss, info.n_ref = len(fixes), len(refs)

    events = [(g.t, 0, g) for g in fixes] + [(r.t, 1, r) for r in refs]
    events.sort(key=lambda e: (e[0], e[1]))
    samples: list[NavSample] = []
    for t, kind, obj in events:
        last = samples[-1] if samples else None
        if last is not None and abs(t - last.t) <= merge_tol:
            if kind == 0 and last.gnss is None:
                last.gnss = obj
                continue
            if kind == 1 and last.ref is None:
                last.ref = obj
                continue
        samples.append(NavSample(t=t, gnss=obj if kind == 0 else None, ref=obj if kind == 1 else None))
    # NavSample.t = first event time; keep monotone
    for a, b in zip(samples, samples[1:]):
        if b.t < a.t:           # pragma: no cover (merge can only move forward)
            b.t = a.t
    if warn and info.reference_contaminated:
        warnings.warn(CONTAMINATED_WARNING, ContaminatedReferenceWarning, stacklevel=3)
    return UlogData(samples=samples, info=info, px4_flags=flags)


def read_ulog_samples(path: str, *, reference: str = "auto", allow_contaminated: bool = True,
                      merge_tol: float = 0.002, max_cn0_age: float = 5.0) -> Iterator[NavSample]:
    """Iterate NavSamples from a ULog. Use load_ulog() when you also need the metadata / PX4 flags.

    Emits ContaminatedReferenceWarning (via warnings) if the only reference is EKF-fused.
    """
    data = load_ulog(path, reference=reference, allow_contaminated=allow_contaminated,
                     merge_tol=merge_tol, max_cn0_age=max_cn0_age)
    yield from data.samples


def inspect_ulog(path: str, **kw) -> UlogInfo:
    """Topics found, field mapping used, warnings and reference source -- without scoring anything."""
    kw.setdefault("warn", False)
    return load_ulog(path, **kw).info
