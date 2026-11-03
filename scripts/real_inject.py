"""Attacks injected into real PX4 flights (label: REAL LOG + INJECTED). See PREREGISTRATION_REAL_INJECTED.md.

usage:
  python scripts/real_inject.py run --manifest M.csv --logs DIR --out docs/results/real_injected/flights [--limit N]
  python scripts/real_inject.py report --manifest M.csv --flights docs/results/real_injected/flights --out DIR

What is real: the flights. What is injected: a position (and for velocity consistent drift, velocity) offset added
to logged fixes. Arm "ekf" uses the logged EKF fused velocity as reference (an optimistic upper bound: it was
computed from the uninjected fixes). Arm "indep" uses an independent reference where the log has one.
"""

import argparse
import csv
import hashlib
import json
import random
import sys
import time
import warnings
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_corpus import FIXEDWING, clopper_pearson, mcnemar_exact  # noqa: E402
from sih_inject import inject, offset_at  # noqa: E402

from marsad import TrustEngine  # noqa: E402
from marsad.adapters.ulog import load_ulog  # noqa: E402
from marsad.bench.baselines import make_baselines  # noqa: E402
from marsad.config import preset  # noqa: E402
from marsad.types import TrustState  # noqa: E402

METHODS = ("marsad", "gate", "ekf2_gate_ref", "window", "stack")
ANGLES = (0.0, 90.0, 180.0, 270.0)
CASES = [("jump", {"mag": m}) for m in (50.0, 200.0, 1000.0)] + [
    ("drift", {"rate": r, "vel_consistent": vc}) for r in (0.25, 0.5, 1.0, 2.0) for vc in (True, False)
]
MIN_S = 300.0
CLEAN_START_S = 30.0
RAMP = 10.0


def case_name(kind: str, p: dict) -> str:
    if kind == "jump":
        return f"jump_{int(p['mag'])}"
    return f"drift_{p['rate']}_{'velcons' if p['vel_consistent'] else 'posonly'}"


def onset_for(log_id: str, name: str, ang: float, t0: float, t1: float) -> float:
    seed = int(hashlib.sha256(f"{log_id}|{name}|{ang}".encode()).hexdigest()[:12], 16)
    u = random.Random(seed).uniform(0.30, 0.60)
    return t0 + u * (t1 - t0)


def make_engine(vehicle: str) -> TrustEngine:
    return TrustEngine(preset("uav_fixedwing" if vehicle in FIXEDWING else "uav_multirotor"))


def run_methods(samples, vehicle: str, t_on: float, t_start: float) -> dict:
    """Replay one sample list. Returns per method: first alarm time at/after onset, pre onset alarm, state at alarm."""
    eng, bl = make_engine(vehicle), make_baselines()
    res = {m: {"first": None, "pre": False, "denied_at_first": None} for m in METHODS}
    for s in samples:
        r = eng.update(s)
        states = {"marsad": r.state}
        for k in ("gate", "ekf2_gate_ref", "window", "stack"):
            states[k], _ = bl[k].update(s)
        if s.t < t_start:
            continue
        for m, st in states.items():
            if st == TrustState.TRUSTED:
                continue
            if s.t < t_on:
                res[m]["pre"] = True
            elif res[m]["first"] is None:
                res[m]["first"] = s.t
                res[m]["denied_at_first"] = st == TrustState.DENIED
        if s.t >= t_on and all(res[m]["first"] is not None for m in METHODS):
            break
    return res


