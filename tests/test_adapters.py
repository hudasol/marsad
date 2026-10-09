"""Adapter tests: ULog writer/reader round trip, reference selection, CLI. All data is SYNTHETIC."""
import json
import math
import struct
import subprocess
import sys
import warnings

import numpy as np
import pytest

pytest.importorskip("pyulog")
from pyulog import ULog

from marsad import TrustEngine, preset
from marsad.adapters._common import ContaminatedReferenceWarning, normalise_agc
from marsad.adapters.replay import replay_samples
from marsad.adapters.ulog import inspect_ulog, load_ulog, read_ulog_samples
from marsad.adapters.ulog_writer import MAGIC, UTC_BASE, Topic, _info, _msg, sat_snrs, write_ulog
from marsad.cli import main
from marsad.sim import generate


def states(samples, cfg="uav_multirotor"):
    e = TrustEngine(preset(cfg))
    return [e.update(s).state.value for s in samples]


def transitions(samples, st):
    out, prev = [], None
    for s, x in zip(samples, st):
        if x != prev:
            out.append((s.t, x))
            prev = x
    return out


def test_adapters_import_is_lazy():
    code = ("import sys, marsad.adapters as a; "
            "assert not any(m in sys.modules for m in ('pyulog','pymavlink','rclpy')), 'eager import'; "
            "assert 'write_ulog' in a.__all__; a.write_ulog; "
            "print('ok')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


# ----------------------------------------------------------------------------- writer + pyulog
@pytest.fixture(scope="module")
def spoof_run():
    return generate("spoof_drift", 1, "dev")


def test_writer_output_is_valid_ulog_for_pyulog(tmp_path, spoof_run):
    p = tmp_path / "s.ulg"
    info = write_ulog(str(p), spoof_run)
    raw = p.read_bytes()
    assert raw[:7] == MAGIC and raw[7] == 1
    u = ULog(str(p))
    assert not u.file_corruption
    names = {d.name: len(d.data["timestamp"]) for d in u.data_list}
    assert names["sensor_gps"] == info["gps_rows"] == sum(s.gnss is not None for s in spoof_run.samples)
    assert names["vehicle_visual_odometry"] == info["ref_rows"]
    assert "satellite_info" in names
    assert "SIMULATED" in u.msg_info_dict["marsad_synthetic"]
    g = next(d for d in u.data_list if d.name == "sensor_gps").data
    assert g["lat"].dtype == np.int32 and abs(g["lat"][0] / 1e7 - spoof_run.samples[0].gnss.lat) < 1e-6


@pytest.mark.parametrize("kind", ["nominal", "spoof_drift", "jam_hard", "replay", "benign_obstruction"])
def test_roundtrip_matches_simulator_samples(tmp_path, kind):
    run = generate(kind, 1, "dev")
    p = tmp_path / "r.ulg"
    write_ulog(str(p), run)
    d = load_ulog(str(p))
    a, b = run.samples, d.samples
    assert len(a) == len(b)
    assert d.info.synthetic and d.info.reference_source == "px4:vehicle_visual_odometry"
    assert not d.info.reference_contaminated
    for x, y in zip(a, b):
        assert abs(x.t - y.t) < 1e-5
        assert (x.gnss is None) == (y.gnss is None) and (x.ref is None) == (y.ref is None)
        if x.gnss:
            gx, gy = x.gnss, y.gnss
            assert abs(gx.lat - gy.lat) < 1e-6 and abs(gx.lon - gy.lon) < 1e-6
            assert abs(gx.alt - gy.alt) < 1e-2
            assert abs(gx.ve - gy.ve) < 1e-5 and abs(gx.vn - gy.vn) < 1e-5
            assert abs(gx.cn0_mean - gy.cn0_mean) < 0.1 and abs(gx.cn0_std - gy.cn0_std) < 0.2
            assert abs(gx.agc - gy.agc) < 1e-3
            assert gx.n_sats == gy.n_sats and gx.fix_type == gy.fix_type
            assert abs((gx.t - gx.t_gnss) - (gy.t - gy.t_gnss + UTC_BASE)) < 1e-5     # clock offset preserved (shifted by the synthetic UTC base)
        if x.ref:
            assert abs(x.ref.ve - y.ref.ve) < 1e-5 and abs(x.ref.vn - y.ref.vn) < 1e-5
            assert abs(x.ref.sigma - y.ref.sigma) < 1e-5


@pytest.mark.parametrize("kind,seed", [("spoof_drift", 1), ("spoof_drift", 3), ("jam_hard", 2), ("replay", 2),
                                       ("spoof_jump", 1), ("nominal", 1), ("benign_multipath", 1)])
def test_engine_verdict_on_roundtrip_matches_original(tmp_path, kind, seed):
    """Same state sequence; transition times may move by a few seconds because uint8 SNR quantisation nudges
    marginal evidence (documented)."""
    run = generate(kind, seed, "dev")
    p = tmp_path / "v.ulg"
    write_ulog(str(p), run)
    rt = load_ulog(str(p)).samples
    ta, tb = transitions(run.samples, states(run.samples)), transitions(rt, states(rt))
    assert [s for _, s in ta][-1] == [s for _, s in tb][-1]
    # collapse flicker: compare the set of states visited and the first non-TRUSTED time
    assert {s for _, s in ta} == {s for _, s in tb}
    fa = next((t for t, s in ta if s != "TRUSTED"), None)
    fb = next((t for t, s in tb if s != "TRUSTED"), None)
    assert (fa is None) == (fb is None)
    if fa is not None:
        assert abs(fa - fb) < 5.0


def test_sat_snrs_hits_targets():
    for m, s, k in [(42.0, 3.0, 20), (30.5, 1.05, 20), (20.0, 0.6, 20), (44.2, 3.2, 8)]:
        v = sat_snrs(m, s, k)
        assert all(1 <= x <= 99 for x in v)
        assert abs(np.mean(v) - m) < 0.1 and abs(np.std(v) - s) < 0.15


def test_no_satellite_info_means_no_cn0_and_a_warning(tmp_path, spoof_run):
    p = tmp_path / "n.ulg"
    write_ulog(str(p), spoof_run, include_satellite_info=False)
    d = load_ulog(str(p))
    assert not d.info.has_cn0 and all(s.gnss.cn0_mean is None for s in d.samples if s.gnss)
    assert any("satellite_info" in w for w in d.info.warnings)


# --------------------------------------------------- hand-built logs: aliases, units, references
def build_ulog(path, topics, rows, info_kv=()):
    """topics: list[Topic]; rows: list[(topic_name, values_dict)] in file order."""
    out = bytearray(MAGIC + bytes([1]) + struct.pack("<Q", 0))
    out += _msg(b"B", bytes(40))
    for k, v in info_kv:
        out += _info(k, v)
    for tp in topics:
        out += _msg(b"F", tp.format_string.encode())
    ids = {}
    for i, tp in enumerate(topics):
        ids[tp.name] = (i, tp)
        out += _msg(b"A", struct.pack("<BH", 0, i) + tp.name.encode())
    for name, vals in rows:
        i, tp = ids[name]
        out += _msg(b"D", struct.pack("<H", i) + tp.pack(vals))
    open(path, "wb").write(out)


def straight_rows(n=200, rate=10.0, lat_scale=1e7):
    """North-moving vehicle at 5 m/s, lat as given scale."""
    rows = []
    for i in range(n):
        t = i / rate
        lat = 24.0 + math.degrees(5.0 * t / 6378137.0)
        rows.append((int(t * 1e6), lat, 54.0))
    return rows


GPS_DEG = Topic("vehicle_gps_position", [          # legacy name, float degrees, float alt, no AGC
    ("uint64_t", "timestamp", 0), ("double", "lat", 0), ("double", "lon", 0), ("float", "alt", 0),
    ("float", "vel_n_m_s", 0), ("float", "vel_e_m_s", 0), ("uint16_t", "jamming_indicator", 0),
    ("uint8_t", "fix_type", 0), ("uint8_t", "satellites_used", 0)])


def test_unit_autodetect_degrees_and_legacy_topic_and_jamming_indicator_proxy(tmp_path):
    p = tmp_path / "deg.ulg"
    rows = [("vehicle_gps_position", dict(timestamp=ts, lat=la, lon=lo, alt=100.5, vel_n_m_s=5.0, vel_e_m_s=0.0,
                                          jamming_indicator=20 + (i > 100) * 60, fix_type=3, satellites_used=12))
            for i, (ts, la, lo) in enumerate(straight_rows())]
    build_ulog(p, [GPS_DEG], rows)
    d = load_ulog(str(p))
    assert d.info.gps_topic == "vehicle_gps_position"
    g = d.samples[0].gnss
    assert abs(g.lat - 24.0) < 1e-9 and abs(g.alt - 100.5) < 1e-6 and g.n_sats == 12
    assert "degrees" in d.info.mapping["gps.lat/lon units"]
    assert "PROXY" in d.info.mapping["gps.agc"]
    assert any("jamming_indicator" in w for w in d.info.warnings)
    # proxy normalised by its own max (<=255 -> /255) and rises when the indicator rises
    assert d.samples[150].gnss.agc > d.samples[10].gnss.agc + 0.1
    assert d.info.reference_source is None and any("NO velocity reference" in w for w in d.info.warnings)
    assert d.info.has_px4_flags is False


GPS_INT = Topic("sensor_gps", [
    ("uint64_t", "timestamp", 0), ("int32_t", "lat", 0), ("int32_t", "lon", 0), ("int32_t", "alt", 0),
    ("float", "vel_n_m_s", 0), ("float", "vel_e_m_s", 0), ("uint8_t", "fix_type", 0), ("uint8_t", "satellites_used", 0)])
ODOM = Topic("vehicle_visual_odometry", [
    ("uint64_t", "timestamp", 0), ("float", "position", 3), ("float", "q", 4), ("float", "velocity", 3),
    ("float", "velocity_variance", 3), ("uint8_t", "pose_frame", 0), ("uint8_t", "velocity_frame", 0)])
LPOS = Topic("vehicle_local_position", [
    ("uint64_t", "timestamp", 0), ("float", "vx", 0), ("float", "vy", 0), ("bool", "v_xy_valid", 0)])
FLOWVEL = Topic("vehicle_optical_flow_vel", [
    ("uint64_t", "timestamp", 0), ("float", "vel_body", 2), ("float", "vel_ne", 2)])


def gps_rows_int(n=200):
    return [("sensor_gps", dict(timestamp=ts, lat=int(round(la * 1e7)), lon=int(round(lo * 1e7)), alt=50000,
                                vel_n_m_s=5.0, vel_e_m_s=0.0, fix_type=3, satellites_used=10))
            for ts, la, lo in straight_rows(n)]


def odom_row(ts, vn, ve, frame=1, q=(1, 0, 0, 0), pos=(math.nan, math.nan, 0), pose_frame=1):
    return ("vehicle_visual_odometry", dict(timestamp=ts, position=list(pos), q=list(q), velocity=[vn, ve, 0.0],
                                            velocity_variance=[0.04] * 3, pose_frame=pose_frame, velocity_frame=frame))


def test_reference_priority_prefers_independent_over_ekf(tmp_path):
    p = tmp_path / "prio.ulg"
    rows = gps_rows_int()
    rows += [odom_row(ts, 5.0, 0.0) for ts, _, _ in straight_rows()]
    rows += [("vehicle_local_position", dict(timestamp=ts, vx=5.0, vy=0.0, v_xy_valid=True)) for ts, _, _ in straight_rows()]
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, ODOM, LPOS], rows)
    with warnings.catch_warnings():
        warnings.simplefilter("error")                     # no contamination warning must be raised
        d = load_ulog(str(p))
    assert d.info.reference_topic == "vehicle_visual_odometry" and not d.info.reference_contaminated
    assert d.samples[5].ref.sigma == pytest.approx(0.2, rel=1e-4)


