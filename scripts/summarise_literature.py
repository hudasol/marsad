"""Summarise the output of run_literature.py: detection, false alarms, paired tests, latency medians.

python scripts/summarise_literature.py docs/results/literature_dev/runs.json
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_corpus import clopper_pearson, mcnemar_exact  # noqa: E402

METHODS = ["marsad", "gate", "ekf2_gate_ref", "window", "stack"]


def boot_median(xs, n=10000, seed=20261103):
    rng = random.Random(seed)
    meds = sorted(statistics.median(rng.choices(xs, k=len(xs))) for _ in range(n))
    return meds[int(0.025 * n)], meds[int(0.975 * n)]


def summarise(path: str) -> dict:
    d = json.load(open(path))
    kinds = sorted({r["kind"] for r in d["runs"]})
    out = {"family": d["family"], "seeds": [d["seeds"][0], d["seeds"][-1]], "n_seeds": len(d["seeds"]), "kinds": {}}
    for k in kinds:
        rs = [r for r in d["runs"] if r["kind"] == k]
        n = len(rs)
        row = {"n": n}
        if rs[0]["attack"]:
            row["pre_attack_false_alarm"] = {m: sum(r["pre_alarm"][m] for r in rs) for m in METHODS}
            det = {m: [r["latency_s"][m] is not None for r in rs] for m in METHODS}
            row["detected"] = {
                m: {"k": sum(det[m]), "n": n, "ci95": [round(x, 4) for x in clopper_pearson(sum(det[m]), n)]}
                for m in METHODS
            }
            row["median_latency_s"] = {}
            for m in METHODS:
                xs = [r["latency_s"][m] for r in rs if r["latency_s"][m] is not None]
                row["median_latency_s"][m] = (
                    None
                    if len(xs) < 3
                    else {
                        "median": round(statistics.median(xs), 2),
                        "ci95": [round(x, 2) for x in boot_median(xs)],
                        "n": len(xs),
                    }
                )
            row["mcnemar_vs_marsad"] = {}
            for m in METHODS[1:]:
                b = sum(1 for a, c in zip(det["marsad"], det[m]) if a and not c)
                c_ = sum(1 for a, c in zip(det["marsad"], det[m]) if c and not a)
                row["mcnemar_vs_marsad"][m] = {
                    "marsad_only": b,
                    "baseline_only": c_,
                    "p": round(mcnemar_exact(b, c_), 6),
                }
        else:
            row["false_alarm"] = {
                m: {
                    "k": sum(r["any_alarm"][m] for r in rs),
                    "n": n,
                    "ci95": [round(x, 4) for x in clopper_pearson(sum(r["any_alarm"][m] for r in rs), n)],
                }
                for m in METHODS
            }
        out["kinds"][k] = row
    return out


def to_md(s: dict) -> str:
    L = [f"# {s['family']} family, seeds {s['seeds'][0]} to {s['seeds'][1]}", ""]
    L += [
        "| kind | method | detected or false alarm | 95% interval | median latency s (95% interval) | pre attack false alarms |",
        "|---|---|---|---|---|---|",
    ]
    for k, r in s["kinds"].items():
        for m in METHODS:
            if "detected" in r:
                x = r["detected"][m]
                lat = r["median_latency_s"][m]
                lt = "n/a" if lat is None else f"{lat['median']} ({lat['ci95'][0]} to {lat['ci95'][1]})"
                pre = r["pre_attack_false_alarm"][m]
            else:
                x = r["false_alarm"][m]
                lt, pre = "n/a", "n/a"
            L.append(f"| {k} | {m} | {x['k']}/{x['n']} | {x['ci95'][0]} to {x['ci95'][1]} | {lt} | {pre} |")
    L += ["", "Paired exact McNemar tests against Marsad (detection):", ""]
    for k, r in s["kinds"].items():
        if "mcnemar_vs_marsad" in r:
            for m, v in r["mcnemar_vs_marsad"].items():
                L.append(f"* {k}, {m}: only Marsad {v['marsad_only']}, only {m} {v['baseline_only']}, p {v['p']}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    p = Path(sys.argv[1])
    s = summarise(str(p))
    (p.parent / "summary.json").write_text(json.dumps(s, indent=1))
    (p.parent / "summary.md").write_text(to_md(s))
    print(to_md(s))
