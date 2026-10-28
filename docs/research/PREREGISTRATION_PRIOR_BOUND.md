# Proposal and preregistration: a prior bound channel for the drift detector

Written on 2026-10-28 (UTC+4), before any engine code for it exists. The predictions below are fixed now and will
be scored as written, whether or not they hold. Outcome section at the end is empty until then.

## Why this is being tried

[BASELINES.md](../BASELINES.md) compares the engine with detectors that share its input. A plain sliding window
displacement test (GNSS displacement minus integrated reference velocity, fixed bias allowance, no learning)
detects the velocity consistent 0.25 m/s drift on `sitl2.ulg` in 57 s where Marsad v1.3.0 detects nothing
([KNOWN_LIMITS.md](../KNOWN_LIMITS.md)). Marsad already has the same test in `detectors/inertial.py`. The difference is
that Marsad compares GNSS with the *bias corrected* reference integral. Once the bias estimator has learned a drift
as sensor bias, the corrected integral follows the drift and the test sees nothing.

An earlier attempt to guard the estimator itself was scored and rejected ([PREREGISTRATION_BIAS.md](PREREGISTRATION_BIAS.md),
`docs/results/bias_fix/`). This proposal leaves the estimator alone.

## Proposed change (one mechanism)

* The engine also keeps the integral of the *uncorrected* reference velocity.
* For each drift window the inertial detector computes the existing z score (corrected integral, bias bound as
  today) and a second z score from the uncorrected integral with the configured prior bound `ref_bias_bound`
  (0.08 m/s for `uav_multirotor`), which never tightens. The window z is the larger of the two.
* Nothing else changes: same windows, same threshold `drift_z0`, same evidence rule, no new configuration values.

Physical argument: the prior bound is the contract the preset states for the reference sensor. A discrepancy larger
than that bound over a window cannot be explained by sensor bias, whatever the estimator has learned. Before the
estimator has tightened its bound (first 150 s of learning) both z scores are identical, so the channel only
matters afterwards, which is where the absorption happens.

## Predictions (scored when implemented)

Commands as in [VALIDATION.md](../VALIDATION.md) and the README reproduction table; output goes to
`docs/results/prior_bound/`. Latency is from the attack start. "Unchanged" means the same detected count and a
median latency within 0.5 s of `docs/results/weighting_fix/`.

| run | case | v1.3.0 | predicted |
|---|---|---|---|
| sitl2, 230 s, SIH + INJECTED | drift 0.25 m/s, velocity consistent | 0/4 | 4/4, median 100 to 170 s |
| sitl2 | drift 0.25 m/s, velocity not consistent | 4/4, 113.6 s | 4/4, median no later than 114.1 s |
| sitl2 | drift 0.1 m/s, both modes | 0/4 | 0/4 (24 m after 240 s against a 20 m allowance, z about 1.2) |
| sitl2 | drift 0.5, 1, 2 m/s, both modes | see weighting_fix | 4/4, median no later than v1.3.0 plus 0.5 s |
| sitl2 | jumps 50, 200, 1000 m | 4/4 at first fix | unchanged |
| sitl1, 32 s, SIH + INJECTED | every row | see weighting_fix | unchanged |
| sitl1, sitl2 clean | samples not TRUSTED | 0 | 0 |
| SIMULATED held out, seeds 5000 to 5029 | nominal, benign obstruction | 0% / 0% of runs DENIED | unchanged |
| SIMULATED held out | benign multipath | 3% of runs DENIED | no more than 6% (2 of 30) |
| SIMULATED held out | spoof_drift_stealth, spoof_drift | 100%, 58.3 s and 27.2 s | 100%, median no later than before plus 0.5 s |
| SIMULATED held out | every other attack row | see weighting_fix | unchanged |
| SIMULATED detectability sweep | every cell | see weighting_fix | each cell at least as high, 0.05 m/s still 0% |
| REAL LOG, flight1 and flight2 | share of time TRUSTED | 100% | 100% (to be run by the author; the logs are not available to the build environment) |
| Tests | existing tests | all pass | all pass unmodified, plus one new test that fails before the change |

## Risks named in advance

