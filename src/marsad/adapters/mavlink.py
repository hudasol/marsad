"""MAVLink adapter: live link / .tlog -> NavSample stream, and an advisory-only trust reporter.

pymavlink is imported lazily. Message and field names below were checked against the pymavlink 2.4.x
'all' dialect bundled with this repo's environment (field NAMES and the GNSS_INTEGRITY message are
verified there), but semantics against real autopilots (what PX4/ArduPilot actually put in each field,
which streams a given vehicle emits) are UNVERIFIED -- see docs/ADAPTERS.md.

ADVISORY ONLY: MavlinkReporter can emit exactly NAMED_VALUE_FLOAT, STATUSTEXT and (optionally)
HEARTBEAT. It never sends commands, mode changes, position/setpoint messages or parameter writes; this is
enforced in one choke point (`_send`) and covered by a test.
"""
from __future__ import annotations
import math
import os
from collections import deque
from typing import Iterable, Iterator, Optional

from ..types import GnssFix, NavSample, RefMotion, TrustReport, TrustState
from ._common import CONTAMINATED_WARNING, ContaminatedReferenceWarning, mean_std
from .ulog import Px4Flag

# MAV_ESTIMATOR_TYPE values that are independent of GNSS (verified in the 'all' dialect)
_EST_INDEPENDENT = {2: "VISION", 3: "VIO", 6: "MOCAP", 7: "LIDAR"}
_EST_NAMES = {0: "UNKNOWN", 1: "NAIVE", 2: "VISION", 3: "VIO", 4: "GPS", 5: "GPS_INS", 6: "MOCAP",
              7: "LIDAR", 8: "AUTOPILOT"}
# MAV_FRAME ids we can interpret
_F_LOCAL_NED, _F_LOCAL_ENU, _F_BODY_FRD, _F_LOCAL_FRD = 1, 4, 12, 20
ALLOWED_OUT = frozenset({"NAMED_VALUE_FLOAT", "STATUSTEXT", "HEARTBEAT"})

STATE_CODE = {TrustState.TRUSTED: 0, TrustState.DEGRADED: 1, TrustState.DENIED: 2}


def _import_mavutil(dialect: str = "all"):
    os.environ.setdefault("MAVLINK20", "1")
    try:
        from pymavlink import mavutil
    except ImportError as e:        # pragma: no cover
        raise ImportError("MAVLink support needs pymavlink: pip install pymavlink  (or marsad[adapters])") from e
    return mavutil


def dialect_module(name: str = "all"):
    """The MAVLink 2 dialect module ('all' includes GNSS_INTEGRITY on current pymavlink; 'common' may not)."""
    os.environ.setdefault("MAVLINK20", "1")
    import importlib
    return importlib.import_module(f"pymavlink.dialects.v20.{name}")


def has_gnss_integrity(name: str = "all") -> bool:
    return hasattr(dialect_module(name), "MAVLink_gnss_integrity_message")