def test_contaminated_fallback_is_flagged_loudly(tmp_path):
    p = tmp_path / "ekf.ulg"
    rows = gps_rows_int() + [("vehicle_local_position", dict(timestamp=ts, vx=5.0, vy=1.0, v_xy_valid=True))
                             for ts, _, _ in straight_rows()]
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, LPOS], rows)
    with pytest.warns(ContaminatedReferenceWarning):
        samples = list(read_ulog_samples(str(p)))
    info = inspect_ulog(str(p))
    assert info.reference_contaminated and "CONTAMINATED" in info.reference_source
    assert info.warnings[0].startswith("REFERENCE VELOCITY IS CONTAMINATED")
    r = next(s.ref for s in samples if s.ref)
    assert (r.vn, r.ve) == (5.0, 1.0) and "CONTAMINATED" in r.source
    # opt out
    d = load_ulog(str(p), allow_contaminated=False)
    assert d.info.reference_source is None and all(s.ref is None for s in d.samples)


def test_optical_flow_velocity_reference(tmp_path):
    p = tmp_path / "flow.ulg"
    rows = gps_rows_int() + [("vehicle_optical_flow_vel", dict(timestamp=ts, vel_body=[0, 0], vel_ne=[4.0, 3.0]))
                             for ts, _, _ in straight_rows()]
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, FLOWVEL], rows)
    d = load_ulog(str(p))
    r = next(s.ref for s in d.samples if s.ref)
    assert d.info.reference_topic == "vehicle_optical_flow_vel" and (r.vn, r.ve) == (4.0, 3.0)


