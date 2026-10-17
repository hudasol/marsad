"""False alarm margin on clean logs: how close does the engine come to leaving TRUSTED?

usage: python scripts/clean_margin.py [sitl1.ulg:77] [sitl2.ulg:290] [flight1.ulg] [flight2.ulg]

For each log (optionally cut at LOG:END seconds) prints the share of time spent TRUSTED, the minimum P(nominal)
(DEGRADED starts below 0.5), the time spent with P(nominal) below 0.9, and the largest drift z score of the inertial
detector (evidence accrues above 2). SIH logs (those with a vehicle_local_position_groundtruth topic) use simulator
truth velocity as the reference, exactly as scripts/sih_inject.py does; other logs use the adapter's reference.
No attack is injected. To compare engine versions, run it with PYTHONPATH pointing at another checkout's src.
"""
import importlib.util
import pathlib
import sys
import warnings

import marsad
from marsad import TrustEngine, preset
from marsad.adapters.ulog import load_ulog
from marsad.detectors import Context
from marsad.types import TrustState

_p = pathlib.Path(__file__).resolve().parent / "sih_inject.py"
_spec = importlib.util.spec_from_file_location("sih_inject", _p)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)


def margin(path, end=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = load_ulog(path, allow_contaminated=True, warn=False)
    smp = [s for s in d.samples if end is None or s.t <= end]
    label = "REAL LOG"
    try:
        smp, _ = S.groundtruth_ref(path, smp)
        label = "SIH, no injection"
    except SystemExit:
        pass
    eng = TrustEngine(preset("uav_multirotor"))
    t_trusted = t_low = 0.0
    p_min, z_max, prev = 1.0, 0.0, None
    for s in smp:
        r = eng.update(s)
        if prev is not None:
            step = s.t - prev
            t_trusted += step if r.state == TrustState.TRUSTED else 0.0
            t_low += step if eng.p_nom < 0.9 else 0.0
        prev = s.t
        if not r.warmup:
            p_min = min(p_min, eng.p_nom)
        if s.gnss is not None:
            z_max = max(z_max, eng.inertial.last_z)
    span = smp[-1].t - smp[0].t
    return label, span, t_trusted, p_min, t_low, z_max


def main(argv=None):
    args = (argv if argv is not None else sys.argv[1:]) or ["sitl1.ulg:77", "sitl2.ulg:290", "flight1.ulg", "flight2.ulg"]
    per_fix = hasattr(Context(), "gnss_dt")
    print(f"engine: marsad {marsad.__version__}, per-fix evidence scaled by "
          + ("the time since the previous fix (weighting fix)" if per_fix else "the time since the previous sample"))
    print(f"{'log':16s} {'label':18s} {'span s':>7s} {'TRUSTED':>8s} {'min P(nominal)':>14s} "
          f"{'s with P<0.9':>12s} {'max drift z':>11s}")
    for a in args:
        path, _, end = a.partition(":")
        label, span, tt, pmin, tlow, zmax = margin(path, float(end) if end else None)
        print(f"{a:16s} {label:18s} {span:7.0f} {100 * tt / span:7.1f}% {pmin:14.3f} {tlow:12.1f} {zmax:11.2f}")
    print("\nMinimum P(nominal) excludes the warm-up period. No attack is present in any log.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
