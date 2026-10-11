import importlib.util
import pathlib

from marsad.geo import haversine
from marsad.sim import generate

_p = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sih_inject.py"
_spec = importlib.util.spec_from_file_location("sih_inject", _p)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)


def _pair(smp, att, t_min):
    i = next(i for i, s in enumerate(smp) if s.gnss and s.t > t_min)
    return smp[i].gnss, att[i].gnss


def test_jump_displacement_is_exact_and_input_untouched():
    smp = generate("nominal", 5, "dev", duration=60).samples
    before = [(s.gnss.lat, s.gnss.lon) for s in smp if s.gnss][:5]
    att = S.inject(smp, "jump", 30.0, mag=100.0, angle=0.7)
    g0, g1 = _pair(smp, att, 40)
    assert abs(haversine(g0.lat, g0.lon, g1.lat, g1.lon) - 100.0) < 0.5
    assert [(s.gnss.lat, s.gnss.lon) for s in smp if s.gnss][:5] == before
    g0, g1 = _pair(smp, att, 10)
    assert (g0.lat, g0.lon) == (g1.lat, g1.lon)          # nothing changes before t_attack


def test_drift_ramps_then_is_linear():
    assert S._drift_dist(0, 10, 1.0, 10) == 0
    assert abs(S._drift_dist(20, 10, 1.0, 10) - 5.0) < 1e-9
    assert abs(S._drift_dist(30, 10, 1.0, 10) - 25.0) < 1e-9


def test_clean_run_has_no_alarm():
    smp = generate("nominal", 11, "dev", duration=77).samples
    m, _ = S.run(smp)
    assert all(st.value == "TRUSTED" for _, st in m)
