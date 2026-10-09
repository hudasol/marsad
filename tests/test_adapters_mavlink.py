"""MAVLink adapter tests, fully offline: real message bytes via pymavlink's encoder, parsed back."""
import io
import math
import struct
import warnings

import pytest

pytest.importorskip("pymavlink")
from marsad import TrustEngine, preset, TrustState
from marsad.adapters._common import ContaminatedReferenceWarning
from marsad.adapters.mavlink import (ALLOWED_OUT, MavlinkMapper, MavlinkReporter, MavlinkSource, cn0_from_gps_status,
                                     dialect_module, gnss_integrity_flag, has_gnss_integrity, named_values,
                                     read_tlog_samples, ref_from_odometry, sample_from_gps_raw_int, status_text)
from marsad.sim import generate
from marsad.types import GnssFix, NavSample, RefMotion

M = dialect_module("all")


def roundtrip(msg, sysid=1, compid=1):
    """Encode to wire bytes and parse them back with a fresh parser (as a receiver would)."""
    buf = io.BytesIO()
    mav = M.MAVLink(buf, srcSystem=sysid, srcComponent=compid)
    mav.send(msg)
    parser = M.MAVLink(None)
    out = parser.parse_buffer(buf.getvalue())
    assert out and len(out) == 1
    return out[0]


def gps_raw(lat=24.45, lon=54.37, alt=50.0, fix=3, eph=90, vel=1000, cog=9000, nsat=12, tu=0):
    return roundtrip(M.MAVLink_gps_raw_int_message(tu, fix, int(lat * 1e7), int(lon * 1e7), int(alt * 1000), eph,
                                                   200, vel, cog, nsat))


def gps_status(snr, used=None):
    n = len(snr)
    pad = lambda v, fill=0: list(v) + [fill] * (20 - len(v))      # noqa: E731
    return roundtrip(M.MAVLink_gps_status_message(n, pad(range(1, n + 1)), pad(used if used is not None else [1] * n),
                                                  pad([45] * n), pad([0] * n), pad(snr)))


def test_dialect_has_gnss_integrity_in_all_but_maybe_not_common():
    assert has_gnss_integrity("all")
    assert M.MAVLink_gnss_integrity_message.id == 441
    # graceful: common may or may not carry it; the helper must not raise
    assert isinstance(has_gnss_integrity("common"), bool)


def test_gps_raw_int_units_and_sentinels():
    f = sample_from_gps_raw_int(gps_raw(vel=1000, cog=9000, eph=90, nsat=12), t=5.0)
    assert f.t == 5.0 and f.lat == pytest.approx(24.45, abs=1e-7) and f.lon == pytest.approx(54.37, abs=1e-7)
    assert f.alt == pytest.approx(50.0) and f.fix_type == 3 and f.n_sats == 12 and f.hdop == pytest.approx(0.9)
    assert f.ve == pytest.approx(10.0, abs=1e-6) and f.vn == pytest.approx(0.0, abs=1e-6)     # 10 m/s heading 90 deg
    assert f.t_gnss is None                                                                      # boot-time, not epoch
    u = sample_from_gps_raw_int(gps_raw(vel=65535, cog=65535, eph=65535, nsat=255, tu=1_700_000_000_000_000), t=1.0)
    assert u.ve is None and u.vn is None and u.hdop is None and u.n_sats is None
    assert u.t_gnss == pytest.approx(1.7e9)


def test_gps_status_cn0_ignores_zero_snr():
    m, sd, used, trk = cn0_from_gps_status(gps_status([40, 44, 0, 42, 38], used=[1, 1, 0, 1, 0]))
    assert m == pytest.approx(41.0) and trk == 4 and used == 3 and sd > 0
    assert cn0_from_gps_status(gps_status([0, 0]))[0] is None


def gnss_integrity(jam, spoof):
    return roundtrip(M.MAVLink_gnss_integrity_message(0, 0, 0, jam, spoof, 0, 0, 0, 0, 0, 0, 0))


def test_gnss_integrity_becomes_side_series_not_samples():
    mp = MavlinkMapper()
    assert mp.feed(gnss_integrity(3, 1), t=10.0) == []
    assert mp.feed(gnss_integrity(1, 3), t=11.0) == []
    assert [(f.jamming_state, f.spoofing_state, f.jam_flag, f.spoof_flag) for f in mp.flags] == [
        (3, 1, True, False), (1, 3, False, True)]
    assert gnss_integrity_flag(gnss_integrity(2, 2), 3.0).jam_flag


def odometry(vx, vy, est, frame=1, q=(1, 0, 0, 0), sysid=1, compid=1):
    return roundtrip(M.MAVLink_odometry_message(0, 1, frame, 0, 0, 0, list(q), vx, vy, 0, 0, 0, 0, [math.nan] * 21,
                                                [0.04] + [0.0] * 20, 0, est, 100), sysid, compid)


