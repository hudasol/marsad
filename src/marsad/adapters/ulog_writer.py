"""Minimal ULog (v1) binary writer for SYNTHETIC PX4-style logs made from simulator output.

These logs are produced by the Marsad measurement-level simulator. They are NOT real flight data, they
contain no real PX4 firmware output, and the topic layouts are our best recollection of PX4's (see
docs/ADAPTERS.md, known unknowns). They exist to exercise the ULog reader end to end. The first thing to
do once a real PX4 log is available is to replay it (`marsad inspect`, `marsad replay`).

Format reference (public ULog spec): 16-byte header (magic 55 4C 6F 67 01 12 35, version, u64 start
timestamp), then messages [u16 size][u8 type][payload]: 'B' flag bits (first), 'F' format, 'I' info,
'A' subscription, 'D' data.
"""
from __future__ import annotations
import math
import struct
from statistics import NormalDist
from typing import Callable, Iterable, Optional, Union

from ..types import GnssFix, NavSample, RefMotion
from ._common import SYNTHETIC_BANNER

MAGIC = b"\x55\x4c\x6f\x67\x01\x12\x35"
UTC_BASE = 1_700_000_000.0          # arbitrary synthetic UTC epoch (2023-11-14) added to GNSS time
AGC_FULL_SCALE = 8191.0
MAX_SATS = 20

_CT = {"uint64_t": ("Q", 8), "int64_t": ("q", 8), "uint32_t": ("I", 4), "int32_t": ("i", 4),
       "uint16_t": ("H", 2), "int16_t": ("h", 2), "uint8_t": ("B", 1), "int8_t": ("b", 1),
       "float": ("f", 4), "double": ("d", 8), "bool": ("?", 1), "char": ("c", 1)}


class Topic:
    """A flat, packed ULog message definition. fields = [(ctype, name, array_len or 0)].

    No trailing padding is written: pyulog (1.2.x) treats data longer than the unpadded format as corrupt,
    and real PX4 logs omit the trailing `_padding` bytes. Field order is chosen so no interior padding
    is needed (largest types first).
    """

    def __init__(self, name: str, fields: list):
        self.name = name
        self.fields = list(fields)
        fmt = "<"
        for t, _, n in self.fields:
            fmt += _CT[t][0] * (n or 1)
        self._st = struct.Struct(fmt)

    @property
    def format_string(self) -> str:
        parts = []
        for t, nm, n in self.fields:
            parts.append(f"{t}[{n}] {nm};" if n else f"{t} {nm};")
        return f"{self.name}:" + "".join(parts)

    def pack(self, values: dict) -> bytes:
        flat = []
        for t, nm, n in self.fields:
            if n:
                v = values.get(nm, [0] * n)
                flat.extend(v)
            else:
                flat.append(values.get(nm, 0))
        return self._st.pack(*flat)


SENSOR_GPS = Topic("sensor_gps", [
    ("uint64_t", "timestamp", 0), ("uint64_t", "time_utc_usec", 0),
    ("int32_t", "lat", 0), ("int32_t", "lon", 0), ("int32_t", "alt", 0),
    ("float", "vel_n_m_s", 0), ("float", "vel_e_m_s", 0), ("float", "hdop", 0), ("float", "eph", 0),
    ("uint32_t", "noise_per_ms", 0), ("uint16_t", "automatic_gain_control", 0),
    ("uint16_t", "jamming_indicator", 0),
    ("uint8_t", "fix_type", 0), ("uint8_t", "satellites_used", 0),
    ("uint8_t", "jamming_state", 0), ("uint8_t", "spoofing_state", 0)])
# Layout of current PX4 main (verified against PX4-Autopilot msg docs, Oct 2026): float64 degrees, metres.
SENSOR_GPS_CURRENT = Topic("sensor_gps", [
    ("uint64_t", "timestamp", 0), ("uint64_t", "time_utc_usec", 0),
    ("double", "latitude_deg", 0), ("double", "longitude_deg", 0), ("double", "altitude_msl_m", 0),
    ("float", "vel_n_m_s", 0), ("float", "vel_e_m_s", 0), ("float", "hdop", 0), ("float", "eph", 0),
    ("int32_t", "noise_per_ms", 0), ("int32_t", "jamming_indicator", 0),
    ("uint16_t", "automatic_gain_control", 0),
    ("uint8_t", "fix_type", 0), ("uint8_t", "satellites_used", 0),
    ("uint8_t", "jamming_state", 0), ("uint8_t", "spoofing_state", 0)])
