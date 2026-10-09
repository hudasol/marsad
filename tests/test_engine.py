import math
import pytest
from marsad import TrustEngine, preset, TrustState, NavAction, GnssFix, NavSample, RefMotion
from marsad.sim import generate


def run(kind, seed=1, split="dev", **kw):
    r = generate(kind, seed, split, **kw)
    eng = TrustEngine(preset("uav_multirotor"))
    reps = [eng.update(s) for s in r.samples]
    return r, reps


def first(r, reps, thr):
    for s, rep in zip(r.samples, reps):
        if s.t >= r.attack_start and rep.state != TrustState.TRUSTED and (thr == 1 or rep.state == TrustState.DENIED):
            return s.t - r.attack_start
    return None


def test_nominal_never_alarms():
    for seed in range(3):
        r, reps = run("nominal", seed)
        assert all(x.state == TrustState.TRUSTED for x in reps)


def test_jam_hard_denied_and_labelled_and_recovers():
    r, reps = run("jam_hard")
    assert first(r, reps, 2) < 8
    i = next(i for i, x in enumerate(reps) if x.state == TrustState.DENIED)
    assert reps[i + 10].dominant == "jamming"
    assert reps[i + 10].action == NavAction.FALLBACK_REFERENCE
    assert reps[-1].state == TrustState.TRUSTED


def test_spoof_jump_detected_immediately_and_nav_stays_near_truth():
    r, reps = run("spoof_jump")
    assert first(r, reps, 2) < 1.0
    errs = [math.hypot(x.nav_e - r.truth_e[i], x.nav_n - r.truth_n[i]) for i, x in enumerate(reps)
            if r.t[i] >= r.attack_start and x.nav_e is not None]
    assert max(errs) < 40.0          # raw GNSS error is hundreds of metres
    assert reps[-1].state == TrustState.DENIED   # persistent offset: must not silently re-trust


def test_carry_off_detected_before_large_error():
    r, reps = run("spoof_drift_stealth", split="dev")
    lat = first(r, reps, 1)
    assert lat is not None and lat < 90.0
    assert reps[-1].state == TrustState.DENIED


def test_obstruction_is_degraded_not_denied():
    r, reps = run("benign_obstruction")
    assert not any(x.state == TrustState.DENIED for x in reps)


def test_replay_detected():
    r, reps = run("replay")
    assert first(r, reps, 2) < 2.0


def test_works_without_reference_sensor():
    r, reps = run("spoof_drift_noref")
    assert first(r, reps, 1) is not None       # via the signal signature
    assert any(x.action == NavAction.HOLD_AND_ALERT for x in reps)


def test_report_serialises_with_evidence():
    r, reps = run("spoof_jump")
    d = reps[-1].to_dict()
    assert d["state"] == "DENIED" and d["evidence"] and "message" in d["evidence"][0]
    import json; json.dumps(d)


def test_no_gnss_at_all_does_not_crash():
    eng = TrustEngine()
    for i in range(50):
        rep = eng.update(NavSample(t=i * 0.2, gnss=None, ref=RefMotion(t=i * 0.2, ve=1.0, vn=0.0)))
    assert rep.state in (TrustState.DENIED, TrustState.TRUSTED, TrustState.DEGRADED)


def test_determinism():
    a = generate("spoof_drift", 7, "dev"); b = generate("spoof_drift", 7, "dev")
    assert a.obs_e.tolist() == b.obs_e.tolist() or all(
        (x == y) or (math.isnan(x) and math.isnan(y)) for x, y in zip(a.obs_e, b.obs_e))
    assert generate("spoof_drift", 8, "dev").params != a.params
