"""A drift that moves the receiver velocity too must not be learned away as reference bias.

Reproduces the SIH shape: 125 Hz reference, 8 Hz fixes, the attack starts 60 s in (before the bias estimator has
the 150 s it needs to tighten its bound), the spoofer shifts position and velocity together. See
docs/PREREGISTRATION_PRIOR_BOUND.md.
"""
import math
import random

from marsad import GnssFix, NavSample, RefMotion, TrustEngine, preset
from marsad.geo import LocalFrame
from marsad.types import TrustState


def _first_alarm(rate, t_att=60.0, t_end=290.0, seed=1):
    rnd = random.Random(seed)
    fr = LocalFrame(24.45, 54.38)
    eng = TrustEngine(preset("uav_multirotor"))
    t, dt, next_fix, e, n = 0.0, 0.008, 0.0, 0.0, 0.0
    while t < t_end:
        ang = (int(t // 40) % 4) * math.pi / 2                  # square track at 5 m/s
        vx, vy = 5 * math.cos(ang), 5 * math.sin(ang)
        e, n = e + vx * dt, n + vy * dt
        ref = RefMotion(t=t, ve=vx + rnd.gauss(0, 0.1), vn=vy + rnd.gauss(0, 0.1), sigma=0.1)
        g = None
        if t >= next_fix:
            next_fix += 0.125
            off = max(0.0, t - t_att) * rate * math.sqrt(0.5)
            lat, lon = fr.to_geo(e + rnd.gauss(0, 0.5) + off, n + rnd.gauss(0, 0.5) + off)
            dv = rate * math.sqrt(0.5) if t >= t_att else 0.0
            g = GnssFix(t=t, lat=lat, lon=lon, ve=vx + dv + rnd.gauss(0, 0.05), vn=vy + dv + rnd.gauss(0, 0.05),
                        cn0_mean=42 + rnd.gauss(0, 0.3), cn0_std=3.0, n_sats=14, agc=0.3, hdop=0.9, fix_type=3)
        rep = eng.update(NavSample(t=t, gnss=g, ref=ref))
        if t >= t_att and rep.state != TrustState.TRUSTED:
            return t - t_att
        t += dt
    return None


def test_velocity_consistent_drift_of_a_quarter_metre_per_second_is_detected():
    lat = _first_alarm(0.25)
    assert lat is not None and 60.0 < lat < 200.0


def test_clean_flight_stays_trusted():
    assert _first_alarm(0.0) is None


def test_drift_below_the_prior_bound_floor_is_not_claimed():
    assert _first_alarm(0.1) is None
