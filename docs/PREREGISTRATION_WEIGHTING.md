# Preregistration: evidence weighting fix for mixed sample rates

Written on 2026-10-18 at 02:40 (UTC+4), **before** any engine code was changed and before any of the runs below
was made with the fixed engine. Committed on its own so that the commit history shows the order. No threshold,
preset or other detector logic will be changed in this change, and none will be changed after seeing the results.

## The defect

Documented in [VALIDATION.md](VALIDATION.md) ("Why the drifts were missed") and
[REVIEW_FINDINGS.md](REVIEW_FINDINGS.md). The engine computes one time step per input sample, `dt`, the gap since
the previous sample of any kind. Several pieces of evidence are computed only when a GNSS fix arrives but are
multiplied by that `dt`, as if the evidence were a rate accrued over the sample interval. When the reference
arrives faster than GNSS as separate samples, `dt` on a GNSS sample is the gap to the previous reference sample,
not the gap to the previous fix, and the evidence is diluted by the ratio of the two rates.

Sample structure as fed to the engine (counted from the logs, no engine run):

| log | label | samples | GNSS samples | reference samples | median GNSS gap | median reference gap | dilution |
|---|---|---|---|---|---|---|---|
| `sitl1.ulg` (to 77 s) | SIH + INJECTED | 9,530 | 612 | 9,213 | 0.124 s | 0.008 s | about 6% |
| `sitl2.ulg` (to 290 s) | SIH + INJECTED | 36,986 | 2,305 | 35,826 | 0.124 s | 0.008 s | about 6% |
| `flight1.ulg` | REAL LOG | 106,083 | 9,109 | 100,968 | 0.100 s | 0.009 s | about 9% |
| `flight2.ulg` | REAL LOG | 3,675 | 334 | 3,341 | 1.0 s | 0.1 s | about 10% |
| simulator (`marsad.sim`) | SIMULATED | 5 Hz | every sample with a usable fix | every sample | 0.2 s | 0.2 s | none, except after fix dropouts |

## The change

The engine will compute a second step, `gnss_dt`: the time since the previous usable fix (fix type 3), capped at
`gnss_gap_timeout` (1.5 s in every preset, beyond which the fix is treated as lost and the time based `fix_loss`
evidence takes over). It is 0 on samples without a usable fix and on the first fix. Every quantity that is
computed once per GNSS fix and scaled by a time step will use `gnss_dt` instead of `dt`:

| where | quantity | today | after |
|---|---|---|---|
| `detectors/inertial.py` | `gnss_vs_reference_drift` and `gnss_matches_reference` evidence | `dt` | `gnss_dt` |
| `detectors/kinematic.py` | `pos_vel_inconsistent` evidence | `dt` | `gnss_dt` |
| `detectors/signal.py` | `signal_down`, `signal_ok`, `agc_rise`, `spoof_power_signature` evidence | `dt` | `gnss_dt` |
| `engine.py` | `persistent_offset` and `verified_continuity` evidence (need a fix) | `dt` | `gnss_dt` |
| `engine.py` | reference bias estimator step and its "seconds of clean learning" counter | `dt` | `gnss_dt` |
| `engine.py` | anchor smoothing step (10 s time constant) | `dt` | `gnss_dt` |

Left unchanged, with reasons:

* `fix_loss` evidence (signal detector) and the fusion decay: these run on every sample and are meant to accrue
  or decay with elapsed time, so `dt` is correct.
* `noise_inflation` and the position prediction in the kinematic detector already use the gap to the previous fix.
* `position_jump`, `implied_speed`, `jump_reverted`, timing and replay evidence are per event, not per second.
* The reference white noise term in the inertial bound, `ref_noise * sqrt(W * max(dt, 0.05))`, models integration
  of reference noise at the reference sample rate, so the reference rate step is the right input there. It is
  below 0.15 m against a GNSS term of 5.7 m for the windows that matter, so it does not affect the results.
* Evidence produced by samples without a fix is unchanged, so the behaviour between fixes is unchanged.

A new unit test will feed a synthetic flight with the reference at 100 Hz and GNSS at 5 Hz as separate samples and
a 2 m/s carry off drift. It must fail on the current code and pass after the change.

## Predictions