# ----------------------------------------------------------------------------- pure message layer
def _fin(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def cn0_from_gps_status(msg) -> tuple:
    """GPS_STATUS -> (mean, std, n_used, n_tracked) over satellites with non-zero SNR (dB-Hz)."""
    snr = list(getattr(msg, "satellite_snr", []) or [])
    used = list(getattr(msg, "satellite_used", []) or [])
    n = int(getattr(msg, "satellites_visible", len(snr)) or 0)
    vals = [int(s) for s in snr[:max(n, 0) or len(snr)] if int(s) > 0]
    m, sd = mean_std(vals)
    return m, sd, sum(1 for u in used if int(u)), len(vals)


def sample_from_gps_raw_int(msg, t: Optional[float] = None, *, cn0: Optional[tuple] = None,
                            agc: Optional[float] = None) -> GnssFix:
    """GPS_RAW_INT -> GnssFix.

    Units (MAVLink spec): lat/lon degE7, alt mm, eph = HDOP*100 (65535 unknown), vel = ground speed cm/s
    (65535 unknown), cog = course cdeg (65535 unknown), satellites_visible (255 unknown). Velocity is
    decomposed with cog, so it is unreliable at very low speed. t_gnss is set only if time_usec looks like
    a UNIX-epoch value (>1e15 us); on many autopilots it is time-since-boot and is then ignored.
    cn0: optional (mean, std, ...) tuple from cn0_from_gps_status (GPS_STATUS is a separate message).
    """
    if t is None:
        t = float(getattr(msg, "_timestamp", 0.0))
    vel, cog = getattr(msg, "vel", 65535), getattr(msg, "cog", 65535)
    ve = vn = None
    if vel != 65535 and cog != 65535:
        v, c = vel / 100.0, math.radians(cog / 100.0)
        ve, vn = v * math.sin(c), v * math.cos(c)
    eph = getattr(msg, "eph", 65535)
    nsat = getattr(msg, "satellites_visible", 255)
    tu = getattr(msg, "time_usec", 0)
    return GnssFix(
        t=float(t), lat=msg.lat / 1e7, lon=msg.lon / 1e7, alt=msg.alt / 1e3, ve=ve, vn=vn,
        cn0_mean=cn0[0] if cn0 else None, cn0_std=cn0[1] if cn0 else None,
        n_sats=None if nsat == 255 else int(nsat), agc=agc,
        hdop=None if eph == 65535 else eph / 100.0,
        fix_type=int(msg.fix_type), t_gnss=(tu / 1e6) if tu > 1e15 else None)


def gnss_integrity_flag(msg, t: float) -> Px4Flag:
    """GNSS_INTEGRITY (id 441) -> receiver's own jamming/spoofing state (side-series, not fed to the engine).

    Enums (verified in dialect): jamming 0 unknown,1 not jammed,2 mitigated,3 detected; spoofing likewise.
    """
    return Px4Flag(t=float(t), jamming_state=int(msg.jamming_state), spoofing_state=int(msg.spoofing_state))


def _yaw_from_q(q) -> Optional[float]:
    try:
        w, x, y, z = (float(v) for v in q)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (w, x, y, z)) or (w * w + x * x + y * y + z * z) < 0.5:
        return None
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _rot(vx, vy, yaw):
    """Body/FRD horizontal vector -> (north, east) using yaw (rad from north, clockwise)."""
    return vx * math.cos(yaw) - vy * math.sin(yaw), vx * math.sin(yaw) + vy * math.cos(yaw)


def ref_from_odometry(msg, t: float) -> Optional[tuple]:
    """ODOMETRY -> (RefMotion, independent: bool, label) or None if the frame/velocity is unusable."""
    vx, vy = _fin(msg.vx), _fin(msg.vy)
    if vx is None or vy is None:
        return None
    # ODOMETRY: frame_id = pose frame; child_frame_id = velocity frame
    vfr = int(msg.child_frame_id)
    if vfr == _F_LOCAL_NED:
        vn, ve = vx, vy
    elif vfr == _F_LOCAL_ENU:
        ve, vn = vx, vy
    elif vfr in (_F_BODY_FRD, _F_LOCAL_FRD):
        yaw = _yaw_from_q(msg.q)
        if yaw is None:
            return None
        vn, ve = _rot(vx, vy, yaw)
    else:
        return None
    est = int(getattr(msg, "estimator_type", 0))
    independent = est in _EST_INDEPENDENT
    cov = getattr(msg, "velocity_covariance", None)
    sig = None
    if cov is not None and len(cov) > 0 and _fin(cov[0]) is not None and cov[0] > 0:
        sig = math.sqrt(cov[0])
    label = f"mavlink:ODOMETRY(est={_EST_NAMES.get(est, est)})" + ("" if independent else "[CONTAMINATED?]")
    return RefMotion(t=float(t), ve=ve, vn=vn, sigma=sig, source=label), independent, label


def ref_from_optical_flow_rad(msg, t: float, yaw: Optional[float], distance_m: Optional[float],
                              min_quality: int = 50) -> Optional[RefMotion]:
    """OPTICAL_FLOW_RAD (+ range) -> RefMotion. UNVERIFIED axis/sign convention (see docs)."""
    dt = msg.integration_time_us / 1e6
    d = msg.distance if msg.distance >= 0 else distance_m
    if dt <= 0 or d is None or d <= 0 or yaw is None or msg.quality < min_quality:
        return None
    vbx = (msg.integrated_y - msg.integrated_ygyro) / dt * d
    vby = -(msg.integrated_x - msg.integrated_xgyro) / dt * d
    vn, ve = _rot(vbx, vby, yaw)
    return RefMotion(t=float(t), ve=ve, vn=vn, sigma=None, source="mavlink:OPTICAL_FLOW_RAD+range")


