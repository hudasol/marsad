# Known limits (v1.3.0)

This page states what Marsad still misses after the evidence weighting fix, why, and what that costs. Every number
carries one label and comes from a file in `docs/results/`. Nothing on this page changes the engine.

## What is missed

**Label: SIH + INJECTED** (PX4 SIH log `sitl2.ulg`, offset added to the logged GNSS fixes, 230 s attack window,
simulator truth velocity as the reference, 4 headings per case; `docs/results/weighting_fix/sih_inject_long.txt`).

| drift | velocity consistent (spoofer also shifts the GNSS velocity) | velocity not consistent (GNSS velocity honest) |
|---|---|---|
| 0.1 m/s | 0/4 | 0/4 |
| 0.25 m/s | **0/4** | 4/4, median 113.6 s, median offset 27.1 m |
| 0.5 m/s | 4/4, median 48.3 s, median offset 21.7 m | 4/4, median 42.5 s, median offset 18.8 m |

In the 32 s window of `sitl1.ulg` every drift of 0.5 m/s or slower is missed (0/4 in both modes,
`docs/results/weighting_fix/sih_inject.txt`); the window is too short for that rate, not only the method.

## Why (measured, exploratory)

Both traces were made after the results were seen and are not preregistered. Reproduce:
`python scripts/bias_trace.py sitl2.ulg` (0.25 m/s, `docs/results/weighting_fix/bias_trace_sitl2.txt`) and
`python scripts/bias_trace.py sitl2.ulg --rate 0.1` (`docs/results/weighting_fix/bias_trace_sitl2_0.1.txt`).

1. **The reference bias estimator absorbs a velocity consistent drift.** While the drift z score is below 1 and the
   state is TRUSTED, the engine learns the reference velocity bias as the mean of (reference velocity minus GNSS
   velocity). A spoofer that shifts the GNSS velocity together with the position makes that difference equal to
   the drift rate, so the estimator learns the drift as if it were sensor bias and subtracts it from the reference.
   * 0.25 m/s: the north bias estimate reached -0.087 m/s (34.8% of the drift) by 115 s; from then on the z score
     stayed above 1 and learning stopped. The remaining drift raised the z score to a peak of 1.80, below the evidence
     threshold of 2, and the state stayed TRUSTED.
   * 0.1 m/s: the z score never reached 1, so learning never stopped. The estimate reached -0.079 m/s (79% of the
     drift) by 275 s and the z score peaked at 0.55.
   * With honest GNSS velocity the estimate stays near zero (-0.000 m/s at 0.25 m/s, -0.001 m/s at 0.1 m/s), which is
     why the same 0.25 m/s drift is caught in that mode.
2. **The bound is wide for the first 150 s of learning.** The tighter bias bound (0.03 m/s instead of 0.08 m/s) is
   used only after 150 s of clean learning, and the estimator learns only on fixes that share an input sample with a
   reference sample: 1,145 of 2,305 fixes in `sitl2.ulg`. Learning reached 43.6 s and 47.0 s at 0.25 m/s and at most
   135.7 s by 275 s at 0.1 m/s, below 150 s in every case, so the wide bound applied throughout. With honest
   velocity at 0.1 m/s the z score peaked at 1.06: the drift is too small against the wide bound within 230 s.

## The exact condition

A drift is missed on this log when **both** hold:

* the spoofer shifts the GNSS velocity consistently with the position (or the drift is so slow that the 0.08 m/s bias
  bound covers it), and
* the drift is slow enough that the drift z score stays below 1 for long enough for the estimator to learn a large
  share of the drift rate; on `sitl2.ulg` this happened at 0.25 m/s and 0.1 m/s and did not happen at 0.5 m/s.

The estimator's learning rate is a running mean for its first samples and then a 900 s exponential average, so the
share it absorbs depends on how long the vehicle has flown cleanly before the attack. Here the attack started 60 s
into the log, and the trace shows 25.7 s of learning at 55 s, the last point before the attack, which favours absorption.

## What it costs

