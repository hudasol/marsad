"""Score the baselines on the same injected PX4 SIH attacks as scripts/sih_inject.py (label SIH + INJECTED).

    python scripts/sih_baselines.py sitl2.ulg --end 290 --t-attack 60 \
        --marsad docs/results/weighting_fix/sih_inject_long.json --out docs/results/baselines/sih_inject_long.json

Same log, same injection, same reference (simulator truth velocity), 4 headings per case. Marsad's rows are read
from the JSON that scripts/sih_inject.py wrote, so both come from identical attacks. Also prints how long each
baseline stays TRUSTED on the unmodified log (the false alarm side).
"""

import argparse
import json
import math
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sih_inject import groundtruth_ref, inject  # noqa: E402

from marsad.adapters.ulog import load_ulog  # noqa: E402
from marsad.bench.baselines import make_baselines  # noqa: E402
from marsad.types import TrustState  # noqa: E402

LABEL = {
    "marsad": "Marsad",
    "gate": "simplified gate",
    "ekf2_gate": "EKF2 style gate",
    "ekf2_gate_ref": "EKF2 style + reference",
    "window": "window consistency",
    "signal": "signal monitor",
    "stack": "stack of the three",
}


def first_alarm(samples, t_a, bs):
    out = {k: None for k in bs}
    n_bad = {k: 0 for k in bs}
    for s in samples:
        for k, b in bs.items():
            st, _ = b.update(s)
            if st != TrustState.TRUSTED:
                n_bad[k] += 1
                if out[k] is None and s.t >= t_a:
                    out[k] = s.t
    return out, n_bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--end", type=float, default=77.0)
    ap.add_argument("--t-attack", type=float, default=45.0)
    ap.add_argument("--marsad", default=None, help="JSON written by scripts/sih_inject.py for the same log and window")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = load_ulog(a.log, allow_contaminated=True, warn=False)
    samples = [s for s in d.samples if s.t <= a.end]
    samples, ref_src = groundtruth_ref(a.log, samples)
    t_a = a.t_attack
    names = list(make_baselines())
    _, clean = first_alarm(samples, 1e18, make_baselines())
    print(f"{a.log}: {len(samples)} samples to {a.end:.0f} s, attack from {t_a:.0f} s; reference {ref_src}")
    print("clean log, samples not TRUSTED: " + ", ".join(f"{k} {v}" for k, v in clean.items()) + "\n")
    marsad = {r["attack"]: r for r in json.load(open(a.marsad))["rows"]} if a.marsad else {}
    angles = [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]
    cases = [("drift", dict(rate=r, vel_consistent=vc)) for r in (0.1, 0.25, 0.5, 1.0, 2.0) for vc in (True, False)] + [
        ("jump", dict(mag=x)) for x in (50.0, 200.0, 1000.0)
    ]
    rows = []
    cols = (["marsad"] if marsad else []) + names
    print("| attack | " + " | ".join(LABEL[c] for c in cols) + " |")
    print("|---|" + "---|" * len(cols))
    for kind, p in cases:
        lats = {k: [] for k in names}
        for ang in angles:
            att = inject(samples, kind, t_a, angle=ang, **p)
            fa, _ = first_alarm(att, t_a, make_baselines())
            for k, v in fa.items():
                if v is not None:
                    lats[k].append(v - t_a)
        name = kind + " " + ", ".join(f"{k}={v}" for k, v in p.items())
        row = {"attack": name, "n": len(angles)}
        cells = []
        if marsad:
            m = marsad.get(name)
            row["marsad"] = {"detected": m["marsad_detected"], "median_s": m["marsad_median_s"]} if m else None
            cells.append(
                f"{m['marsad_detected']}/4 {m['marsad_median_s']:.1f} s"
                if m and m["marsad_median_s"] is not None
                else "0/4"
            )
        for k in names:
            L = lats[k]
            row[k] = {"detected": len(L), "median_s": float(np.median(L)) if L else None}
            cells.append(f"{len(L)}/4 {np.median(L):.1f} s" if L else "0/4")
        rows.append(row)
        print(f"| {name} | " + " | ".join(cells) + " |")
    if a.out:
        json.dump(
            {
                "log": a.log,
                "end_s": a.end,
                "t_attack_s": t_a,
                "reference": ref_src,
                "clean_not_trusted_samples": clean,
                "n_samples": len(samples),
                "rows": rows,
            },
            open(a.out, "w"),
            indent=1,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
