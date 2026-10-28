"""The baselines are comparison points, so they get their own behavioural tests."""
import math

import pytest

from marsad.bench.baselines import AnyOf, Ekf2Gate, SignalMonitor, WindowConsistency, make_baselines
from marsad.geo import LocalFrame
from marsad.sim import generate
from marsad.types import GnssFix, NavSample, RefMotion, TrustState

T = TrustState.TRUSTED


def _first_alarm(det, run):
    for s in run.samples:
        st, _ = det.update(s)
        if run.attack_start is not None and s.t >= run.attack_start and st != T:
            return s.t - run.attack_start
    return None


def _straight(seconds=200, rate=5.0, drift=0.0, t_drift=100.0, jump=0.0, t_jump=1e9, ref=True, n_sats=12):
    """Vehicle flying east at 5 m/s, 5 Hz fixes, noiseless: isolates the logic of each detector."""
    fr = LocalFrame(24.45, 54.38)
    out, e = [], 0.0
    for i in range(int(seconds * 5)):
        t = i * 0.2
        e = 5.0 * t
        off = max(0.0, t - t_drift) * drift + (jump if t >= t_jump else 0.0)
        lat, lon = fr.to_geo(e + off, 0.0)
        v = 5.0 + (drift if t >= t_drift else 0.0)          # spoofer shifts the receiver velocity consistently
        g = GnssFix(t=t, lat=lat, lon=lon, ve=v, vn=0.0, cn0_mean=42.0, n_sats=n_sats, agc=0.3, fix_type=3)
        out.append(NavSample(t=t, gnss=g, ref=RefMotion(t=t, ve=5.0, vn=0.0, sigma=0.15) if ref else None))
    return out


def _alarm_time(det, samples, after):
    for s in samples:
        st, _ = det.update(s)
        if s.t >= after and st != T:
            return s.t - after
    return None


@pytest.mark.parametrize("name", ["gate", "ekf2_gate", "ekf2_gate_ref", "window", "signal", "stack"])
def test_silent_on_clean_flight(name):
    det = make_baselines()[name]
    assert _alarm_time(det, _straight(), 0.0) is None


@pytest.mark.parametrize("name", ["gate", "ekf2_gate", "ekf2_gate_ref", "window", "stack"])
def test_every_position_check_catches_a_jump_at_once(name):
    det = make_baselines()[name]
    t = _alarm_time(det, _straight(jump=300.0, t_jump=100.0), 100.0)
    assert t is not None and t < 1.0


def test_autopilot_style_gate_absorbs_a_velocity_consistent_drift():
    """Receiver velocity moves with the position, so a filter that follows the receiver sees nothing."""
    s = _straight(drift=0.5)
    assert _alarm_time(Ekf2Gate(use_reference=False), s, 100.0) is None


def test_reference_makes_the_drift_visible_to_the_window_test():
    s = _straight(drift=0.5)
    t = _alarm_time(WindowConsistency(), s, 100.0)
    assert t is not None and 20.0 < t < 80.0


def test_ekf2_gate_resets_to_gnss_after_seven_seconds_of_rejection():
    """Documented EKF2 behaviour that lets a persistent offset win: after reset_timeout_max the fix is accepted again."""
    det = Ekf2Gate(use_reference=False)
    states = []
    for s in _straight(seconds=160, jump=300.0, t_jump=100.0):
        st, _ = det.update(s)
        if s.t >= 100.0:
            states.append((s.t, st))
    denied = [t for t, st in states if st != T]
    assert denied and max(denied) - min(denied) <= 7.5          # alarm ends with the reset
    assert states[-1][1] == T


def test_low_satellite_count_is_not_used_by_the_ekf2_gate():
    det = Ekf2Gate()
    t = _alarm_time(det, _straight(n_sats=4), 0.0)
    assert t is not None                                        # no usable fix => estimate becomes stale


def test_signal_monitor_sees_a_power_step_but_not_a_matched_power_spoof():
    samples = _straight()
    for s in samples:
        if s.t >= 100.0:
            s.gnss.agc = 0.6
    assert _alarm_time(SignalMonitor(), samples, 100.0) is not None
    assert _alarm_time(SignalMonitor(), _straight(drift=0.5), 100.0) is None


def test_any_of_is_the_union():
    s = _straight(drift=0.5)
    a = AnyOf(Ekf2Gate(use_reference=False), WindowConsistency())
    assert _alarm_time(a, s, 100.0) is not None


def test_nominal_simulated_flight_is_silent_for_all():
    run = generate("nominal", 3, "dev")
    for name, det in make_baselines().items():
        assert _first_alarm(det, run) is None, name
