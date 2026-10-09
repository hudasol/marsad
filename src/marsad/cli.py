"""marsad command line: benchmark and demo runs. (More subcommands arrive with the adapters.)"""
from __future__ import annotations
import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="marsad", description="Position-trust layer for autonomous systems.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench", help="run the simulated benchmark")
    b.add_argument("--split", default="heldout", choices=["dev", "heldout"])
    b.add_argument("--seeds", type=int, default=30)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--out", default=None, help="write JSON results here")
    b.add_argument("--markdown", default=None, help="write markdown report here")
    d = sub.add_parser("demo", help="run one simulated scenario and print state transitions")
    d.add_argument("kind")
    d.add_argument("--seed", type=int, default=1)
    d.add_argument("--split", default="dev")
    a = ap.parse_args(argv)

    if a.cmd == "bench":
        from .bench import run_benchmark, summarize
        from .bench.report import markdown
        res = run_benchmark(a.split, range(a.seeds), workers=a.workers)
        summ = summarize(res)
        md = markdown(summ, f"Benchmark: {a.split} split, {a.seeds} seeds per scenario",
                      "All results are SIMULATED measurement-level scenarios; see docs/EVALUATION.md.")
        print(md)
        if a.out:
            json.dump({"split": a.split, "seeds": a.seeds, "summary": summ, "runs": res}, open(a.out, "w"), indent=1)
        if a.markdown:
            open(a.markdown, "w").write(md)
        return 0
    if a.cmd == "demo":
        from . import TrustEngine, preset
        from .sim import generate
        r = generate(a.kind, a.seed, a.split)
        eng = TrustEngine(preset("uav_multirotor"))
        prev = None
        print(f"scenario={a.kind} seed={a.seed} split={a.split} attack_start={r.attack_start} (SIMULATED)")
        for s in r.samples:
            rep = eng.update(s)
            if rep.state != prev:
                print(f"t={s.t:7.1f}s  {rep.state.value:9s} trust={rep.trust:.2f}  {rep.summary}")
                prev = rep.state
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