**SIH + INJECTED.** The slowest drift caught in both modes, 0.5 m/s, is caught at a median offset of **21.7 m**
(velocity consistent) and **18.8 m** (velocity not consistent). That is the position error the vehicle accepts
before Marsad leaves TRUSTED. For faster drifts the median offset at the alarm is 20.5 to 22.4 m. A slower,
velocity consistent drift is not caught in 230 s at all, so its cost is unbounded within the window: a 0.25 m/s
drift is about 56 m off when the log is cut (computed from the injected offset).

## Smallest drift rate each label supports

| label | smallest drift rate that is supported | source |
|---|---|---|
| SIMULATED | 0.15 m/s stealth carry off, detected in 100% of runs (median 134 to 138 s); 0.1 m/s in 50 to 56%; 0.05 m/s never | `docs/results/weighting_fix/detectability.md` (unchanged from v1.1.0) |
| SIH + INJECTED | 0.5 m/s in both velocity modes within 230 s; 0.25 m/s only when the GNSS velocity is honest; 1 m/s within 32 s | `docs/results/weighting_fix/sih_inject*.txt` |
| REAL LOG | none. The real logs contain no attack and support only the false alarm claim (zero alarms over 911 s and 334 s) | `docs/results/weighting_fix/real_logs.txt` |
| SITL FAULT | none. No PX4 failure injection was scored; the fault at about 78 s in `sitl1.ulg` is cut off | |

The simulated floor is lower than the SIH floor mainly because in the simulator the estimator learns on every sample
and attacks start 150 to 260 s into each scenario (`src/marsad/sim/generator.py`), so the tighter bound is in force
before the attack begins.

## Tried and rejected: the bias estimator guard (2026-10-23)

The guard proposed in [PREREGISTRATION_BIAS.md](research/PREREGISTRATION_BIAS.md) was implemented exactly as written (commit
`a65372c`), evaluated, rejected and reverted (commit `5c5ca79`). The engine in this repository is the v1.3.0 engine.
Results of the runs that completed are in `docs/results/bias_fix/`; the v1.3.0 files are unchanged.

| check | label | v1.3.0 | with the guard | prediction |
|---|---|---|---|---|
| sitl1, every row (32 s window) | SIH + INJECTED | see `weighting_fix/sih_inject.txt` | identical | unchanged: hit |
| sitl1 and sitl2 clean, time TRUSTED | SIH + INJECTED (zero offset) | 100% | 100% (`bias_fix/clean_margin.txt`) | hit |
| flight1, flight2 time TRUSTED | REAL LOG | 100% | 100% (`bias_fix/real_logs.txt`) | hit |
| held out `benign_multipath`, runs reaching DENIED | SIMULATED | 3% | 7% | rise of at most 3 points: **miss** |
| held out `nominal` and `benign_obstruction`, runs reaching DENIED | SIMULATED | 0% and 0% | 0% and 0% | hit |
| held out `spoof_drift_stealth`, median latency | SIMULATED | 58.3 s | 52.9 s | no higher than 58.3 s: hit |
| dev `nominal`, time not TRUSTED and runs reaching DENIED | SIMULATED | 0% and 0% | 1% and 3% (1 of 30) | not predicted; a new false alarm on a clean run |
| held out navigation error (median of max), `spoof_jump` and `replay` | SIMULATED | 8 m and 10 m | 23 m and 21 m | not predicted; a regression |
| new test (`tests/test_bias_guard.py`) | | fails | passes | hit |
| sitl2 230 s rows (including 0.25 m/s velocity consistent), detectability sweep, ablation, full test suite with the guard | | | not completed: the runs were stopped when the rejection was already certain | not scored |

**Decision: rejected.** The acceptance conditions were no new false alarm on any clean or REAL LOG run and no
SIMULATED regression beyond seed noise. The same seeds as v1.3.0 were used, so the changes above are not seed noise:
a clean simulated flight now reaches DENIED, multipath reaches DENIED more often, and navigation error after a jump
or replay roughly doubles. The likely reason, not verified: in the simulator the estimator is still converging after
30 s of learning, so the guard compares against an early, unconverged estimate and fires on honest data. The 0.25 m/s
velocity consistent miss therefore remains, as described above. Any further attempt needs a new preregistration.