def ref_from_optical_flow(msg, t: float, yaw: Optional[float], min_quality: int = 50) -> Optional[RefMotion]:
    """OPTICAL_FLOW (flow_comp_m_x/y body-frame m/s) -> RefMotion."""
    if yaw is None or msg.quality < min_quality:
        return None
    vn, ve = _rot(msg.flow_comp_m_x, msg.flow_comp_m_y, yaw)
    return RefMotion(t=float(t), ve=ve, vn=vn, sigma=None, source="mavlink:OPTICAL_FLOW")


def ref_from_local_position_ned(msg, t: float) -> Optional[RefMotion]:
    vn, ve = _fin(msg.vx), _fin(msg.vy)
    if vn is None or ve is None:
        return None
    return RefMotion(t=float(t), ve=ve, vn=vn, sigma=None,
                     source="mavlink:LOCAL_POSITION_NED[EKF-FUSED,CONTAMINATED]")


# ------------------------------------------------------------------------------------ stateful map
class MavlinkMapper:
    """Feed decoded MAVLink messages (any order a link produces); get NavSamples. No I/O, fully offline.

    Reference policy: independent sources (ODOMETRY with a VISION/VIO/MOCAP/LIDAR estimator_type,
    OPTICAL_FLOW[_RAD]) are always preferred. EKF-derived ones (ODOMETRY from GPS/AUTOPILOT, LOCAL_POSITION_NED)
    are used ONLY if no independent source has ever been seen in the stream, and only when
    allow_contaminated=True; a loud warning is recorded and emitted via warnings.warn.
    """

    def __init__(self, *, allow_contaminated: bool = True, ref_ids: Optional[Iterable[tuple]] = None,
                 max_cn0_age: float = 5.0, min_flow_quality: int = 50, warn: bool = True):
        self.allow_contaminated = allow_contaminated
        self.ref_ids = set(ref_ids) if ref_ids else None      # {(sysid, compid)} allowed for ODOMETRY
        self.max_cn0_age = max_cn0_age
        self.min_flow_quality = min_flow_quality
        self.warn = warn
        self.warnings: list = []
        self.flags: list = []                 # Px4Flag series from GNSS_INTEGRITY
        self.ref_source: Optional[str] = None
        self.ref_contaminated = False
        self.counts: dict = {}
        self._t = -math.inf
        self._cn0 = None                      # (t, mean, std, used, tracked)
        self._yaw = None
        self._dist = None
        self._independent_seen = False
        self._contam_warned = False

    def _warn(self, text: str):
        if text not in self.warnings:
            self.warnings.append(text)

    def _tick(self, msg, t):
        if t is None:
            t = float(getattr(msg, "_timestamp", None) or 0.0)
        self._t = max(self._t, float(t))      # guard against non-monotonic log stamps
        return self._t

    def feed(self, msg, t: Optional[float] = None) -> list:
        typ = msg.get_type()
        if typ == "BAD_DATA":
            return []
        self.counts[typ] = self.counts.get(typ, 0) + 1
        t = self._tick(msg, t)
        if typ == "GPS_RAW_INT":
            cn0 = None
            if self._cn0 and t - self._cn0[0] <= self.max_cn0_age:
                cn0 = self._cn0[1:3]
            elif self._cn0 is None:
                self._warn("no GPS_STATUS seen yet: C/N0-based evidence unavailable (request GPS_STATUS stream)")
            fix = sample_from_gps_raw_int(msg, t, cn0=cn0)
            return [NavSample(t=t, gnss=fix)]
        if typ == "GPS_STATUS":
            m, sd, used, trk = cn0_from_gps_status(msg)
            if m is not None:
                self._cn0 = (t, m, sd, used, trk)
            return []
        if typ == "GNSS_INTEGRITY":
            self.flags.append(gnss_integrity_flag(msg, t))
            return []
        if typ == "ATTITUDE":
            self._yaw = float(msg.yaw)
            return []
        if typ == "ATTITUDE_QUATERNION":
            self._yaw = _yaw_from_q((msg.q1, msg.q2, msg.q3, msg.q4))
            return []
        if typ == "DISTANCE_SENSOR":
            d = msg.current_distance / 100.0
            if msg.min_distance <= msg.current_distance <= msg.max_distance:
                self._dist = d
            return []
        ref = None
        if typ == "ODOMETRY":
            if self.ref_ids is not None and (msg.get_srcSystem(), msg.get_srcComponent()) not in self.ref_ids:
                return []
            res = ref_from_odometry(msg, t)
            if res is None:
                self._warn("ODOMETRY with unsupported frame or non-finite velocity ignored")
                return []
            ref, independent, _ = res
        elif typ == "OPTICAL_FLOW_RAD":
            ref, independent = ref_from_optical_flow_rad(msg, t, self._yaw, self._dist, self.min_flow_quality), True
        elif typ == "OPTICAL_FLOW":
            ref, independent = ref_from_optical_flow(msg, t, self._yaw, self.min_flow_quality), True
        elif typ == "LOCAL_POSITION_NED":
            ref, independent = ref_from_local_position_ned(msg, t), False
        else:
            return []
        if ref is None:
            return []
        if independent:
            self._independent_seen = True
            self.ref_contaminated = False
        else:
            if self._independent_seen or not self.allow_contaminated:
                return []
            self.ref_contaminated = True
            if not self._contam_warned:
                self._contam_warned = True
                self._warn(CONTAMINATED_WARNING + f" (source: {ref.source})")
                if self.warn:
                    import warnings
                    warnings.warn(CONTAMINATED_WARNING, ContaminatedReferenceWarning, stacklevel=3)
        self.ref_source = ref.source
        return [NavSample(t=t, ref=ref)]