Detection means the state leaves TRUSTED at or after the attack start; latency is measured from the attack start.
"Expected direction" refers to part 3 of `docs/results/sih_diagnose.txt` and `docs/results/sih_diagnose_long.txt`,
where the unchanged engine was fed the same logs at the GNSS epoch rate only (exploratory, post hoc). With the fix,
feeding the full mixed rate stream should behave like that epoch rate feed, because every quantity listed above then
accrues per second of GNSS time in both cases. The remaining differences (reference integrated at 125 Hz rather
than at 8 Hz, and the noise term above) are small.

### P1. SIH + INJECTED, sitl1.ulg, 32 s window

Command: `python scripts/sih_inject.py sitl1.ulg --out docs/results/weighting_fix/sih_inject.json`
(defaults `--end 77 --t-attack 45`). The case list has contained 0.1 and 0.25 m/s since the sitl2 run.

| case | v1.2.0 result | expected direction (epoch rate feed) | predicted Marsad detected (of 4) | predicted median latency | predicted gate baseline |
|---|---|---|---|---|---|
| clean log, no attack | 0 non TRUSTED | 0 | 0 non TRUSTED samples | n/a | 0 non TRUSTED samples |
| drift 0.1 m/s (both velocity modes) | 0/4 | not run | 0 | n/a | 0 |
| drift 0.25 m/s (both velocity modes) | 0/4 | not run | 0 | n/a | 0 |
| drift 0.5 m/s (both velocity modes) | 0/4 | 0/4 | 0 | n/a | 0 |
| drift 1.0 m/s, velocity consistent | 0/4 | 4/4, 27.6 s | 4 | 20 to 32 s | 0 |
| drift 1.0 m/s, velocity not consistent | 0/4 | 4/4, 25.5 s | 4 | 18 to 32 s | 0 |
| drift 2.0 m/s, velocity consistent | 0/4 | 4/4, 16.3 s | 4 | 11 to 22 s | 0 |
| drift 2.0 m/s, velocity not consistent | 0/4 | 4/4, 15.7 s | 4 | 11 to 22 s | 0 |
| jump 50, 200 and 1000 m | 4/4, 0.0 s | not run | 4 | under 1 s | 4, under 1 s |

### P2. SIH + INJECTED, sitl2.ulg, 230 s window

Command: `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/weighting_fix/sih_inject_long.json`

| case | v1.2.0 result | expected direction (epoch rate feed) | predicted Marsad detected (of 4) | predicted median latency | predicted gate baseline |
|---|---|---|---|---|---|
| clean log, no attack | 0 non TRUSTED | 0 | 0 non TRUSTED samples | n/a | 0 non TRUSTED samples |
| drift 0.1 m/s (both velocity modes) | 0/4 | not run | 0 | n/a | 0 |
| drift 0.25 m/s (both velocity modes) | 0/4 | not run | 4 | 70 to 200 s | 0 |
| drift 0.5 m/s, velocity consistent | 4/4, 204.6 s | 4/4, 48.2 s | 4 | 35 to 70 s | 0 |
| drift 0.5 m/s, velocity not consistent | 4/4, 159.1 s | 4/4, 42.5 s | 4 | 30 to 65 s | 0 |
| drift 1.0 m/s, velocity consistent | 4/4, 112.3 s | 4/4, 27.2 s | 4 | 20 to 40 s | 0 |
| drift 1.0 m/s, velocity not consistent | 4/4, 110.1 s | 4/4, 25.5 s | 4 | 18 to 38 s | 0 |
| drift 2.0 m/s, velocity consistent | 4/4, 98.4 s | 4/4, 16.2 s | 4 | 11 to 25 s | 0 |
| drift 2.0 m/s, velocity not consistent | 4/4, 98.1 s | 4/4, 15.7 s | 4 | 11 to 25 s | 0 |
| jump 50, 200 and 1000 m | 4/4, 0.0 s | not run | 4 | under 1 s | 4, under 1 s |

Additional predictions for P1 and P2:

* P3. Median position offset at the Marsad alarm is under 35 m for every detected drift case of 0.5 m/s and faster
  (v1.2.0: 77 to 187 m on sitl2).
