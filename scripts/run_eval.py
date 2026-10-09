"""Reproduce every number in docs/EVALUATION.md. All results are SIMULATED.

    python scripts/run_eval.py            # full (several minutes)
    python scripts/run_eval.py --quick    # smoke
"""
import argparse, json, os, time
import numpy as np
from marsad.bench import run_benchmark, summarize
from marsad.bench.report import markdown
from marsad import TrustEngine, preset
from marsad.sim import generate, KINDS

ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); ap.add_argument("--workers", type=int, default=4)
a = ap.parse_args()
OUT = "docs/results"; os.makedirs(OUT, exist_ok=True)
N = 6 if a.quick else 30
t0 = time.time()

# 1. dev and held-out main tables --------------------------------------------------------------
for split, seeds in (("dev", range(N)), ("heldout", range(1000, 1000 + N))):
    res = run_benchmark(split, seeds, workers=a.workers)
    summ = summarize(res)
    json.dump({"split": split, "n_seeds": N, "summary": summ, "runs": res}, open(f"{OUT}/{split}.json", "w"), indent=1)
    open(f"{OUT}/{split}.md", "w").write(markdown(summ, f"{split} split, {N} seeds per scenario (SIMULATED)"))
    print(split, "done", round(time.time() - t0))

# 2. ablations (held-out) --------------------------------------------------------------------
ab_kinds = ["nominal", "benign_obstruction", "benign_multipath", "jam_hard", "jam_soft", "spoof_jump", "spoof_drift",
            "spoof_drift_stealth", "replay"]
rows = {}
for name, dis in (("full", ()), ("-signal", ("signal",)), ("-kinematic", ("kinematic",)),
                  ("-inertial", ("inertial",)), ("-timing", ("timing",))):
    res = run_benchmark("heldout", range(2000, 2000 + (4 if a.quick else 20)), kinds=ab_kinds, disable=dis, workers=a.workers)
    rows[name] = summarize(res)
    print("ablation", name, round(time.time() - t0))
json.dump(rows, open(f"{OUT}/ablation.json", "w"), indent=1)
L = ["### Ablation: detection rate / median latency (s) per scenario, held-out (SIMULATED)", "",
     "| scenario | " + " | ".join(rows) + " |", "|---|" + "---|" * len(rows)]
for k in ab_kinds:
    cells = []
    for name in rows:
        v = rows[name][k]
        if "alarm_rate_marsad" in v:
            lat = v["lat_alarm_med_marsad"]
            cells.append(f"{100*v['alarm_rate_marsad']:.0f}% / {'–' if lat is None else f'{lat:.1f}'}")
        else:
            cells.append(f"FA {100*v['alarm_frac_marsad']:.0f}% time, deny {100*v['runs_with_deny_marsad']:.0f}% runs")
    L.append(f"| `{k}` | " + " | ".join(cells) + " |")
open(f"{OUT}/ablation.md", "w").write("\n".join(L) + "\n")

# 3. detectability sweep: carry-off rate x reference bias -------------------------------------
rates = [0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0]
biases = [0.0, 0.04, 0.08]
sw = {}
for b in biases:
    for r in rates:
        res = run_benchmark("heldout", range(3000, 3000 + (4 if a.quick else 16)), kinds=["spoof_drift_stealth"],
                            ref_bias=b, overrides={"rate": r}, workers=a.workers)
        s = summarize(res)["spoof_drift_stealth"]
        sw[f"{b}|{r}"] = {"detect": s["alarm_rate_marsad"], "lat_med": s["lat_alarm_med_marsad"],
                          "err_max_med": s["err_max_med_marsad"], "raw_err_med": s["err_max_med_raw"]}
    print("sweep bias", b, round(time.time() - t0))
json.dump(sw, open(f"{OUT}/detectability.json", "w"), indent=1)
L = ["### Stealth carry-off (no power signature, velocity-consistent): detection rate / median latency (s) / median max nav error (m)",
     "", "Rows: reference-sensor velocity bias magnitude bound (m/s). Columns: drift rate (m/s). Held-out seeds, SIMULATED.", "",
     "| ref bias \\ drift | " + " | ".join(f"{r} m/s" for r in rates) + " |", "|---|" + "---|" * len(rates)]
for b in biases:
    cells = []
    for r in rates:
        v = sw[f"{b}|{r}"]
        lat = "–" if v["lat_med"] is None else f"{v['lat_med']:.0f}s"
        err = "–" if v["err_max_med"] is None else f"{v['err_max_med']:.0f}m"
        cells.append(f"{100*v['detect']:.0f}% / {lat} / {err}")
    L.append(f"| {b} | " + " | ".join(cells) + " |")
open(f"{OUT}/detectability.md", "w").write("\n".join(L) + "\n")

# 4. throughput ---------------------------------------------------------------------------------
run = generate("nominal", 1, "dev", duration=600)
eng = TrustEngine(preset("uav_multirotor")); t1 = time.perf_counter()
for s in run.samples: eng.update(s)
dt = time.perf_counter() - t1
tp = {"samples": len(run.samples), "seconds": dt, "us_per_sample": 1e6 * dt / len(run.samples)}
json.dump(tp, open(f"{OUT}/throughput.json", "w"), indent=1)
print("throughput", tp)
print("total", round(time.time() - t0), "s")
