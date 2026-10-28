"""Score the baselines (marsad.bench.baselines) on the held out SIMULATED scenarios and put them next to Marsad.

    python scripts/run_baselines.py --out docs/results/baselines [--seeds 30] [--workers 4]

Seeds are 5000 to 5000+N-1 on the held out split, the same runs as docs/results/weighting_fix/heldout.json. Marsad's
per run results are read from that file (--marsad) instead of being recomputed; pass --rerun-marsad to recompute.
Detection = first sample at or after the scenario onset whose state is not TRUSTED. All results are SIMULATED.
"""
import argparse
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from marsad.bench.baselines import make_baselines
from marsad.sim import ATTACK_KINDS, KINDS, generate
from marsad.types import TrustState

NAMES = ["gate", "ekf2_gate", "ekf2_gate_ref", "window", "signal", "stack"]
LABEL = {"marsad": "Marsad", "gate": "simplified gate", "ekf2_gate": "EKF2 style gate", "ekf2_gate_ref": "EKF2 style gate + reference",
         "window": "window consistency", "signal": "signal monitor", "stack": "stack of the three"}


def one(args):
    kind, seed, split = args
    run = generate(kind, seed, split)
    bs = make_baselines()
    t_a, t_b = run.attack_start, run.attack_end
    ts = run.t
    out = {"kind": kind, "seed": seed}
    state = {k: np.zeros(len(ts), bool) for k in bs}
    err = {k: np.full(len(ts), np.nan) for k in bs}
    for i, s in enumerate(run.samples):
        for k, b in bs.items():
            st, pos = b.update(s)
            state[k][i] = st != TrustState.TRUSTED
            if pos is not None:
                err[k][i] = math.hypot(pos[0] - run.truth_e[i], pos[1] - run.truth_n[i])
    pre = ts < (t_a if t_a is not None else 1e18)
    for k in bs:
        out[k] = {"pre_alarm_frac": float(state[k][pre].mean()) if pre.any() else 0.0}
        if t_a is None:
            out[k]["alarm_frac"] = float(state[k].mean())
            continue
        end = t_b if t_b is not None else ts[-1] + 1
        act = (ts >= t_a) & (ts < end)
        post = ts >= t_a
        idx = np.where(post & state[k])[0]
        out[k]["latency"] = float(ts[idx[0]] - t_a) if len(idx) else None
        out[k]["alarm_frac"] = float(state[k][act].mean())
        sel = post & ~np.isnan(err[k])
        out[k]["err_max"] = float(np.nanmax(err[k][sel])) if sel.any() else None
    return out


def med(x):
    x = [v for v in x if v is not None]
    return float(np.median(x)) if x else None


def summarize(runs, marsad):
    rows = {}
    for kind in KINDS:
        rs = [r for r in runs if r["kind"] == kind]
        ms = [m for m in marsad if m["kind"] == kind]
        n = len(rs)
        row = {"n": n, "attack": kind in ATTACK_KINDS}
        cols = {"marsad": ms, **{k: rs for k in NAMES}}
        for k, src in cols.items():
            if k == "marsad":
                if kind in ATTACK_KINDS:
                    lat = [m["lat_alarm_marsad"] for m in src]
                    row[k] = {"rate": sum(v is not None for v in lat) / len(lat), "lat_med": med(lat),
                              "err_med": med([m["err_max_marsad"] for m in src]),
                              "pre_alarm": float(np.mean([m["pre_alarm_frac_marsad"] for m in src]))}
                else:
                    row[k] = {"alarm_frac": float(np.mean([m["alarm_frac_marsad"] for m in src])),
                              "runs_alarm": sum(m["alarm_frac_marsad"] > 0 for m in src) / len(src)}
            else:
                if kind in ATTACK_KINDS:
                    lat = [r[k]["latency"] for r in src]
                    row[k] = {"rate": sum(v is not None for v in lat) / len(lat), "lat_med": med(lat),
                              "err_med": med([r[k]["err_max"] for r in src]),
                              "pre_alarm": float(np.mean([r[k]["pre_alarm_frac"] for r in src]))}
                else:
                    row[k] = {"alarm_frac": float(np.mean([r[k]["alarm_frac"] for r in src])),
                              "runs_alarm": sum(r[k]["alarm_frac"] > 0 for r in src) / len(src)}
        rows[kind] = row
    return rows


def f(x, pct=False, nd=1):
    if x is None:
        return "-"
    return f"{100 * x:.0f}%" if pct else f"{x:.{nd}f}"


def markdown(rows, n):
    cols = ["marsad"] + NAMES
    L = [f"### Detection against baselines, held out split, {n} seeds per scenario (SIMULATED)", "",
         "Cell: share of runs detected / median latency in seconds. Detection is the first non TRUSTED sample at or after the onset.", "",
         "| scenario | " + " | ".join(LABEL[c] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for kind, r in rows.items():
        if not r["attack"]:
            continue
        L.append(f"| `{kind}` | " + " | ".join(f"{f(r[c]['rate'], pct=True)} / {f(r[c]['lat_med'])}" for c in cols) + " |")
    L += ["", "### Largest navigation error after onset, median over runs (m)", "",
          "Position each detector would hand to the vehicle (Marsad: its recommended position; empty while it advises holding).", "",
          "| scenario | " + " | ".join(LABEL[c] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for kind, r in rows.items():
        if r["attack"]:
            L.append(f"| `{kind}` | " + " | ".join(f(r[c]["err_med"], nd=0) for c in cols) + " |")
    L += ["", "### Alarm behaviour in benign conditions: share of runs with any alarm / mean share of time not TRUSTED", "",
          "| scenario | " + " | ".join(LABEL[c] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for kind, r in rows.items():
        if not r["attack"]:
            L.append(f"| `{kind}` | " + " | ".join(f"{f(r[c]['runs_alarm'], pct=True)} / {f(r[c]['alarm_frac'], pct=True)}" for c in cols) + " |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/baselines")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--split", default="heldout")
    ap.add_argument("--marsad", default="docs/results/weighting_fix/heldout.json")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    seeds = range(5000, 5000 + a.seeds)
    jobs = [(k, s, a.split) for k in KINDS for s in seeds]
    with ProcessPoolExecutor(a.workers) as ex:
        runs = list(ex.map(one, jobs, chunksize=4))
    marsad = [r for r in json.load(open(a.marsad))["runs"] if r["seed"] in set(seeds)]
    rows = summarize(runs, marsad)
    json.dump({"split": a.split, "seeds": [seeds[0], seeds[-1]], "summary": rows, "runs": runs},
              open(f"{a.out}/heldout_baselines.json", "w"), indent=1)
    md = markdown(rows, a.seeds)
    open(f"{a.out}/heldout_baselines.md", "w", encoding="utf-8").write(md)
    print(md)


if __name__ == "__main__":
    main()
