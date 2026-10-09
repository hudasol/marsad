"""ROS 2 adapter tests with duck-typed stubs (no ROS runtime here: STUB-TESTED ONLY)."""
import math
from types import SimpleNamespace as NS

import pytest

from marsad import TrustEngine, TrustState, preset
from marsad.adapters import ros2
from marsad.adapters.ros2 import RosBridge, build_diagnostic, process_cn0, process_navsat, process_odom
from marsad.geo import LocalFrame
from marsad.types import NavAction, TrustReport


def stamp(t):
    return NS(sec=int(t), nanosec=int(round((t % 1) * 1e9)))


def navsat(t, lat=24.45, lon=54.37, status=0, cov=(4.0, 0, 0, 0, 4.0, 0, 0, 0, 9.0), ctype=2):
    return NS(header=NS(stamp=stamp(t)), latitude=lat, longitude=lon, altitude=10.0, status=NS(status=status),
              position_covariance=list(cov), position_covariance_type=ctype)


def odom(t, vx, vy, yaw=None, cov0=0.04):
    q = NS(x=0.0, y=0.0, z=0.0, w=1.0) if yaw is None else NS(x=0.0, y=0.0, z=math.sin(yaw / 2), w=math.cos(yaw / 2))
    return NS(header=NS(stamp=stamp(t)), pose=NS(pose=NS(orientation=q)),
              twist=NS(twist=NS(linear=NS(x=vx, y=vy, z=0.0)), covariance=[cov0] + [0.0] * 35))


def test_module_imports_without_ros():
    assert ros2.HAVE_ROS2 is False
    with pytest.raises(ImportError):
        ros2.MarsadNode()


def test_process_navsat_fields():
    f = process_navsat(navsat(12.5), vel=(1.0, 2.0), cn0=(41.0, 2.0))
    assert f.t == 12.5 and f.lat == 24.45 and f.fix_type == 3 and (f.ve, f.vn) == (1.0, 2.0) and f.cn0_mean == 41.0
    assert f.hdop == pytest.approx(math.sqrt(8.0) / 3.0) and f.n_sats is None
    assert process_navsat(navsat(1.0, status=-1)).fix_type == 1
    assert process_navsat(navsat(1.0, ctype=0)).hdop is None
    assert process_navsat(navsat(1.0, lat=float("nan"))) is None


def test_process_odom_frames_and_twist():
    r = process_odom(odom(3.0, 5.0, 0.0, yaw=math.pi / 2))                 # forward 5 m/s, facing north (ENU yaw 90)
    assert r.t == 3.0 and r.vn == pytest.approx(5.0) and r.ve == pytest.approx(0.0, abs=1e-9)
    assert r.sigma == pytest.approx(0.2)
    p = process_odom(odom(3.0, 5.0, 1.0, yaw=0.7), twist_frame="parent")
    assert (p.ve, p.vn) == (5.0, 1.0)
    tw = NS(header=NS(stamp=stamp(4.0)), twist=NS(linear=NS(x=2.0, y=3.0, z=0.0)))      # TwistStamped
    t = process_odom(tw)
    assert (t.ve, t.vn, t.t) == (2.0, 3.0, 4.0)
    assert process_odom(NS(header=NS(stamp=stamp(1.0)))) is None


def test_process_cn0_generic():
    assert process_cn0(NS(data=[40.0, 44.0, 0.0, 42.0]))[0] == pytest.approx(42.0)
    assert process_cn0(NS(cn0=[]))is None and process_cn0(NS(foo=1)) is None


def test_build_diagnostic_levels():
    for st, lvl in [(TrustState.TRUSTED, 0), (TrustState.DEGRADED, 1), (TrustState.DENIED, 2)]:
        rep = TrustReport(t=0, state=st, trust=0.3, probs={}, dominant="jamming", action=NavAction.USE_GNSS,
                          summary="s")
        d = build_diagnostic(rep)
        kv = {v.key: v.value for v in d.values}
        assert d.level == lvl and d.name == "marsad/gnss_trust" and kv["state"] == st.value and kv["trust"] == "0.3000"


def test_bridge_end_to_end_detects_jump_with_stubs():
    """Straight line then a 300 m position jump, with an odometry reference: engine must leave TRUSTED."""
    br = RosBridge(TrustEngine(preset("ground_robot")), clock=lambda: 0.0)
    fr = LocalFrame(24.45, 54.37)
    states = []
    for i in range(1200):                                    # 120 s at 10 Hz
        t = 100.0 + i * 0.1
        east = 2.0 * i * 0.1 + (300.0 if i > 800 else 0.0)
        lat, lon = fr.to_geo(east, 0.0)
        br.on_odom(odom(t, 2.0, 0.0, yaw=0.0))
        rep = br.on_navsat(navsat(t, lat, lon))
        states.append(rep.state)
    assert states[500] == TrustState.TRUSTED
    assert states[-1] != TrustState.TRUSTED
    out = RosBridge.outputs(br.last_report)
    assert set(out) == {"trust", "state", "diagnostic"} and 0.0 <= out["trust"] <= 1.0


def test_bridge_drops_out_of_order_and_flags_contaminated():
    br = RosBridge(clock=lambda: 0.0, ref_contaminated=True)
    assert br.warnings and "CONTAMINATED" in br.warnings[0]
    assert br.on_navsat(navsat(10.0)) is not None
    assert br.on_navsat(navsat(9.0)) is None and br.dropped_out_of_order == 1
    assert br.on_odom(odom(11.0, 1, 0)) is not None
    assert process_odom(odom(12.0, 1, 0), source="x").source == "x"