SATELLITE_INFO = Topic("satellite_info", [
    ("uint64_t", "timestamp", 0), ("uint8_t", "count", 0),
    ("uint8_t", "svid", MAX_SATS), ("uint8_t", "used", MAX_SATS), ("uint8_t", "elevation", MAX_SATS),
    ("uint8_t", "azimuth", MAX_SATS), ("uint8_t", "snr", MAX_SATS), ("uint8_t", "prn", MAX_SATS)])
VISUAL_ODOMETRY = Topic("vehicle_visual_odometry", [
    ("uint64_t", "timestamp", 0), ("uint64_t", "timestamp_sample", 0),
    ("float", "position", 3), ("float", "q", 4), ("float", "velocity", 3),
    ("float", "angular_velocity", 3), ("float", "position_variance", 3),
    ("float", "orientation_variance", 3), ("float", "velocity_variance", 3),
    ("uint8_t", "pose_frame", 0), ("uint8_t", "velocity_frame", 0),
    ("uint8_t", "reset_counter", 0), ("int8_t", "quality", 0)])
NAN = float("nan")


def _msg(mtype: bytes, payload: bytes) -> bytes:
    return struct.pack("<HB", len(payload), mtype[0]) + payload


def _info(key: str, value, ctype: str = "char") -> bytes:
    if ctype == "char":
        v = value.encode("ascii", "replace")
        k = f"char[{len(v)}] {key}".encode()
    else:
        code = _CT[ctype][0]
        v = struct.pack("<" + code, value)
        k = f"{ctype} {key}".encode()
    return _msg(b"I", bytes([len(k)]) + k + v)


def sat_snrs(mean: float, std: float, k: int) -> list:
    """k integer SNR values (dB-Hz, 1..99) whose mean and (population) std approximate the targets.

    Deterministic. Start from standard-normal quantiles scaled to the target std, rounded with error
    diffusion, then greedily move 1 dB between satellite pairs while that reduces the mean/std error.
    The residual error is bounded by the uint8 quantisation PX4's satellite_info itself has.
    """
    nd = NormalDist()
    z = [nd.inv_cdf((i + 0.5) / k) for i in range(k)]
    zs = math.sqrt(sum(x * x for x in z) / k) or 1.0
    v, carry = [], 0.0
    for x in z:
        want = mean + std * x / zs + carry
        q = int(min(max(round(want), 1), 99))
        carry = want - q
        v.append(q)

    S = sum(v)
    m = S / k
    best_q = sum(a * a for a in v)

    def err(q):
        sd = math.sqrt(max(q / k - m * m, 0.0))
        return abs(m - mean) + abs(sd - std)

    best = err(best_q)
    for _ in range(4 * k):
        cand = None
        for i in range(k):
            for d in (1, -1):
                if not 1 <= v[i] + d <= 99:
                    continue
                for j in range(k):
                    if i == j or not 1 <= v[j] - d <= 99:
                        continue
                    q = best_q + 2 * d * (v[i] - v[j]) + 2     # mean unchanged: sum is conserved
                    e = err(q)
                    if e < best - 1e-9:
                        best, cand, cq = e, (i, j, d), q
        if cand is None:
            break
        i, j, d = cand
        v[i] += d
        v[j] -= d
        best_q = cq
    return v


def _samples_of(src):
    return src.samples if hasattr(src, "samples") else list(src)