def test_odometry_independence_follows_estimator_type():
    r, ind, label = ref_from_odometry(odometry(5.0, 1.0, M.MAV_ESTIMATOR_TYPE_VIO, frame=M.MAV_FRAME_LOCAL_NED), 2.0)
    assert ind and (r.vn, r.ve) == (5.0, pytest.approx(1.0)) and r.sigma == pytest.approx(0.2) and "VIO" in label
    for est in (M.MAV_ESTIMATOR_TYPE_AUTOPILOT, M.MAV_ESTIMATOR_TYPE_GPS_INS, M.MAV_ESTIMATOR_TYPE_UNKNOWN):
        assert ref_from_odometry(odometry(5.0, 1.0, est, frame=M.MAV_FRAME_LOCAL_NED), 2.0)[1] is False
    # frames: ENU swaps axes; FRD rotates by yaw (facing east: forward 5 -> east 5)
    enu = ref_from_odometry(odometry(3.0, 4.0, M.MAV_ESTIMATOR_TYPE_VIO, frame=M.MAV_FRAME_LOCAL_ENU), 0)[0]
    assert (enu.ve, enu.vn) == (pytest.approx(3.0), pytest.approx(4.0))
    yaw = math.pi / 2
    frd = ref_from_odometry(odometry(5.0, 0.0, M.MAV_ESTIMATOR_TYPE_VIO, frame=M.MAV_FRAME_LOCAL_FRD,
                                     q=(math.cos(yaw / 2), 0, 0, math.sin(yaw / 2))), 0)[0]
    assert frd.ve == pytest.approx(5.0, abs=1e-6) and frd.vn == pytest.approx(0.0, abs=1e-6)


def local_pos(vx, vy):
    return roundtrip(M.MAVLink_local_position_ned_message(0, 0, 0, 0, vx, vy, 0))


def test_reference_policy_independent_preferred_and_contaminated_flagged():
    mp = MavlinkMapper(warn=False)
    out = mp.feed(local_pos(5.0, 0.0), t=1.0)                       # only EKF data so far: used, but flagged
    assert out[0].ref.source.endswith("[EKF-FUSED,CONTAMINATED]") and mp.ref_contaminated
    assert mp.warnings and mp.warnings[0].startswith("REFERENCE VELOCITY IS CONTAMINATED")
    out = mp.feed(odometry(5.0, 0.0, M.MAV_ESTIMATOR_TYPE_VIO), t=2.0)   # independent appears
    assert not mp.ref_contaminated and "VIO" in out[0].ref.source
    assert mp.feed(local_pos(5.0, 0.0), t=3.0) == []                 # EKF never mixed in afterwards
    mp2 = MavlinkMapper(allow_contaminated=False, warn=False)
    assert mp2.feed(local_pos(5.0, 0.0), t=1.0) == [] and mp2.ref_source is None


def test_contaminated_reference_emits_python_warning():
    mp = MavlinkMapper()
    with pytest.warns(ContaminatedReferenceWarning):
        mp.feed(local_pos(1.0, 1.0), t=1.0)


def test_ref_ids_filter_for_odometry():
    mp = MavlinkMapper(ref_ids={(1, 197)})
    assert mp.feed(odometry(5, 0, M.MAV_ESTIMATOR_TYPE_VIO, sysid=1, compid=1), t=1.0) == []     # FC's own copy
    assert mp.feed(odometry(5, 0, M.MAV_ESTIMATOR_TYPE_VIO, sysid=1, compid=197), t=2.0)


def test_optical_flow_needs_yaw_and_quality():
    mp = MavlinkMapper()
    of = roundtrip(M.MAVLink_optical_flow_message(0, 0, 0, 0, 3.0, 4.0, 200, 1.0))
    assert mp.feed(of, t=1.0) == []                                  # no ATTITUDE yet
    mp.feed(roundtrip(M.MAVLink_attitude_message(0, 0, 0, math.pi / 2, 0, 0, 0)), t=1.1)      # yaw east
    out = mp.feed(of, t=1.2)
    assert out[0].ref.ve == pytest.approx(3.0) and out[0].ref.vn == pytest.approx(-4.0)
    low = roundtrip(M.MAVLink_optical_flow_message(0, 0, 0, 0, 3.0, 4.0, 10, 1.0))
    assert mp.feed(low, t=1.3) == []
    # OPTICAL_FLOW_RAD with range from the message
    rad = roundtrip(M.MAVLink_optical_flow_rad_message(0, 0, 100_000, 0.0, 0.1, 0.0, 0.0, 0.0, 0, 200, 0, 5.0))
    out = mp.feed(rad, t=1.4)           # vbx = 0.1/0.1*5 = 5 forward; yaw east -> east 5
    assert out[0].ref.ve == pytest.approx(5.0, abs=1e-5) and out[0].ref.vn == pytest.approx(0.0, abs=1e-5)