def test_odometry_frd_velocity_is_rotated_by_yaw(tmp_path):
    p = tmp_path / "frd.ulg"
    yaw = math.pi / 2                                      # facing east
    q = (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))
    rows = gps_rows_int() + [odom_row(ts, 5.0, 0.0, frame=2, q=q) for ts, _, _ in straight_rows()]   # 5 m/s forward
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, ODOM], rows)
    r = next(s.ref for s in load_ulog(str(p)).samples if s.ref)
    assert r.vn == pytest.approx(0.0, abs=1e-5) and r.ve == pytest.approx(5.0, abs=1e-5)


def test_odometry_position_differencing_when_velocity_is_nan(tmp_path):
    p = tmp_path / "diff.ulg"
    rows = gps_rows_int()
    for ts, _, _ in straight_rows():
        t = ts / 1e6
        rows.append(odom_row(ts, math.nan, math.nan, pos=(5.0 * t, 2.0 * t, 0.0)))
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, ODOM], rows)
    d = load_ulog(str(p))
    r = next(s.ref for s in d.samples if s.ref)
    assert r.vn == pytest.approx(5.0, abs=1e-3) and r.ve == pytest.approx(2.0, abs=1e-3)
    assert "differenced" in d.info.mapping["ref.vehicle_visual_odometry"]


