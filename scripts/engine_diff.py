"""Same machine control: does a code change alter the simulated benchmark, and in which scenarios?

usage:
    python scripts/engine_diff.py --out new.json                        # benchmark summary with this checkout
    PYTHONPATH=<other checkout>/src python scripts/engine_diff.py --out old.json
    python scripts/engine_diff.py --compare old.json new.json           # per scenario: IDENTICAL or the changed metrics

Runs the held out split (seeds 5000+, as scripts/run_eval.py) and stores the summary per scenario. Comparing two
summaries made on the same machine separates engine changes from platform differences in floating point (the
published results were produced on another machine). Label: SIMULATED.
"""

import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--compare", nargs=2)
    ap.add_argument("--split", default="heldout")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    if a.compare:
        x, y = (json.load(open(p))["summary"] for p in a.compare)
        for k in x:
            if x[k] == y[k]:
                print(f"{k:24s} IDENTICAL")
            else:
                ch = {m: (x[k][m], y[k].get(m)) for m in x[k] if x[k][m] != y[k].get(m)}
                print(f"{k:24s} CHANGED " + ", ".join(f"{m}: {u} -> {v}" for m, (u, v) in ch.items()))
        return 0
    import marsad
    from marsad.bench import run_benchmark, summarize

    base = 5000 if a.split == "heldout" else 0
    res = run_benchmark(a.split, range(base, base + a.seeds), workers=a.workers)
    json.dump({"marsad": marsad.__version__, "split": a.split, "summary": summarize(res)}, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