def test_mapper_attaches_cn0_and_time_is_monotonic():
    mp = MavlinkMapper()
    mp.feed(gps_status([40, 44, 42, 38]), t=1.0)
    s = mp.feed(gps_raw(), t=1.5)[0]
    assert s.gnss.cn0_mean == pytest.approx(41.0)
    s2 = mp.feed(gps_raw(), t=1.0)[0]                                # out-of-order stamp is clamped, never goes back
    assert s2.t == 1.5
    stale = mp.feed(gps_raw(), t=100.0)[0]
    assert stale.gnss.cn0_mean is None                               # older than max_cn0_age


# -------------------------------------------------------------------------------------- tlog
def write_tlog(path, items):
    """items: [(t_seconds, message)] -> .tlog (8-byte big-endian microsecond stamp + packet)."""
    with open(path, "wb") as fh:
        for t, msg in items:
            buf = io.BytesIO()
            msg.pack(M.MAVLink(buf, srcSystem=1, srcComponent=1))
            fh.write(struct.pack(">Q", int(t * 1e6)) + msg.get_msgbuf())


def sim_to_mavlink(run, with_ref=True):
    items = []
    base = 1_700_000_000.0
    for s in run.samples:
        g = s.gnss
        if g is not None:
            n = max(int(g.n_sats), 4)
            snr = [int(round(g.cn0_mean))] * n                       # flat SNR: only the mean survives
            items.append((base + s.t, M.MAVLink_gps_status_message(
                n, list(range(1, n + 1)) + [0] * (20 - n), [1] * n + [0] * (20 - n), [45] * n + [0] * (20 - n),
                [0] * 20, snr + [0] * (20 - n))))
            sp = math.hypot(g.ve, g.vn)
            cog = int(round((math.degrees(math.atan2(g.ve, g.vn)) % 360) * 100))
            items.append((base + s.t, M.MAVLink_gps_raw_int_message(
                0, g.fix_type, int(round(g.lat * 1e7)), int(round(g.lon * 1e7)), int(g.alt * 1000),
                int(g.hdop * 100), 200, int(round(sp * 100)), cog % 36000, int(g.n_sats))))
        if with_ref and s.ref is not None:
            items.append((base + s.t, M.MAVLink_odometry_message(
                0, M.MAV_FRAME_LOCAL_NED, M.MAV_FRAME_LOCAL_NED, 0, 0, 0, [1, 0, 0, 0], s.ref.vn, s.ref.ve, 0, 0, 0, 0,
                [math.nan] * 21, [s.ref.sigma ** 2] + [0] * 20, 0, M.MAV_ESTIMATOR_TYPE_VIO, 100)))
    return items


def test_tlog_roundtrip_reads_back_positions_and_reference(tmp_path):
    run = generate("nominal", 1, "dev")
    p = tmp_path / "n.tlog"
    write_tlog(str(p), sim_to_mavlink(run))
    samples = list(read_tlog_samples(str(p)))
    g_in = [s for s in run.samples if s.gnss]
    g_out = [s for s in samples if s.gnss]
    r_out = [s for s in samples if s.ref]
    assert len(g_out) == len(g_in) and len(r_out) == sum(1 for s in run.samples if s.ref)
    for a, b in zip(g_in, g_out):
        assert abs(a.gnss.lat - b.gnss.lat) < 1e-6 and abs(a.gnss.lon - b.gnss.lon) < 1e-6
        assert abs(a.gnss.ve - b.gnss.ve) < 0.02 and abs(a.gnss.vn - b.gnss.vn) < 0.02      # cm/s + cdeg quantisation
        assert abs(a.gnss.cn0_mean - b.gnss.cn0_mean) <= 0.5
        assert b.t == pytest.approx(a.t + 1_700_000_000.0, abs=1e-5)
    assert all("VIO" in s.ref.source for s in r_out)
    assert all(a.t <= b.t for a, b in zip(samples, samples[1:]))


def test_tlog_spoof_drift_is_detected_via_mavlink_source(tmp_path):
    run = generate("spoof_drift", 1, "dev")
    p = tmp_path / "sd.tlog"
    write_tlog(str(p), sim_to_mavlink(run))
    src = MavlinkSource(str(p), warn=False)
    eng = TrustEngine(preset("uav_multirotor"))
    last, first_bad = None, None
    for s in src.samples():
        last = eng.update(s)
        if first_bad is None and last.state != TrustState.TRUSTED:
            first_bad = s.t - 1_700_000_000.0
    assert last.state == TrustState.DENIED
    assert first_bad is not None and run.attack_start < first_bad < run.attack_start + 120
    assert src.mapper.ref_source and not src.mapper.ref_contaminated