def write_ulog(path: str, source, *, include_satellite_info: bool = True, note: Optional[str] = None,
               scenario: Optional[str] = None, seed: Optional[int] = None,
               flag_fn: Optional[Callable[[float], tuple]] = None, schema: str = "legacy") -> dict:
    """Write a synthetic PX4-style ULog from a marsad.sim.Run (or an iterable of NavSample).

    Writes sensor_gps (+ satellite_info for C/N0) and vehicle_visual_odometry (the simulated independent
    reference) in the same timestamp as the originating NavSample. PX4's own jamming_state/spoofing_state
    are written as 0 (unknown): the simulator does not model a receiver's built-in detector, so no PX4
    flag behaviour is invented. `flag_fn(t) -> (jamming_state, spoofing_state)` is a TEST HOOK to exercise
    the flag-comparison path; it is not a model of any receiver. Returns a small dict describing what was written.
    """
    samples = _samples_of(source)
    if scenario is None and hasattr(source, "kind"):
        scenario, seed = source.kind, getattr(source, "seed", None)
    if not samples:
        raise ValueError("no samples to write")
    t0_us = int(round(samples[0].t * 1e6))
    gps_topic = SENSOR_GPS_CURRENT if schema == "current" else SENSOR_GPS
    topics = [gps_topic, VISUAL_ODOMETRY] + ([SATELLITE_INFO] if include_satellite_info else [])
    out = bytearray(MAGIC + bytes([1]) + struct.pack("<Q", t0_us))
    out += _msg(b"B", bytes(8) + bytes(8) + bytes(24))                     # compat, incompat, appended offsets
    out += _info("marsad_synthetic", note or SYNTHETIC_BANNER)
    if scenario:
        out += _info("marsad_scenario", scenario)
    if seed is not None:
        out += _info("marsad_seed", int(seed), "int32_t")
    for tp in topics:
        out += _msg(b"F", tp.format_string.encode())
    ids = {}
    for i, tp in enumerate(topics):
        ids[tp.name] = i
        out += _msg(b"A", struct.pack("<BH", 0, i) + tp.name.encode())
    n_gps = n_ref = 0
    for s in samples:
        ts = int(round(s.t * 1e6))
        g, r = s.gnss, s.ref
        if g is not None:
            n_gps += 1
            jf, sf = flag_fn(s.t) if flag_fn else (0, 0)
            agc = 0 if g.agc is None else int(min(max(round(g.agc * AGC_FULL_SCALE), 0), 65535))
            out += _msg(b"D", struct.pack("<H", ids["sensor_gps"]) + gps_topic.pack({
                "timestamp": ts,
                "time_utc_usec": 0 if g.t_gnss is None else int(round((g.t_gnss + UTC_BASE) * 1e6)),
                **({"latitude_deg": g.lat, "longitude_deg": g.lon, "altitude_msl_m": g.alt}
                   if schema == "current" else
                   {"lat": int(round(g.lat * 1e7)), "lon": int(round(g.lon * 1e7)),
                    "alt": int(round(g.alt * 1e3))}),
                "vel_n_m_s": NAN if g.vn is None else g.vn, "vel_e_m_s": NAN if g.ve is None else g.ve,
                "hdop": NAN if g.hdop is None else g.hdop, "eph": NAN,
                "automatic_gain_control": agc, "fix_type": g.fix_type,
                "satellites_used": 0 if g.n_sats is None else min(int(g.n_sats), 255),
                "jamming_state": jf, "spoofing_state": sf}))
            if include_satellite_info and g.cn0_mean is not None:
                k = MAX_SATS                         # tracked channels (>= used); gives snr stats enough resolution
                snr = sat_snrs(g.cn0_mean, g.cn0_std if g.cn0_std is not None else 0.0, k)
                pad = lambda v: list(v) + [0] * (MAX_SATS - len(v))      # noqa: E731
                used = [1] * min(int(g.n_sats or 0), k)
                out += _msg(b"D", struct.pack("<H", ids["satellite_info"]) + SATELLITE_INFO.pack({
                    "timestamp": ts, "count": k, "svid": pad(range(1, k + 1)), "used": pad(used),
                    "elevation": pad([45] * k), "azimuth": pad([0] * k), "snr": pad(snr),
                    "prn": pad(range(1, k + 1))}))
        if r is not None:
            n_ref += 1
            var = (r.sigma ** 2) if r.sigma is not None else NAN
            out += _msg(b"D", struct.pack("<H", ids["vehicle_visual_odometry"]) + VISUAL_ODOMETRY.pack({
                "timestamp": ts, "timestamp_sample": ts,
                "position": [NAN] * 3, "q": [1.0, 0.0, 0.0, 0.0],
                "velocity": [r.vn, r.ve, 0.0], "angular_velocity": [NAN] * 3,
                "position_variance": [NAN] * 3, "orientation_variance": [NAN] * 3,
                "velocity_variance": [var, var, var],
                "pose_frame": 1, "velocity_frame": 1, "reset_counter": 0, "quality": 100}))
    with open(path, "wb") as fh:
        fh.write(out)
    return {"path": str(path), "bytes": len(out), "gps_rows": n_gps, "ref_rows": n_ref,
            "topics": [t.name for t in topics], "synthetic": True}