class MavlinkSource:
    """Iterate NavSamples from a MAVLink connection string (udp:, udpin:, tcp:, serial path, or a .tlog).

    For files the iterator ends at EOF; for live links it runs until close() or `idle_timeout` seconds
    without any message. The mapper (warnings, GNSS_INTEGRITY flags, reference source) is `.mapper`.
    """

    def __init__(self, connection, *, allow_contaminated: bool = True, ref_ids=None,
                 idle_timeout: Optional[float] = None, dialect: str = "all", warn: bool = True):
        self.connection = connection
        self.idle_timeout = idle_timeout
        self.mapper = MavlinkMapper(allow_contaminated=allow_contaminated, ref_ids=ref_ids, warn=warn)
        if isinstance(connection, str):
            mavutil = _import_mavutil(dialect)
            self._conn = mavutil.mavlink_connection(connection, dialect=dialect)
            self.is_file = os.path.isfile(connection)
        else:                                  # injected connection-like object (tests)
            self._conn = connection
            self.is_file = True
        self._closed = False
        if not has_gnss_integrity(dialect):
            self.mapper._warn(f"dialect {dialect!r} has no GNSS_INTEGRITY; receiver jamming/spoofing flags unavailable")

    def close(self):
        self._closed = True
        try:
            self._conn.close()
        except Exception:                      # pragma: no cover
            pass

    def messages(self) -> Iterator:
        import time
        last = time.monotonic()
        while not self._closed:
            msg = self._conn.recv_match(blocking=not self.is_file, timeout=None if self.is_file else 1.0)
            if msg is None:
                if self.is_file:
                    return
                if self.idle_timeout is not None and time.monotonic() - last > self.idle_timeout:
                    return
                continue
            last = time.monotonic()
            yield msg

    def samples(self) -> Iterator[NavSample]:
        for msg in self.messages():
            yield from self.mapper.feed(msg)

    __iter__ = samples


def read_tlog_samples(path: str, **kw) -> Iterator[NavSample]:
    src = MavlinkSource(path, **kw)
    try:
        yield from src.samples()
    finally:
        src.close()


# -------------------------------------------------------------------------------------- reporting
def named_values(report: TrustReport) -> list:
    """The two NAMED_VALUE_FLOAT payloads: MSD_TRUST (0..1) and MSD_STATE (0 trusted,1 degraded,2 denied)."""
    return [("MSD_TRUST", float(report.trust)), ("MSD_STATE", float(STATE_CODE[report.state]))]


