"""Run Marsad and the baselines on a scenario family.

  python scripts/run_literature.py --family literature --seeds 0-29 --out docs/results/literature_dev
  python scripts/run_literature.py --family design --seeds 7000-7099 --final --out docs/results/sealed/design

Labels: SIMULATED (LITERATURE) for the literature family, SIMULATED for the design family; SEALED when the seeds are
7000 to 7099. Those seeds are refused without --final, and --final is refused once docs/results/sealed exists, so the
sealed split can be evaluated once.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from marsad import TrustEngine, preset
from marsad.bench.baselines import make_baselines
from marsad.sim import generate
from marsad.sim.literature import LIT_BENIGN, LIT_KINDS, LIT_TRUTH, generate_literature
from marsad.types import TrustState

SEALED = range(7000, 7100)
DESIGN_KINDS = [
    "nominal",
    "benign_obstruction",
    "benign_multipath",
    "jam_hard",
    "jam_soft",
    "spoof_jump",
    "spoof_jump_transient",
    "spoof_drift",
    "spoof_drift_stealth",
    "replay",
    "spoof_drift_noref",
    "spoof_drift_ref_outage",
]
METHODS = ("marsad", "gate", "ekf2_gate_ref", "window", "stack")


def parse_seeds(s: str) -> list:
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def evaluate(family: str, kind: str, seed: int) -> dict:
    if family == "literature":
        run = generate_literature(kind, seed) if kind in LIT_KINDS else generate(kind, seed, "dev")
    else:
        run = generate(kind, seed, "heldout")
    eng, bl = TrustEngine(preset("uav_multirotor")), make_baselines()
    t_a = run.attack_start
    attack = kind in LIT_KINDS or (family == "design" and kind in _attack_kinds())
    first = {m: None for m in METHODS}
    pre = dict.fromkeys(METHODS, False)
    denied_first = None
    err = []
    for i, s in enumerate(run.samples):
        rep = eng.update(s)
        st = {"marsad": rep.state}
        for k in ("gate", "ekf2_gate_ref", "window", "stack"):
            st[k], _ = bl[k].update(s)
        for m, v in st.items():
            if v == TrustState.TRUSTED:
                continue
            if t_a is None or s.t < t_a:
                pre[m] = True
            elif first[m] is None:
                first[m] = s.t
                if m == "marsad":
                    denied_first = v == TrustState.DENIED
        if t_a is not None and s.t >= t_a and rep.nav_e is not None and rep.action.value != "HOLD_AND_ALERT":
            err.append(math.hypot(rep.nav_e - run.truth_e[i], rep.nav_n - run.truth_n[i]))
    out = {"family": family, "kind": kind, "seed": seed, "attack": attack, "pre_alarm": pre}
    if attack and t_a is not None:
        out["latency_s"] = {m: (None if first[m] is None else first[m] - t_a) for m in METHODS}
        out["marsad_denied_at_first"] = denied_first
        out["marsad_nav_err_max_m"] = max(err) if err else None
        a = first["marsad"]
        if a is not None:
            j = int(np.searchsorted(run.t, a))
            j = min(j, len(run.t) - 1)
            if not math.isnan(run.obs_e[j]):
                out["raw_offset_at_alarm_m"] = math.hypot(run.obs_e[j] - run.truth_e[j], run.obs_n[j] - run.truth_n[j])
    else:
        out["any_alarm"] = {m: first[m] is not None or pre[m] for m in METHODS}
        # nominal and benign runs: first-family code stores no onset; use full-run alarm
        out["alarm_samples_marsad_frac"] = None
    return out


def _attack_kinds():
    from marsad.sim import ATTACK_KINDS

    return ATTACK_KINDS


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=["literature", "design"], required=True)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--final", action="store_true", help="required for the sealed seeds 7000 to 7099")
    ap.add_argument("--kinds", default=None)
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    touches = any(s in SEALED for s in seeds)
    if touches and not a.final:
        print("refused: seeds 7000 to 7099 are sealed; use --final (once, at the end of the release)", file=sys.stderr)
        return 2
    if a.final and Path("docs/results/sealed").exists() and not str(a.out).startswith("docs/results/sealed"):
        print("refused: docs/results/sealed already exists", file=sys.stderr)
        return 2
    if a.final and touches and Path(a.out).exists() and any(Path(a.out).iterdir()):
        print("refused: sealed output already exists; the sealed split is evaluated once", file=sys.stderr)
        return 2
    kinds = a.kinds.split(",") if a.kinds else (LIT_KINDS + LIT_BENIGN if a.family == "literature" else DESIGN_KINDS)
    rows = []
    for k in kinds:
        for s in seeds:
            rows.append(evaluate(a.family, k, s))
        print(k, "done", flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump(
        {"family": a.family, "seeds": seeds, "truth": LIT_TRUTH, "runs": rows}, open(out / "runs.json", "w"), indent=1
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