def process_flight(row: dict, path: str, ref_mode: str) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = load_ulog(path, allow_contaminated=(ref_mode == "ekf"), warn=False)
    info = data.info
    samples = data.samples
    t1 = next((s.t for s in samples if s.gnss is not None and s.gnss.fix_type >= 3), None)
    if t1 is None:
        return {"error": "no fix of type 3 or better"}
    tend = max(s.t for s in samples if s.gnss is not None)
    out = {
        "log_id": row["log_id"],
        "ref_mode": ref_mode,
        "reference_source": info.reference_source,
        "span_s": tend - t1,
        "cases": {},
    }
    if tend - t1 < MIN_S:
        out["excluded"] = "less than 300 s of fixes"
        return out
    if info.reference_source is None:
        out["excluded"] = "no reference for this arm"
        return out
    # clean start: uninjected replay, no alarm in the 30 s before the earliest possible onset
    t_min = t1 + 0.30 * (tend - t1)
    clean = run_methods(samples, row["vehicle_type"], t_min, t1)
    out["clean_pre_alarm"] = {m: clean[m]["pre"] for m in METHODS}
    start_ok = True
    eng = make_engine(row["vehicle_type"])
    for s in samples:
        r = eng.update(s)
        if s.t >= t1 and t_min - CLEAN_START_S <= s.t < t_min and r.state != TrustState.TRUSTED:
            start_ok = False
            break
    out["clean_start"] = start_ok
    if not start_ok:
        out["excluded"] = "Marsad not TRUSTED in the 30 s before the earliest onset"
        return out
    for kind, p in CASES:
        name = case_name(kind, p)
        per = []
        for ang in ANGLES:
            t_on = onset_for(row["log_id"], name, ang, t1, tend)
            att = inject(samples, kind, t_on, angle=ang * 3.141592653589793 / 180.0, ramp=RAMP, **p)
            r = run_methods(att, row["vehicle_type"], t_on, t1)
            rec = {"heading": ang, "onset": t_on}
            for m in METHODS:
                f = r[m]["first"]
                rec[m] = {
                    "detected": f is not None,
                    "latency_s": None if f is None else f - t_on,
                    "offset_m": None
                    if f is None
                    else offset_at(kind, f, t_on, p.get("rate", 0.0), RAMP, p.get("mag", 0.0)),
                    "denied": r[m]["denied_at_first"],
                    "pre_alarm": r[m]["pre"],
                }
            per.append(rec)
        out["cases"][name] = per
    return out


def cmd_run(a) -> int:
    rows = list(csv.DictReader(open(a.manifest, encoding="utf-8")))
    rows = [r for r in rows if r["design_subset"] != "true" and r["stratum"] == "main"]
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    done = 0
    for r in rows:
        modes = ["ekf"] + (["indep"] if r["independent_reference"] not in ("none", "") else [])
        for mode in modes:
            f = outdir / f"{r['log_id']}_{mode}.json"
            if f.exists():
                continue
            p = Path(a.logs) / f"{r['log_id']}.ulg"
            if not p.exists():
                continue
            if a.budget_s and time.time() - t_start > a.budget_s:
                print("wall clock budget reached", flush=True)
                return 0
            try:
                res = process_flight(r, str(p), mode)
            except Exception as e:
                res = {"log_id": r["log_id"], "ref_mode": mode, "error": f"{type(e).__name__}: {e}"}
            json.dump(res, open(f, "w"), indent=1)
            done += 1
            print(
                f"{r['log_id']} {mode} {res.get('excluded', res.get('error', 'ok'))} ({done}, {time.time() - t_start:.0f}s)",
                flush=True,
            )
            if a.limit and done >= a.limit:
                return 0
    return 0


# --------------------------------------------------------------------------------------------- report
BOOT = 10000
BOOT_SEED = 20261103


def _median(v: list) -> Optional[float]:
    v = sorted(v)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def _boot_ci(per_flight: list) -> Optional[list]:
    if len(per_flight) < 2:
        return None
    rng = random.Random(BOOT_SEED)
    n = len(per_flight)
    meds = sorted(_median([per_flight[rng.randrange(n)] for _ in range(n)]) for _ in range(BOOT))
    return [meds[int(0.025 * BOOT)], meds[int(0.975 * BOOT) - 1]]


def _flight_view(res: dict, case: str, m: str) -> Optional[dict]:
    recs = res["cases"][case]
    det = [r[m] for r in recs if r[m]["detected"]]
    return {
        "detected": len(det) >= 3,
        "n_detected_headings": len(det),
        "latency": _median([d["latency_s"] for d in det]),
        "offset": _median([d["offset_m"] for d in det]),
        "denied": sum(1 for d in det if d["denied"]),
        "n_det": len(det),
    }