* P4. Within each velocity mode, latency is ordered 0.25 > 0.5 > 1.0 > 2.0 m/s for the cases that are detected.
* P5. The gate baseline results are identical to v1.2.0 (it does not use the engine).

Reasoning for 0.25 m/s on sitl2, the least certain prediction: the epoch rate feed did not include it. In the
simulated detectability sweep (`docs/results/detectability.md`) 0.2 and 0.3 m/s are detected 100% at 101 s and
70 s. On sitl2 the bias estimator reaches its 150 s of clean learning only after the attack has started, so the
looser 0.08 m/s bias bound applies for part of the window, and in the velocity consistent mode the estimator can
absorb part of the drift before the drift z score passes 1. Either effect could push detection past the end of the
window for some headings.

### P6. REAL LOG replays, false alarm side

Commands: `marsad replay flight1.ulg --json docs/results/weighting_fix/real_flight1.json` and the same for
`flight2.ulg`, console output in `docs/results/weighting_fix/real_logs.txt`.

| log | v1.2.0 | predicted |
|---|---|---|
| `flight1.ulg` | TRUSTED 911 s (100%), Marsad never non TRUSTED | TRUSTED 100%, 0 s non TRUSTED |
| `flight2.ulg` | TRUSTED 334 s (100%), Marsad never non TRUSTED | TRUSTED 100%, 0 s non TRUSTED |

Reasoning: GNSS driven evidence grows by roughly 10 to 11 times on these logs. The reference is the EKF fused
velocity, which follows GNSS, so the drift z score stays low, and there is no C/N0 in these logs. The risk is the
satellite count part of `signal_down` and the kinematic `pos_vel_inconsistent` evidence, which now accrue at their
intended rate. These logs test only the false alarm side; the reference is contaminated.

### P7. SIMULATED evaluation (`python scripts/run_eval.py`, about 12 min)

Output to `docs/results/weighting_fix/` (the script will gain an `--out` option; the default stays
`docs/results`, so the v1.1.0 files are not overwritten). Same seeds as v1.1.0.

In the simulator GNSS and reference share one 5 Hz sample, so `gnss_dt` equals `dt` on every sample that carries a
usable fix, except the first fix after one or more samples without a usable fix.

* P7a. **Identical.** For every scenario in which every sample carries a usable fix (`nominal`,
  `benign_multipath`, `spoof_jump`, `spoof_jump_transient`, `spoof_drift`, `spoof_drift_stealth`, `replay`,
  `spoof_drift_noref`, `spoof_drift_ref_outage`), every number in `heldout.md` and `dev.md`, every cell of
  `detectability.md`, and the rows for those scenarios in `ablation.md` are identical to v1.1.0.
* P7b. `jam_hard` (fixes lost during the jam): detection 100% on both splits; median latency within 0.5 s of
  v1.1.0 (held out 2.4 s), because detection happens before the fix is lost.
* P7c. `jam_soft` (30% of fixes dropped at random during the jam): detection 100% on both splits; median latency
  no higher than v1.1.0 (held out 5.0 s, dev 5.2 s) and at least 3.0 s, because the dropped epochs are now
  credited to the next fix and the jamming evidence accrues faster. Settled class accuracy within 10 points of
  v1.1.0.
* P7d. `benign_obstruction` (fixes lost while fewer than 4 satellites): time not TRUSTED within 5 points of v1.1.0
  (held out 85%, dev 88%); runs reaching DENIED at most 10% (v1.1.0: 0%).
* P7e. Throughput (`throughput.json`) is not a prediction target; it varies with the machine. It should stay within
  20% of 187.7 us per sample.

### P8. Tests

All existing tests pass without modification. The new mixed rate test fails on the current code and passes after
the change. `tests/test_api.py` and `tests/test_mcp.py` generate streams at a GNSS cadence of 1 s with the
reference at 5 Hz, so they are mixed rate too and their evidence grows five fold; their assertions are about
state changes in attack scenarios and are expected to hold.

## How hits and misses will be scored

A detection case is a hit if the detected count matches exactly and the median latency falls inside the stated
band. P3 to P8 are scored as stated. Results, hits and misses will be reported in [VALIDATION.md](VALIDATION.md)
and [EVALUATION.md](EVALUATION.md) next to the v1.1.0 and v1.2.0 numbers, which stay in `docs/results/` unchanged.
