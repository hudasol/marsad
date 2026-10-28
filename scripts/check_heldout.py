"""Re run the held out SIMULATED benchmark and compare it with the committed results.

    python scripts/check_heldout.py [--results docs/results/prior_bound/heldout.json] [--workers 4]

Exits 1 on any difference in the per run figures, so a change to the engine or the simulator that moves a published
number has to come with new result files. Used by CI.
"""

import argparse
import json
import sys

from marsad.bench import run_benchmark


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="docs/results/prior_bound/heldout.json")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    ref = json.load(open(a.results))
    seeds = sorted({r["seed"] for r in ref["runs"]})
    new = run_benchmark("heldout", seeds, workers=a.workers)
    old = {(r["kind"], r["seed"]): r for r in ref["runs"]}
    diffs = []
    for r in new:
        o = old.get((r["kind"], r["seed"]))
        if o is None:
            diffs.append(f"{r['kind']} seed {r['seed']}: not in the committed file")
            continue
        for k, v in r.items():
            if isinstance(v, float) and isinstance(o.get(k), float):
                same = abs(v - o[k]) <= 1e-9 * max(1.0, abs(v))
            else:
                same = o.get(k) == v
            if not same:
                diffs.append(f"{r['kind']} seed {r['seed']} {k}: committed {o.get(k)!r}, now {v!r}")
    print(f"{len(new)} runs compared against {a.results}: {len(diffs)} differences")
    for d in diffs[:30]:
        print("  " + d)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