def cmd_report(a) -> int:
    man = {r["log_id"]: r for r in csv.DictReader(open(a.manifest, encoding="utf-8"))}
    summary: dict = {"arms": {}}
    for mode in ("ekf", "indep"):
        files = sorted(Path(a.flights).glob(f"*_{mode}.json"))
        flights = [json.load(open(f)) for f in files]
        ok = [f for f in flights if "cases" in f and f["cases"] and not f.get("excluded")]
        excl: dict = {}
        for f in flights:
            k = f.get("excluded") or ("error: " + f["error"][:60] if "error" in f else None)
            if k:
                excl[k] = excl.get(k, 0) + 1
        arm: dict = {"n_flights_run": len(flights), "n_flights_scored": len(ok), "excluded": excl, "cases": {}}
        arm["clean_pre_alarm_flights"] = {m: sum(1 for f in ok if f["clean_pre_alarm"][m]) for m in METHODS}
        for kind, p in CASES:
            name = case_name(kind, p)
            row: dict = {}
            views = {m: [_flight_view(f, name, m) for f in ok] for m in METHODS}
            for m in METHODS:
                v = views[m]
                k = sum(1 for x in v if x["detected"])
                lat = [x["latency"] for x in v if x["detected"] and x["latency"] is not None]
                off = [x["offset"] for x in v if x["detected"] and x["offset"] is not None]
                nd = sum(x["n_det"] for x in v)
                row[m] = {
                    "detected": k,
                    "n": len(v),
                    "ci95": list(clopper_pearson(k, len(v))) if v else None,
                    "median_latency_s": _median(lat),
                    "latency_ci95": _boot_ci(lat),
                    "median_offset_m": _median(off),
                    "denied_share": (sum(x["denied"] for x in v) / nd) if nd else None,
                }
            for m in METHODS[1:]:
                b = sum(1 for x, y in zip(views["marsad"], views[m]) if x["detected"] and not y["detected"])
                c = sum(1 for x, y in zip(views["marsad"], views[m]) if y["detected"] and not x["detected"])
                row[m]["mcnemar"] = {"marsad_only": b, "baseline_only": c, "p": mcnemar_exact(b, c)}
            arm["cases"][name] = row
        hw: dict = {}
        for f in ok:
            r = man.get(f["log_id"], {})
            key = f"{r.get('hardware', '?')}|{r.get('release', '?')}"
            hw.setdefault(key, {"n": 0, "marsad_detect_fraction": []})
            hw[key]["n"] += 1
            hw[key]["marsad_detect_fraction"].append(
                sum(1 for c in f["cases"].values() for rec in c if rec["marsad"]["detected"])
                / max(sum(len(c) for c in f["cases"].values()), 1)
            )
        arm["by_hardware_release"] = {
            k: {"n": v["n"], "mean_detect": sum(v["marsad_detect_fraction"]) / v["n"]} for k, v in hw.items()
        }
        summary["arms"][mode] = arm
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(out / "summary.json", "w"), indent=1, sort_keys=True)
    lines = ["# Attacks injected into real flights (REAL LOG + INJECTED)", ""]
    for mode, arm in summary["arms"].items():
        lines += [
            f"## Arm {mode}: n flights run {arm['n_flights_run']}, scored {arm['n_flights_scored']}",
            "",
            f"Excluded: {json.dumps(arm['excluded'])}",
            "",
            "| case | method | detected | 95% CI | median latency s (95% CI) | median offset m | p vs Marsad |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, row in arm["cases"].items():
            for m in METHODS:
                d = row[m]
                ci = f"{d['ci95'][0]:.2f} to {d['ci95'][1]:.2f}" if d["ci95"] else "n/a"
                lc = d["latency_ci95"]
                lat = (
                    "n/a"
                    if d["median_latency_s"] is None
                    else f"{d['median_latency_s']:.1f}" + (f" ({lc[0]:.1f} to {lc[1]:.1f})" if lc else "")
                )
                off = "n/a" if d["median_offset_m"] is None else f"{d['median_offset_m']:.0f}"
                pv = f"{d[m]['mcnemar']['p']:.3g}" if False else (f"{d['mcnemar']['p']:.3g}" if "mcnemar" in d else "")
                lines.append(f"| {name} | {m} | {d['detected']}/{d['n']} | {ci} | {lat} | {off} | {pv} |")
        lines.append("")
    open(out / "summary.md", "w").write("\n".join(lines))
    print(f"wrote {out}/summary.json and summary.md")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--manifest", required=True)
    r.add_argument("--logs", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--budget-s", type=float, default=0)
    r.set_defaults(fn=cmd_run)
    q = sub.add_parser("report")
    q.add_argument("--manifest", required=True)
    q.add_argument("--flights", required=True)
    q.add_argument("--out", required=True)
    q.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
