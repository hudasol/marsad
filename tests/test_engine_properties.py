"""Property tests for the engine input path: whatever finite or non finite numbers arrive, the engine must not
raise (except for a non finite sample time), must keep its probabilities valid, and must never report a
non finite position."""

from __future__ import annotations

import math

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from marsad import TrustEngine
from marsad.types import GnssFix, NavSample, RefMotion, TrustState

_FLOAT = st.floats(allow_nan=True, allow_infinity=True, width=64)
_OPT = st.one_of(st.none(), _FLOAT)
_TIME = st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)

_fix = st.builds(
    GnssFix,
    t=_TIME,
    lat=st.one_of(_FLOAT, st.floats(-95.0, 95.0)),
    lon=st.one_of(_FLOAT, st.floats(-185.0, 185.0)),
    alt=_FLOAT,
    ve=_OPT,
    vn=_OPT,
    cn0_mean=_OPT,
    cn0_std=_OPT,
    n_sats=st.one_of(st.none(), st.integers(0, 60)),
    agc=_OPT,
    hdop=_OPT,
    fix_type=st.integers(0, 6),
    t_gnss=_OPT,
)
_ref = st.builds(
    RefMotion,
    t=_TIME,
    ve=_FLOAT,
    vn=_FLOAT,
    sigma=_OPT,
    quality=_OPT,
)
_sample = st.builds(NavSample, t=_TIME, gnss=st.one_of(st.none(), _fix), ref=st.one_of(st.none(), _ref))

_SETTINGS = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _check(rep) -> None:
    assert rep.state in TrustState
    assert all(math.isfinite(v) and 0.0 <= v <= 1.0 + 1e-9 for v in rep.probs.values())
    assert abs(sum(rep.probs.values()) - 1.0) < 1e-6
    assert 0.0 <= rep.trust <= 1.0
    for v in (rep.nav_e, rep.nav_n, rep.nav_lat, rep.nav_lon):
        assert v is None or math.isfinite(v)


@_SETTINGS
@given(st.lists(_sample, min_size=1, max_size=40))
def test_arbitrary_samples_never_break_the_engine(samples):
    """Non finite values, out of range coordinates, missing fields, repeated and backwards times."""
    eng = TrustEngine()
    for s in samples:
        _check(eng.update(s))


@_SETTINGS
@given(st.lists(_sample, min_size=1, max_size=25), st.lists(_sample, min_size=1, max_size=25))
def test_reset_equals_a_fresh_engine(first, second):
    used = TrustEngine()
    for s in first:
        used.update(s)
    used.reset()
    fresh = TrustEngine()
    for s in second:
        a, b = used.update(s), fresh.update(s)
        assert (a.state, a.action, a.probs) == (b.state, b.action, b.probs)
    assert used.n_rejected == fresh.n_rejected


@_SETTINGS
@given(st.lists(_TIME, min_size=2, max_size=30))
def test_time_going_backwards_or_repeating_is_survived(times):
    eng = TrustEngine()
    for k, t in enumerate(times):
        fix = GnssFix(t=t, lat=24.45 + 1e-6 * k, lon=54.37, ve=0.0, vn=0.0)
        _check(eng.update(NavSample(t=t, gnss=fix, ref=RefMotion(t=t, ve=0.0, vn=0.0))))


@given(st.sampled_from([math.nan, math.inf, -math.inf]))
def test_non_finite_sample_time_is_rejected(bad):
    eng = TrustEngine()
    try:
        eng.update(NavSample(t=bad))
    except ValueError:
        return
    raise AssertionError("a non finite sample time must raise ValueError")
