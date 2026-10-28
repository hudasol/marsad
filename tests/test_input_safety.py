"""Bad input must never reach the local frame or leave a latched detector behind."""

import math

import pytest

from marsad import GnssFix, NavSample, RefMotion, TrustEngine, preset
from marsad.sim import generate

NAN, INF = float("nan"), float("inf")


def _fix(t, **kw):
    base = dict(t=t, lat=24.45, lon=54.38, ve=0.0, vn=0.0, cn0_mean=41.0, cn0_std=3.0, n_sats=13, agc=0.3)
    base.update(kw)
    return GnssFix(**base)


def _feed(engine, n, bad_at=None, bad=None, ref=True):
    out = None
    for i in range(n):
        t = float(i)
        g = _fix(t, **(bad if i == bad_at else {}))
        out = engine.update(NavSample(t=t, gnss=g, ref=RefMotion(t=t, ve=0.0, vn=0.0) if ref else None))
    return out


@pytest.mark.parametrize("bad", [dict(lat=NAN), dict(lon=NAN), dict(lat=INF), dict(lat=95.0), dict(lon=-200.0)])
def test_unusable_first_fix_does_not_poison_the_frame(bad):
    e = TrustEngine(preset("uav_multirotor"))
    r = _feed(e, 80, bad_at=0, bad=bad)
    assert e.n_rejected == 1
    assert math.isfinite(r.nav_lat) and math.isfinite(r.nav_lon)
    assert abs(r.nav_lat - 24.45) < 0.01


@pytest.mark.parametrize("bad", [dict(ve=NAN), dict(cn0_mean=INF), dict(agc=NAN), dict(alt=NAN)])
def test_non_finite_optional_fields_are_dropped_not_propagated(bad):
    e = TrustEngine(preset("uav_multirotor"))
    r = _feed(e, 80, bad_at=60, bad=bad)
    assert math.isfinite(r.trust) and math.isfinite(r.nav_lat)
    assert r.state.name == "TRUSTED"


def test_non_finite_reference_is_treated_as_a_gap():
    e = TrustEngine(preset("uav_multirotor"))
    for i in range(80):
        t = float(i)
        ref = RefMotion(t=t, ve=NAN if i == 50 else 0.0, vn=0.0)
        r = e.update(NavSample(t=t, gnss=_fix(t), ref=ref))
    assert e.n_rejected == 1 and math.isfinite(r.trust)


def test_non_finite_time_is_refused():
    e = TrustEngine(preset("uav_multirotor"))
    with pytest.raises(ValueError):
        e.update(NavSample(t=NAN, gnss=_fix(0.0)))


def test_reset_leaves_nothing_behind():
    """A reset engine must give the same reports as a new one on the same input."""
    a = generate("spoof_jump", 3, "dev")
    b = generate("jam_soft", 4, "dev")
    used = TrustEngine(preset("uav_multirotor"))
    for s in a.samples:
        used.update(s)
    used.reset()
    fresh = TrustEngine(preset("uav_multirotor"))
    for s in b.samples[:3000]:
        ru, rf = used.update(s), fresh.update(s)
        assert (ru.state, round(ru.trust, 9), ru.action) == (rf.state, round(rf.trust, 9), rf.action)
