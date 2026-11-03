import math

import numpy as np
import pytest

from marsad.sim import generate
from marsad.sim.literature import LIT_KINDS, LIT_TRUTH, generate_literature


@pytest.mark.parametrize("kind", LIT_KINDS)
def test_deterministic_and_attack_present(kind):
    a = generate_literature(kind, 3, duration=420.0)
    b = generate_literature(kind, 3, duration=420.0)
    assert a.attack_start == b.attack_start and a.params == b.params
    assert a.attack_start is not None and 150.0 <= a.attack_start <= 260.0
    assert LIT_TRUTH[kind]
    base = generate("nominal", 3, "dev", duration=420.0)
    # before the onset the run equals the clean world
    pre = [i for i, t in enumerate(a.t) if t < a.attack_start - 1.0]
    for i in pre[::50]:
        ga, gb = a.samples[i].gnss, base.samples[i].gnss
        assert (ga is None) == (gb is None)
        if ga is not None:
            assert (ga.lat, ga.lon, ga.cn0_mean) == (gb.lat, gb.lon, gb.cn0_mean)


def test_position_offsets_match_parameters():
    r = generate_literature("lit_switch", 5, duration=420.0)
    base = generate("nominal", 5, "dev", duration=420.0)
    i = int(np.searchsorted(r.t, r.attack_start + r.params["gap"] + 5.0))
    d = math.hypot(r.obs_e[i] - base.obs_e[i], r.obs_n[i] - base.obs_n[i])
    assert d == pytest.approx(r.params["offset_m"], abs=1e-3)


def test_jammer_lowers_cn0_and_raises_agc():
    r = generate_literature("lit_jam_chirp", 2, duration=600.0)
    base = generate("nominal", 2, "dev", duration=600.0)
    mid = r.attack_start + r.params["rise_s"] + 0.5 * r.params["hold_s"]
    i = int(np.searchsorted(r.t, mid))
    j = next(k for k in range(i, i + 50) if r.samples[k].gnss is not None)
    assert r.samples[j].gnss.cn0_mean < base.samples[j].gnss.cn0_mean - 0.5 * r.params["cn0_drop_db"]
    assert r.samples[j].gnss.agc > base.samples[j].gnss.agc


def test_equal_power_offset_reverts():
    r = generate_literature("lit_equal_power", 4, duration=600.0)
    base = generate("nominal", 4, "dev", duration=600.0)
    end = int(np.searchsorted(r.t, r.attack_end + 5.0))
    assert math.hypot(r.obs_e[end] - base.obs_e[end], r.obs_n[end] - base.obs_n[end]) < 1e-3


def test_unknown_kind():
    with pytest.raises(KeyError):
        generate_literature("nope", 0)
