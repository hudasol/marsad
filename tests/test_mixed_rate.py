"""Evidence must accrue per second of GNSS time, whatever the reference sample rate.

A PX4 log delivers the reference at about 125 Hz and GNSS at about 8 Hz as separate samples. Evidence computed on
a GNSS fix used to be scaled by the gap to the previous sample of any kind (the reference interval), which diluted
it to the ratio of the two rates. These tests feed the same synthetic flight co-sampled and interleaved.
"""

import random

from marsad import GnssFix, NavSample, RefMotion, TrustEngine, TrustState, preset
from marsad.geo import LocalFrame

ORIGIN = (24.45, 54.38)
T_ATTACK = 60.0


def _truth(t):
    """Straight leg at about 5 m/s. Constant velocity keeps the replay detector out of the test: it needs
    manoeuvres to say anything, and a periodic weave would let it match a delayed copy of itself."""
    ve, vn = 5.0, 0.5
    return ve * t, vn * t, ve, vn


def _drift(t, rate, ramp=10.0):
    tau = max(t - T_ATTACK, 0.0)
    d = 0.5 * rate * tau * tau / ramp if tau < ramp else 0.5 * rate * ramp + rate * (tau - ramp)
    v = rate * min(tau / ramp, 1.0)
    return d, v


def flight(*, ref_hz, gnss_hz, interleaved, rate=2.0, duration=100.0, seed=3):
    """Samples of one flight. Interleaved: reference-only and GNSS-only samples at their own rates.
    Co-sampled: one sample per fix carrying both. A northward carry-off drift starts at T_ATTACK."""
    rng = random.Random(seed)
    fr = LocalFrame(*ORIGIN)

    def fix(t):
        e, n, ve, vn = _truth(t)
        d, v = _drift(t, rate)
        lat, lon = fr.to_geo(e + rng.gauss(0, 0.3), n + d + rng.gauss(0, 0.3))
        return GnssFix(
            t=t,
            lat=lat,
            lon=lon,
            alt=50.0,
            ve=ve + rng.gauss(0, 0.05),
            vn=vn + v + rng.gauss(0, 0.05),
            cn0_mean=42.0,
            cn0_std=3.0,
            n_sats=14,
            agc=0.3,
            fix_type=3,
            t_gnss=t - 2.0,
        )

    def ref(t):
        _, _, ve, vn = _truth(t)
        return RefMotion(t=t, ve=ve + rng.gauss(0, 0.05), vn=vn + rng.gauss(0, 0.05), sigma=0.1, source="test")

    out = []
    n_fix = int(duration * gnss_hz)
    if not interleaved:
        for k in range(n_fix):
            t = k / gnss_hz
            out.append(NavSample(t=t, gnss=fix(t), ref=ref(t)))
        return out
    n_ref = int(duration * ref_hz)
    fix_times = [k / gnss_hz + 0.003 for k in range(n_fix)]
    i = 0
    for k in range(n_ref):
        t = k / ref_hz
        while i < len(fix_times) and fix_times[i] < t:
            out.append(NavSample(t=fix_times[i], gnss=fix(fix_times[i])))
            i += 1
        out.append(NavSample(t=t, ref=ref(t)))
    return out


def first_alarm(samples):
    eng = TrustEngine(preset("uav_multirotor"))
    for s in samples:
        r = eng.update(s)
        if s.t >= T_ATTACK and r.state != TrustState.TRUSTED:
            return s.t - T_ATTACK
    return None


def test_interleaved_fast_reference_does_not_dilute_drift_evidence():
    """Fails on the old weighting: the drift evidence accrued at 5% of its rate and the 40 s attack was missed."""
    lat = first_alarm(flight(ref_hz=100.0, gnss_hz=5.0, interleaved=True))
    assert lat is not None and lat < 30.0


def test_latency_does_not_depend_on_reference_rate():
    co = first_alarm(flight(ref_hz=5.0, gnss_hz=5.0, interleaved=False))
    mixed = first_alarm(flight(ref_hz=100.0, gnss_hz=5.0, interleaved=True))
    assert co is not None and mixed is not None
    assert abs(co - mixed) < 3.0


def test_clean_interleaved_flight_stays_trusted():
    eng = TrustEngine(preset("uav_multirotor"))
    states = {eng.update(s).state for s in flight(ref_hz=100.0, gnss_hz=5.0, interleaved=True, rate=0.0)}
    assert states == {TrustState.TRUSTED}
