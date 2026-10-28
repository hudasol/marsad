# Results

One folder per run, named for the change it evaluates. The newest engine is `prior_bound/` (v1.4.0); files at this
level are the v1.1.0 and v1.2.0 runs, kept because documents of those versions cite them.

| path | engine | contents | command |
|---|---|---|---|
| `prior_bound/` | v1.4.0 | SIMULATED dev, held out, ablation, detectability, throughput; SIH + INJECTED on `sitl1.ulg` and `sitl2.ulg` | `python scripts/run_eval.py --out docs/results/prior_bound`, `python scripts/sih_inject.py` |
| `prior_bound_run1/` | v1.4.0 candidate | first scoring run, before the anchor history fix; kept as a record | same |
| `baselines/` | v1.4.0 | baseline comparison on held out SIMULATED scenarios and on injected SIH attacks; clean replay | `python scripts/run_baselines.py`, `scripts/sih_baselines.py` |
| `weighting_fix/` | v1.3.0 | the same tables after the evidence weighting fix, plus REAL LOG replays and bias traces | `python scripts/run_eval.py --out docs/results/weighting_fix` |
| `bias_fix/` | v1.3.0 plus a reverted guard | runs of the rejected bias estimator guard | see `docs/research/PREREGISTRATION_BIAS.md` |
| `v1.0.0/` | v1.0.0 | the first held out tables | tag `v1.0.0` |
| top level `*.json`, `*.md`, `*.txt` | v1.1.0 and v1.2.0 | tables cited by the documents of those versions | check out the tag and run the same commands |

The `.ulg` logs are not stored here; see [../DATA.md](../DATA.md) for checksums and download steps.