def test_cli_replay_on_tlog(tmp_path, capsys):
    from marsad.cli import main
    run = generate("spoof_jump", 1, "dev")
    p = tmp_path / "j.tlog"
    items = sim_to_mavlink(run)
    items.append((1_700_000_000.0 + 300, M.MAVLink_gnss_integrity_message(0, 0, 0, 1, 3, 0, 0, 0, 0, 0, 0, 0)))
    write_tlog(str(p), items)
    assert main(["replay", str(p)]) == 0
    out = capsys.readouterr().out
    assert "MAVLink" in out and "DENIED" in out
    assert main(["inspect", str(p)]) == 0
    assert "GNSS_INTEGRITY samples: 1" in capsys.readouterr().out


# ----------------------------------------------------------------------------------- reporter
class Capture(io.BytesIO):
    pass


def make_report(t, state, trust, dominant="spoofing_drift"):
    from marsad.types import NavAction, TrustReport
    return TrustReport(t=t, state=state, trust=trust, probs={}, dominant=dominant, action=NavAction.USE_GNSS)


def parse_all(buf):
    return M.MAVLink(None).parse_buffer(buf.getvalue()) or []


def test_reporter_emits_only_advisory_message_types_and_respects_rate():
    buf = Capture()
    rep = MavlinkReporter(buf, rate_hz=2.0, heartbeat=True)
    seq = [(0.0, TrustState.TRUSTED, 0.99), (0.1, TrustState.TRUSTED, 0.99), (0.5, TrustState.TRUSTED, 0.97),
           (1.0, TrustState.DEGRADED, 0.4), (1.1, TrustState.DEGRADED, 0.4), (1.5, TrustState.DENIED, 0.05),
           (2.0, TrustState.DENIED, 0.03), (3.0, TrustState.TRUSTED, 0.95)]
    for t, st, tr in seq:
        rep.publish(make_report(t, st, tr))
    msgs = parse_all(buf)
    types = {m.get_type() for m in msgs}
    assert types <= ALLOWED_OUT == {"NAMED_VALUE_FLOAT", "STATUSTEXT", "HEARTBEAT"}
    assert set(rep.sent) <= ALLOWED_OUT
    nv = [m for m in msgs if m.get_type() == "NAMED_VALUE_FLOAT"]
    trust_t = [m.time_boot_ms for m in nv if m.name == "MSD_TRUST"]
    assert trust_t == [0, 500, 1000, 1500, 2000, 3000]              # <= 2 Hz by report time (0.1/1.1 suppressed)
    assert {m.name for m in nv} == {"MSD_TRUST", "MSD_STATE"}
    assert [m.value for m in nv if m.name == "MSD_STATE"] == [0, 0, 1, 2, 2, 0]
    st = [m for m in msgs if m.get_type() == "STATUSTEXT"]
    assert [(m.severity, m.text.split()[1]) for m in st] == [(4, "DEGRADED"), (2, "DENIED"), (5, "TRUSTED")]
    assert all(len(m.text) <= 50 for m in st)


def test_reporter_never_sends_commands_or_mode_changes():
    buf = Capture()
    rep = MavlinkReporter(buf)
    forbidden = [M.MAVLink_command_long_message(1, 1, M.MAV_CMD_DO_SET_MODE, 0, 1, 4, 0, 0, 0, 0, 0),
                 M.MAVLink_set_mode_message(1, 1, 4),
                 M.MAVLink_param_set_message(1, 1, b"EKF2_GPS_CTRL", 0.0, M.MAV_PARAM_TYPE_REAL32),
                 M.MAVLink_set_position_target_local_ned_message(0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 M.MAVLink_gps_input_message(*([0] * 19))]
    for m in forbidden:
        with pytest.raises(RuntimeError, match="advisory-only"):
            rep._send(m)
    assert buf.getvalue() == b"" and not rep.sent


def test_status_text_and_named_values_pure_functions():
    r = make_report(0, TrustState.DENIED, 0.02, dominant="environmental_degradation")
    sev, text = status_text(TrustState.TRUSTED, r)
    assert sev == 2 and len(text) <= 50 and text.startswith("MSD DENIED")
    assert status_text(TrustState.DENIED, r) is None and status_text(None, make_report(0, TrustState.TRUSTED, 1)) is None
    assert named_values(r) == [("MSD_TRUST", 0.02), ("MSD_STATE", 2.0)]
