# Proposal and preregistration: guard the reference bias estimator against velocity consistent drift

Written on 2026-10-18 (UTC+4) as a **proposal**. No engine code has been changed for it, and none will be until the
author decides to go ahead. If it goes ahead, this file is the preregistration: the predictions below are fixed now,
before any implementation or run, and will be scored as written.

## Problem

Documented in [KNOWN_LIMITS.md](KNOWN_LIMITS.md). While the drift z score is below 1, the engine learns the reference
velocity bias from (reference velocity minus GNSS velocity). A spoofer that shifts the GNSS velocity together with the
position turns that difference into the drift rate, and the estimator absorbs it. On `sitl2.ulg` (SIH + INJECTED) the
north estimate moved from -0.035 m/s at 75 s to -0.083 m/s at 95 s during a 0.25 m/s drift, and the drift was missed.

## Physical argument

The reference sensors Marsad is meant for (visual inertial odometry, optical flow with range, wheel odometry, Doppler
logs) have biases that wander slowly: the preset bound after learning, `ref_bias_residual`, is 0.03 m/s. An
estimate that moves by more than that bound within half a minute is better explained by the GNSS velocity moving
than by the reference sensor changing.

## Proposed change (one mechanism, no threshold changes elsewhere)

* Keep a short history of the bias estimate. When the estimator is about to learn on a fix, compare the estimate with
  its value 30 s earlier (only once at least 30 s of learning exist).
* If the north or east component has moved by more than `ref_bias_residual` (0.03 m/s in every preset) in that
  time, do not learn on this fix, restore the estimate to its value 30 s earlier, and emit evidence
  `bias_estimate_moved` towards `spoofing_drift` with the same weight rule as `gnss_vs_reference_drift` at z = 3.
* Two new configuration values with these defaults: `bias_guard_window_s = 30.0`, `bias_guard_step = None` (meaning
  "use `ref_bias_residual`"). No other threshold, preset or detector changes.

Considered and not proposed: letting the estimator learn on every fix rather than only on fixes that share a sample
with the reference. It would reach the tighter bound sooner on SIH logs, but it also speeds up absorption, and its
net effect is not predictable enough to preregister with confidence.

## Predictions (scored only if the change is implemented)

Commands as in [VALIDATION.md](VALIDATION.md), "Evidence weighting fix", with output to a new folder
`docs/results/bias_guard/`. Latency is from the attack start; "unchanged" means the same detected count and a median
latency within 0.5 s of `docs/results/weighting_fix/`.

| run | case | v1.3.0 | predicted |
|---|---|---|---|
| sitl2, 230 s, SIH + INJECTED | drift 0.25 m/s, velocity consistent | 0/4 | 4/4, median 60 to 200 s |
| sitl2 | drift 0.1 m/s, velocity consistent | 0/4 | 0/4 (low confidence: the estimate moved 0.036 m/s in 40 s, close to the guard) |
| sitl2 | drift 0.1 m/s, velocity not consistent | 0/4 | 0/4 (the estimate does not move; the bound limits) |
| sitl2 | every other drift and jump row | see weighting_fix | unchanged |
| sitl1, 32 s, SIH + INJECTED | every row | see weighting_fix | unchanged |
| sitl1, sitl2 clean | non TRUSTED samples | 0 | 0 |
| flight1, flight2, REAL LOG | time TRUSTED | 100% | 100% (risk: the EKF reference follows GNSS, so its apparent bias could move) |
| SIMULATED held out | nominal, benign obstruction, benign multipath | 0% / 0% / 3% runs DENIED | no run fraction reaching DENIED rises by more than 3 points |
| SIMULATED held out | spoof_drift_stealth | 100%, median 58.3 s | 100%, median no higher than 58.3 s |
| SIMULATED detectability | 0.1 m/s cells | 50 to 56% | each cell at least as high as v1.3.0 |
| Tests | existing tests | 143 pass | all pass unmodified, plus one new test with a velocity consistent 0.25 m/s drift that fails before the change |

## Risks named in advance

* Reference sensors with genuinely jumpy bias (vision after a scene change, wheel slip) could trigger the guard and
  raise false alarms. The REAL LOG replays cannot test this because their reference is the EKF output.
* A spoofer who ramps more slowly than 0.03 m/s per 30 s keeps the estimate under the guard; the drift floor would
  move, not disappear.

## Decision

Not implemented. Recorded in [RUN_LOG.md](RUN_LOG.md) for the author to decide.