* A reference sensor with a true bias above the prior bound will now raise drift evidence even after the estimator
  has learned that bias. The simulated held out split uses biases up to 0.096 m/s (1.2 times 0.08), which is the
  reason for the multipath and nominal rows above.
* The channel cannot help below roughly 0.15 m/s; the floor moves for velocity consistent drift, it does not vanish.
* If any nominal or benign row above fails its prediction the change is reverted as a new commit and the outcome is
  recorded here, as was done for the bias guard.

## Outcome

Scored 2026-10-28 against `docs/results/prior_bound/` (second run) and `docs/results/baselines/`. The first run is
kept in `docs/results/prior_bound_run1/`; it exposed the anchor history defect described below.

| prediction | result | verdict |
|---|---|---|
| sitl2, 0.25 m/s velocity consistent: 4/4, median 100 to 170 s | 4/4, 113.6 s | hit |
| sitl2, 0.25 m/s not velocity consistent: 4/4, no later than 114.1 s | 4/4, 113.4 s | hit |
| sitl2, 0.1 m/s both modes: 0/4 | 0/4 in both | hit |
| sitl2, 0.5, 1, 2 m/s: median no later than v1.3.0 plus 0.5 s | 42.4 to 42.5 s, 25.4 to 25.5 s, 15.6 to 15.8 s; all at or below v1.3.0 | hit |
| sitl2, jumps | 4/4 at the first fix | hit |
| sitl1, every row unchanged | the velocity consistent rows at 1 and 2 m/s moved earlier (27.8 to 25.5 s, 16.3 to 15.8 s); the rest unchanged | **miss** (improvement) |
| sitl1 and sitl2 clean: 0 samples not TRUSTED | 0 | hit |
| held out nominal, obstruction: 0% and 0% DENIED | 0% and 0% | hit |
| held out multipath: at most 6% DENIED | 3% | hit |
| held out `spoof_drift_stealth`, `spoof_drift` no later than before plus 0.5 s | 58.0 s and 27.1 s against 58.3 s and 27.2 s | hit |
| held out every other attack row unchanged | detection and latency unchanged; `spoof_drift_ref_outage` median navigation error 37 to 31 m and settled class accuracy 87% to 83% | **miss** |
| detectability sweep: each cell at least as high, 0.05 m/s still 0% | 0.05 m/s is 0% in all rows; the 0.08 bias, 0.15 m/s cell fell from 100% to 94%; the 0.1 m/s cells rose (56%, 56%, 62%) | **miss** (one cell) |
| REAL LOG flight1 and flight2: 100% TRUSTED | not run; the logs were not available to the build environment | not scored |
| tests: all pass, one new test fails before the change | 167 pass; `test_velocity_consistent_drift_of_a_quarter_metre_per_second_is_detected` fails at the parent of the engine change | hit |

Deviations from the preregistered plan:

* The first scoring run showed `spoof_drift_ref_outage` seed 5015 going from 36 m to 495 m of navigation error. The
  cause was not the new channel but an existing defect: a new anchor segment kept the anchor history of the previous
  one, so a later rewind used samples from before the reference restarted. The fix (clear the history when a new
  anchor starts) was not part of the preregistration. Everything was rerun after it; run 1 is kept as a record.
* The `ref_outage` navigation error and settled class accuracy changes above are the effect of that fix and of the
  channel together, and were not separated.

Decision: kept. No nominal or benign prediction failed, the target case was detected, and the three misses are an
improvement on two rows and a small loss on two cells. The 0.08 bias, 0.15 m/s cell is the only place detection got
worse, and it is recorded in `docs/KNOWN_LIMITS.md`.

## Erratum, 2026-10-28, before any run was scored

The sentence "Before the estimator has tightened its bound (first 150 s of learning) both z scores are identical" is
wrong: the estimator subtracts its current estimate from the first sample, so the two integrals differ from the
start. A synthetic check showed the learned estimate reached -0.061 m/s while the bound was still the wide one,
because learning stops once the drift z score passes 1. The mechanism as stated in the bullet list (always take the
larger of the two z scores) is what is implemented. The predictions table is unchanged.