def test_gnss_and_reference_rows_merge_only_within_tolerance(tmp_path):
    p = tmp_path / "m.ulg"
    rows = gps_rows_int(20)
    rows += [odom_row(ts + 50_000, 5.0, 0.0) for ts, _, _ in straight_rows(20)]     # 50 ms later: separate
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, ODOM], rows)
    s = load_ulog(str(p)).samples
    assert len(s) == 40 and all((x.gnss is None) != (x.ref is None) for x in s)
    assert all(a.t <= b.t for a, b in zip(s, s[1:]))


def test_missing_required_gps_fields_raise_clear_error(tmp_path):
    p = tmp_path / "bad.ulg"
    t = Topic("sensor_gps", [("uint64_t", "timestamp", 0), ("float", "foo", 0)])
    build_ulog(p, [t], [("sensor_gps", dict(timestamp=1, foo=1.0))])
    with pytest.raises(ValueError, match="required field"):
        load_ulog(str(p))


def test_normalise_agc_heuristic():
    assert normalise_agc([0.2, 0.4])[0] == [0.2, 0.4]
    assert normalise_agc([50, 80])[0][1] == pytest.approx(0.8)
    assert normalise_agc([100, 200])[0][1] == pytest.approx(200 / 255)
    assert normalise_agc([2000, 4000])[0][1] == pytest.approx(4000 / 8191)
    assert normalise_agc([20000, 40000])[0][1] == pytest.approx(40000 / 65535)
    out, why = normalise_agc([float("nan"), 0.5])
    assert out[0] is None and "already" in why


