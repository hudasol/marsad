"""SIH flights with an imperfect reference (label: SIH + INJECTED). See PREREGISTRATION_SIH_REALISTIC_REF.md.

  python scripts/sih_realistic_ref.py --runs DIR --out docs/results/sih_realistic_ref

DIR holds the clean runs of scripts/sitl_ekf2_spoof.py (clean_h0.ulg ... with their .json). The reference is the
simulator truth velocity, decimated to 20 Hz, with one of the error models below applied. No RF is generated.
"""

import argparse
import json
import math
import random
import sys
import warnings
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_corpus import clopper_pearson  # noqa: E402
from real_inject import METHODS, run_methods  # noqa: E402
from sih_inject import groundtruth_ref, inject, offset_at  # noqa: E402

from marsad.adapters.ulog import load_ulog  # noqa: E402

REF_DT = 0.05
ONSET_AFTER_SQUARE_S = 60.0
WINDOW_S = 180.0
MODELS = {
    "exact": {"noise": 0.0},
    "bias_low": {"noise": 0.1, "bias": 0.03},
    "bias_bound": {"noise": 0.1, "bias": 0.096},
    "bias_high": {"noise": 0.1, "bias": 0.15},
    "bias_vhigh": {"noise": 0.1, "bias": 0.30},
    "walk": {"noise": 0.1, "walk": 0.002},
    "scale_vio": {"noise": 0.1, "scale": 0.0236},
    "scale_flow": {"noise": 0.1, "scale": 0.05},
    "realistic": {"noise": 0.15, "bias": 0.03, "walk": 0.002, "scale": 0.01, "dropouts": True, "latency": 0.1},
}
ATTACKS = [
    ("none", None, {}),
    ("drift_0.5_velcons", "drift", {"rate": 0.5, "vel_consistent": True}),
    ("drift_1.0_velcons", "drift", {"rate": 1.0, "vel_consistent": True}),
    ("drift_1.0_posonly", "drift", {"rate": 1.0, "vel_consistent": False}),
    ("jump_200", "jump", {"mag": 200.0}),
]


def apply_model(samples: list, model: dict, seed: int) -> list:
    rng = random.Random(seed)
    out = [deepcopy(s) for s in samples]
    ref_t = [s.t for s in out if s.ref is not None]
    ref_v = [(s.ref.ve, s.ref.vn) for s in out if s.ref is not None]

    def truth_at(t: float):
        import bisect

        i = max(1, min(bisect.bisect_left(ref_t, t), len(ref_t) - 1))
        a, b = ref_t[i - 1], ref_t[i]
        w = 0.0 if b == a else min(max((t - a) / (b - a), 0.0), 1.0)
        return (ref_v[i - 1][0] * (1 - w) + ref_v[i][0] * w, ref_v[i - 1][1] * (1 - w) + ref_v[i][1] * w)

    ang = rng.uniform(0, 2 * math.pi)
    bias = [model.get("bias", 0.0) * math.sin(ang), model.get("bias", 0.0) * math.cos(ang)]
    scale = 1.0 + model.get("scale", 0.0) * rng.choice([-1, 1])
    drop_until, next_drop = -1.0, ref_t[0] + rng.expovariate(1 / 60.0) if model.get("dropouts") else 1e18
    last_t, last_kept = None, -1e18
    for s in out:
        if s.ref is None:
            continue
        t = s.t
        if t - last_kept < REF_DT - 1e-9:
            s.ref = None
            continue
        last_kept = t
        dt = 0.0 if last_t is None else t - last_t
        last_t = t
        if model.get("walk"):
            bias[0] += rng.gauss(0, model["walk"] * math.sqrt(dt))
            bias[1] += rng.gauss(0, model["walk"] * math.sqrt(dt))
        if t >= next_drop:
            drop_until = t + rng.uniform(2.0, 10.0)
            next_drop = drop_until + rng.expovariate(1 / 60.0)
        if t < drop_until:
            s.ref = None
            continue
        ve, vn = truth_at(t - model.get("latency", 0.0))
        s.ref.ve = scale * ve + bias[0] + rng.gauss(0, model["noise"])
        s.ref.vn = scale * vn + bias[1] + rng.gauss(0, model["noise"])
        s.ref.sigma = max(model["noise"], 0.1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = []
    for meta_path in sorted(Path(a.runs).glob("clean_h*.json")):
        meta = json.load(open(meta_path))
        ulg = Path(a.runs) / f"{meta['name']}.ulg"
        sq = next(e["t_sim"] for e in meta["events"] if e["event"] == "square_start")
        t_on = sq + ONSET_AFTER_SQUARE_S
        heading = meta["heading"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = load_ulog(str(ulg), allow_contaminated=True, warn=False)
        base, _ = groundtruth_ref(str(ulg), data.samples)
        t1 = next(s.t for s in base if s.gnss is not None and s.gnss.fix_type >= 3)
        end = t_on + WINDOW_S
        base = [s for s in base if s.t <= end]
        for mname, model in MODELS.items():
            ms = apply_model(base, model, seed=int(heading) + 7)
            for aname, kind, p in ATTACKS:
                smp = ms if kind is None else inject(ms, kind, t_on, angle=math.radians(heading), ramp=10.0, **p)
                r = run_methods(smp, "Quadrotor", t_on, t1)
                row = {"flight": meta["name"], "heading": heading, "model": mname, "attack": aname}
                for m in METHODS:
                    f = r[m]["first"]
                    row[m] = {
                        "pre_alarm": r[m]["pre"],
                        "detected": f is not None,
                        "latency_s": None if f is None else f - t_on,
                        "offset_m": None
                        if f is None or kind is None
                        else offset_at(kind, f, t_on, p.get("rate", 0.0), 10.0, p.get("mag", 0.0)),
                    }
                rows.append(row)
            print(meta["name"], mname, flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump({"models": MODELS, "runs": rows}, open(out / "runs.json", "w"), indent=1)
    # summary: per model and attack, n, false alarm share (no attack), detection share
    lines = ["# SIH flights with an imperfect reference (SIH + INJECTED)", "", "n is 4 flights per cell.", ""]
    lines += [
        "| model | attack | method | false alarm or detection | 95% CI | median latency s |",
        "|---|---|---|---|---|---|",
    ]
    for mname in MODELS:
        for aname, kind, _ in ATTACKS:
            cell = [r for r in rows if r["model"] == mname and r["attack"] == aname]
            for m in METHODS:
                if kind is None:
                    k = sum(1 for r in cell if r[m]["pre_alarm"] or r[m]["detected"])
                else:
                    k = sum(1 for r in cell if r[m]["detected"])
                lo, hi = clopper_pearson(k, len(cell))
                lat = sorted(r[m]["latency_s"] for r in cell if r[m]["latency_s"] is not None)
                med = f"{lat[len(lat) // 2]:.1f}" if lat else "n/a"
                lines.append(f"| {mname} | {aname} | {m} | {k}/{len(cell)} | {lo:.2f} to {hi:.2f} | {med} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
