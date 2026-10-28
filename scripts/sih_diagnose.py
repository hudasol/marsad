"""Exploratory diagnosis of the SIH + INJECTED drift misses (NOT preregistered, engine unchanged).

usage: python scripts/sih_diagnose.py sitl1.ulg [--end 77] [--t-attack 45] [--out docs/results/sih_diagnose.json]

sih_inject.py feeds the engine every sample the ULog adapter produces. In a PX4 SIH log the reference
(groundtruth velocity) arrives at about 125 Hz and GNSS at about 8 Hz as separate samples, so the time step the
inertial detector multiplies its evidence by on a GNSS epoch is the gap to the previous reference sample
(about 0.008 s), not the gap to the previous GNSS fix (about 0.12 s). This script prints:

1. the sample structure of the log (counts and median gaps);
2. the drift z-score and P(nominal) during one 2 m/s drift fed exactly as sih_inject.py feeds it;
3. the same drift cases fed at the GNSS epoch rate only (groundtruth velocity attached to each fix), which is
   the sample structure of the repository's own simulator.

Part 3 changes the input stream, not the engine. It is a post hoc check of one explanation for the miss and is
labelled exploratory. Label for every number: SIH + INJECTED. No RF is generated.
"""

import argparse
import importlib.util
import json
import math
import pathlib
import sys
import warnings
from copy import deepcopy

import numpy as np

from marsad import TrustEngine, preset
from marsad.adapters.ulog import load_ulog
from marsad.types import RefMotion, TrustState

_p = pathlib.Path(__file__).resolve().parent / "sih_inject.py"
_spec = importlib.util.spec_from_file_location("sih_inject", _p)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

ANGLES = [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]


def gnss_epochs(path, samples, sigma=0.1):
    """One sample per GNSS fix, with simulator-truth velocity interpolated to the fix time as the reference."""
    from pyulog import ULog

    f = next(
        x for x in ULog(path, disable_str_exceptions=True).data_list if x.name == "vehicle_local_position_groundtruth"
    ).data
    t = f["timestamp"] / 1e6
    vn, ve = np.asarray(f["vx"], float), np.asarray(f["vy"], float)
    out = []
    for s in samples:
        if s.gnss is None:
            continue
        s = deepcopy(s)
        s.ref = RefMotion(
            t=s.t,
            ve=float(np.interp(s.t, t, ve)),
            vn=float(np.interp(s.t, t, vn)),
            sigma=sigma,
            source="sih_groundtruth",
            quality=1.0,
        )
        out.append(s)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--end", type=float, default=77.0)
    ap.add_argument("--t-attack", type=float, default=45.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    t_a = a.t_attack

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = load_ulog(a.log, allow_contaminated=True, warn=False)
    raw = [s for s in d.samples if s.t <= a.end]
    full, _ = S.groundtruth_ref(a.log, raw)

    ts = np.array([s.t for s in full])
    tg = np.array([s.t for s in full if s.gnss is not None])
    tr = np.array([s.t for s in full if s.ref is not None])
    struct = {
        "samples": len(ts),
        "gnss_samples": len(tg),
        "ref_samples": len(tr),
        "median_gap_all_s": float(np.median(np.diff(ts))),
        "median_gap_gnss_s": float(np.median(np.diff(tg))),
        "median_gap_ref_s": float(np.median(np.diff(tr))),
    }
    print(f"{a.log}: to {a.end:.0f}s, attack from {t_a:.0f}s")
    print("1. sample structure as fed by sih_inject.py")
    for k, v in struct.items():
        print(f"   {k:20s} {v:.3f}" if isinstance(v, float) else f"   {k:20s} {v}")

    print("\n2. drift 2.0 m/s, velocity consistent, heading north, fed as sih_inject.py feeds it")
    print(f"   {'t(s)':>6} {'state':8} {'drift z':>7} {'offset m':>8} {'P(nominal)':>10}")
    eng = TrustEngine(preset("uav_multirotor"))
    trace, nxt = [], t_a - 5.0
    for s in S.inject(full, "drift", t_a, rate=2.0, vel_consistent=True, angle=0.0):
        r = eng.update(s)
        if s.gnss is not None and s.t >= nxt:
            nxt = s.t + 4.0
            row = (
                round(s.t, 1),
                r.state.value,
                round(eng.inertial.last_z, 2),
                round(eng.inertial.last_mag, 1),
                round(eng.p_nom, 3),
            )
            trace.append(row)
            print(f"   {row[0]:6.1f} {row[1]:8} {row[2]:7.2f} {row[3]:8.1f} {row[4]:10.3f}")

    ep = gnss_epochs(a.log, raw)
    m, b = S.run(ep)
    clean = {
        "marsad": sum(st != TrustState.TRUSTED for _, st in m),
        "baseline": sum(st != TrustState.TRUSTED for _, st in b),
    }
    print(f"\n3. fed at the GNSS epoch rate only ({len(ep)} samples). Exploratory, not preregistered.")
    print(f"   clean (no attack): Marsad non-TRUSTED samples {clean['marsad']}, gate baseline {clean['baseline']}")
    print(f"   {'attack':36s} {'Marsad':>14s} {'baseline':>10s}")
    rows = []
    for rate in (0.5, 1.0, 2.0):
        for vc in (True, False):
            lat, latb = [], []
            for ang in ANGLES:
                mm, bb = S.run(S.inject(ep, "drift", t_a, rate=rate, vel_consistent=vc, angle=ang))
                x, y = S.first_alarm(mm, t_a), S.first_alarm(bb, t_a)
                if x is not None:
                    lat.append(x - t_a)
                if y is not None:
                    latb.append(y - t_a)
            name = f"drift rate={rate}, vel_consistent={vc}"
            fm = f"{len(lat)}/4 med {np.median(lat):.1f}s" if lat else "0/4"
            fb = f"{len(latb)}/4" if latb else "0/4"
            print(f"   {name:36s} {fm:>14s} {fb:>10s}")
            rows.append(
                {
                    "attack": name,
                    "marsad_detected": len(lat),
                    "marsad_median_s": float(np.median(lat)) if lat else None,
                    "baseline_detected": len(latb),
                    "n": len(ANGLES),
                }
            )
    print("\nLabel: SIH + INJECTED. Part 3 is exploratory (post hoc); it changes the input stream, not the engine.")
    if a.out:
        json.dump(
            {
                "log": a.log,
                "end_s": a.end,
                "t_attack_s": t_a,
                "sample_structure": struct,
                "trace_drift_2mps_north": trace,
                "epoch_rate_clean_non_trusted": clean,
                "epoch_rate_rows": rows,
                "label": "SIH + INJECTED, exploratory",
            },
            open(a.out, "w"),
            indent=1,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