# --------------------------------------------------------------------- PX4 flags comparison
def test_px4_flag_side_series_and_replay_comparison(tmp_path):
    run = generate("jam_hard", 2, "dev")
    t_a = run.attack_start
    p = tmp_path / "f.ulg"
    # TEST HOOK (not a receiver model): flag jamming only 30 s after the attack began
    write_ulog(str(p), run, flag_fn=lambda t: (3, 0) if t_a + 30 < t < t_a + 60 else (1, 1))
    d = load_ulog(str(p))
    assert d.info.has_px4_flags and len(d.px4_flags) == d.info.n_gnss
    assert d.px4_flags[0].jamming_state == 1 and d.px4_flags[0].spoof_flag is False
    res = replay_samples(d.samples, TrustEngine(preset("uav_multirotor")), d.px4_flags)
    assert res.px4_flags_available
    assert res.first_px4_flag_t >= t_a + 30
    assert res.first_nontrusted_t < res.first_px4_flag_t          # Marsad flagged first on this scenario
    assert res.marsad_flagged_px4_silent_s > 20
    assert res.transitions[0].flags == "jam=ok spoof=ok"


def test_replay_ignores_all_unknown_flags(tmp_path, spoof_run):
    p = tmp_path / "u.ulg"
    write_ulog(str(p), spoof_run)
    d = load_ulog(str(p))
    assert d.info.has_px4_flags and not replay_samples(d.samples, TrustEngine(), d.px4_flags).px4_flags_available


# ------------------------------------------------------------------------------------------ CLI
def test_cli_make_inspect_replay(tmp_path, capsys):
    p, js = str(tmp_path / "c.ulg"), str(tmp_path / "o.json")
    assert main(["make-log", "--kind", "spoof_drift", "--seed", "1", "--split", "dev", "--out", p]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out and "SIMULATED" in out
    assert main(["inspect", p]) == 0
    out = capsys.readouterr().out
    assert "px4:vehicle_visual_odometry" in out and "sensor_gps" in out and "SYNTHETIC" in out
    assert main(["replay", p, "--preset", "uav_multirotor", "--json", js]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out and "DENIED" in out
    data = json.load(open(js))
    assert data["result"]["transitions"][-1]["state"] == "DENIED" and data["info"]["synthetic"]


def test_cli_replay_warns_on_contaminated_reference(tmp_path, capsys):
    p = tmp_path / "ekf.ulg"
    rows = gps_rows_int() + [("vehicle_local_position", dict(timestamp=ts, vx=5.0, vy=0.0, v_xy_valid=True))
                             for ts, _, _ in straight_rows()]
    rows.sort(key=lambda r: r[1]["timestamp"])
    build_ulog(p, [GPS_INT, LPOS], rows)
    assert main(["replay", str(p)]) == 0
    out = capsys.readouterr().out
    assert "WARNING: REFERENCE VELOCITY IS CONTAMINATED" in out
    assert main(["replay", str(p), "--no-contaminated-ref"]) == 0
    assert "reference velocity: NONE" in capsys.readouterr().out


def test_existing_demo_still_works(capsys):
    assert main(["demo", "nominal", "--seed", "1"]) == 0
    assert "SIMULATED" in capsys.readouterr().out


def test_current_px4_sensor_gps_schema_roundtrip(tmp_path):
    """PX4 main now logs latitude_deg/longitude_deg (float64) and altitude_msl_m; the legacy layout used int 1e-7."""
    from marsad.adapters import write_ulog, read_ulog_samples
    from marsad.sim import generate
    run = generate("spoof_jump", 3, "dev", duration=120)
    p = str(tmp_path / "cur.ulg")
    write_ulog(p, run, schema="current")
    got = list(read_ulog_samples(p))
    g0 = next(s.gnss for s in got if s.gnss)
    s0 = next(s.gnss for s in run.samples if s.gnss)
    assert abs(g0.lat - s0.lat) < 1e-9 and abs(g0.lon - s0.lon) < 1e-9
