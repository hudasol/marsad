"""Exploratory: trace the drift z score and the reference bias estimate during one injected SIH drift.

usage: python scripts/bias_trace.py sitl2.ulg [--end 290] [--t-attack 60] [--rate 0.25] [--every 20]

Feeds the log as scripts/sih_inject.py does (simulator truth velocity as reference), injects a northward drift in
both velocity modes and prints, every --every seconds of GNSS time, the state, the largest drift z score, the
estimated reference velocity bias (east, north), the seconds of clean learning behind that estimate and
P(nominal). Written after the weighting fix run to explain a miss; post hoc, not preregistered.
Label: SIH + INJECTED. No RF is generated.
"""

import argparse
import importlib.util
import pathlib
import sys
import warnings

from marsad import TrustEngine, preset
from marsad.adapters.ulog import load_ulog

_p = pathlib.Path(__file__).resolve().parent / "sih_inject.py"
_spec = importlib.util.spec_from_file_location("sih_inject", _p)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--end", type=float, default=290.0)
    ap.add_argument("--t-attack", type=float, default=60.0)
    ap.add_argument("--rate", type=float, default=0.25)
    ap.add_argument("--every", type=float, default=20.0)
    a = ap.parse_args(argv)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = load_ulog(a.log, allow_contaminated=True, warn=False)
    full, _ = S.groundtruth_ref(a.log, [s for s in d.samples if s.t <= a.end])
    n_fix = sum(s.gnss is not None for s in full)
    n_fix_ref = sum(s.gnss is not None and s.ref is not None for s in full)
    print(f"{a.log}: to {a.end:.0f}s, northward drift {a.rate} m/s from {a.t_attack:.0f}s")
    print(
        f"GNSS fixes {n_fix}, of which carry a reference sample {n_fix_ref} (the bias estimator learns only on those)"
    )
    for vc in (True, False):
        print(f"\nvelocity consistent: {vc}")
        print(f"  {'t(s)':>6} {'state':8} {'drift z':>7} {'bias e':>7} {'bias n':>7} {'bias s':>6} {'P(nominal)':>10}")
        eng, nxt = TrustEngine(preset("uav_multirotor")), a.t_attack - 5.0
        for s in S.inject(full, "drift", a.t_attack, rate=a.rate, vel_consistent=vc, angle=0.0):
            r = eng.update(s)
            if s.gnss is not None and s.t >= nxt:
                nxt += a.every
                print(
                    f"  {s.t:6.1f} {r.state.value:8} {eng.inertial.last_z:7.2f} {eng.bias[0]:+7.3f} "
                    f"{eng.bias[1]:+7.3f} {eng.bias_s:6.1f} {eng.p_nom:10.3f}"
                )
    print("\nLabel: SIH + INJECTED. Exploratory (post hoc), not preregistered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