def status_text(prev: Optional[TrustState], report: TrustReport) -> Optional[tuple]:
    """(severity, text<=50 chars) on a state change, else None. Severity: DEGRADED=4 WARNING, DENIED=2 CRITICAL,
    recovery to TRUSTED=5 NOTICE. The very first TRUSTED report produces nothing."""
    if report.state == prev or (prev is None and report.state == TrustState.TRUSTED):
        return None
    sev = {TrustState.DEGRADED: 4, TrustState.DENIED: 2, TrustState.TRUSTED: 5}[report.state]
    cause = "" if report.state == TrustState.TRUSTED else f" {report.dominant}"
    text = f"MSD {report.state.value}{cause} trust={report.trust:.2f}"
    return sev, text.encode("ascii", "replace").decode()[:50]


class MavlinkReporter:
    """Publish a TrustReport on MAVLink -- ADVISORY ONLY.

    Emits NAMED_VALUE_FLOAT MSD_TRUST / MSD_STATE at <= rate_hz (by report time), STATUSTEXT only when the
    state changes, and (optional, off by default) a HEARTBEAT identifying an onboard controller with no
    autopilot/mode semantics. Nothing else can be sent: `_send` rejects every other message type.

    connection: a pymavlink connection string for an *output* link (e.g. 'udpout:127.0.0.1:14550',
    'serial:/dev/ttyAMA0:57600') or a file-like object with write(bytes) (used by tests).
    """

    def __init__(self, connection, *, rate_hz: float = 2.0, system_id: int = 1, component_id: int = 191,
                 heartbeat: bool = False, dialect: str = "all"):
        self.min_interval = 1.0 / rate_hz
        self.use_heartbeat = heartbeat
        self.sent = deque(maxlen=1000)         # names of messages sent (introspection / tests)
        self._last_pub: Optional[float] = None
        self._last_hb: Optional[float] = None
        self._prev: Optional[TrustState] = None
        self._t0: Optional[float] = None
        self._mod = dialect_module(dialect)
        if isinstance(connection, str):
            mavutil = _import_mavutil(dialect)
            self._conn = mavutil.mavlink_connection(connection, source_system=system_id,
                                                    source_component=component_id, dialect=dialect)
            self._mav = self._conn.mav
        else:
            self._conn = None
            self._mav = self._mod.MAVLink(connection, srcSystem=system_id, srcComponent=component_id)

    def _send(self, msg) -> None:
        name = msg.get_type()
        if name not in ALLOWED_OUT:            # the single choke point: advisory messages only
            raise RuntimeError(f"MavlinkReporter refuses to send {name}: advisory-only adapter")
        self._mav.send(msg)
        self.sent.append(name)

    def publish(self, report: TrustReport) -> list:
        """Send what is due for this report; returns the list of message names sent."""
        mod, out = self._mod, []
        if self._t0 is None:
            self._t0 = report.t
        boot_ms = int(max(report.t - self._t0, 0.0) * 1000) & 0xFFFFFFFF
        st = status_text(self._prev, report)
        if st is not None:
            self._send(mod.MAVLink_statustext_message(st[0], st[1].encode("ascii"), 0, 0))
            out.append("STATUSTEXT")
        self._prev = report.state
        if self._last_pub is None or report.t - self._last_pub >= self.min_interval - 1e-9:
            self._last_pub = report.t
            for name, val in named_values(report):
                self._send(mod.MAVLink_named_value_float_message(boot_ms, name.encode("ascii"), val))
                out.append("NAMED_VALUE_FLOAT")
        if self.use_heartbeat and (self._last_hb is None or report.t - self._last_hb >= 1.0):
            self._last_hb = report.t
            self._send(mod.MAVLink_heartbeat_message(
                mod.MAV_TYPE_ONBOARD_CONTROLLER, mod.MAV_AUTOPILOT_INVALID, 0, 0, mod.MAV_STATE_ACTIVE, 3))
            out.append("HEARTBEAT")
        return out

    def close(self):
        if self._conn is not None:
            self._conn.close()
