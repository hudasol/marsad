# Known limits (v1.4.0)

This page lists what Marsad still misses or does badly, with the evidence for each item. Every number carries one
label and comes from a file in `docs/results/`. The analysis of the v1.3.0 misses is kept in
[history/known-limits-v1.3.0.md](history/known-limits-v1.3.0.md).

## 1. Drift slower than 0.25 m/s is not detected

**Label: SIH + INJECTED** (`sitl2.ulg`, 230 s attack window, simulator truth velocity as the reference, 4 headings
per case; `docs/results/prior_bound/sih_inject_long.txt`).

| drift | velocity consistent | velocity not consistent |
|---|---|---|
| 0.1 m/s | 0/4 | 0/4 |
| 0.25 m/s | 4/4, median 113.6 s, offset 27.1 m (v1.3.0: 0/4) | 4/4, median 113.4 s, offset 27.1 m |
| 0.5 m/s | 4/4, median 42.5 s, offset 18.8 m | 4/4, median 42.4 s, offset 18.7 m |

No baseline detects 0.1 m/s either (`docs/BASELINES.md`). Below the reference bias bound a slow drift and a
biased reference are the same observation, so this is a limit of the information available and not only of the
method. **SIMULATED** floor: 0.15 m/s in 100% of runs, 0.1 m/s in 50 to 56%, 0.05 m/s never
(`docs/results/prior_bound/detectability.md`).

What changed in v1.4.0: the engine now also compares the displacement against the uncorrected reference integral
and the bound `ref_bias_bound`, so the bias estimator can no longer absorb a velocity consistent drift. The
prediction and the outcome are in [research/PREREGISTRATION_PRIOR_BOUND.md](research/PREREGISTRATION_PRIOR_BOUND.md).

## 2. Slower than a plain window test

**Label: SIMULATED and SIH + INJECTED** (`docs/BASELINES.md`).

A sliding window consistency test that uses the same reference detects drift sooner than Marsad: 22.6 s against
27.1 s on `spoof_drift`, and 57.1 s against 113.6 s for 0.25 m/s drift on `sitl2.ulg`. Marsad pays this latency for
a bias allowance and for its classification. The window test also alarms in 23% of nominal simulated runs and 60%
of multipath runs, cannot separate drift from jump or replay, and holds no fallback position. The SIH figures are
flattered because the SIH reference has no bias.

## 3. Without an independent reference

**Label: SIMULATED.** `spoof_drift_noref` is detected in 53% of runs (median 33.1 s), labelled
`spoofing_unclassified`, and no fallback position is produced. The window baseline reaches 87% on the same runs
because it falls back to the receiver velocity. Marsad has no equivalent fallback channel yet; it is the first item in
[ROADMAP.md](ROADMAP.md).

## 4. Obstruction is treated as a denial of confidence

**Label: SIMULATED.** In `benign_obstruction` Marsad leaves TRUSTED in 85% of the time (the signal baseline: 95%),
though it reaches DENIED in none of the runs. The position is genuinely poor in that case; the limit is that Marsad
does not tell an operator whether the cause is the sky view or interference.

## 5. Attack at power-up

There is no clean history to compare against, so anchor and bias estimates have nothing to start from. Not scored
on any label.

## 6. What has not been tested at all

| label | status |
|---|---|
| REAL LOG | Two public PX4 flights replay with zero alarms (911 s and 334 s, v1.3.0 engine). These contain no attack, so they support only the false alarm claim. The v1.4.0 engine and the baselines have not been replayed on them in this repository. |
| SITL FAULT | No PX4 failure injection was scored. |
| Real interference data | None. |
| Real flight controller | None. The MAVLink reporter and the `monitor` command are tested against a pymavlink loopback only. |

## 7. Baselines are reimplementations

The EKF2 style baselines follow the documented PX4 defaults but are not the EKF2 filter. A replay of recorded logs
through PX4 with injected GNSS is the proper comparison and is on the roadmap.

## Tried and rejected

The bias estimator guard (2026-10-23), preregistered in [research/PREREGISTRATION_BIAS.md](research/PREREGISTRATION_BIAS.md),
raised false alarms on clean and multipath runs and doubled navigation error after a jump. It was reverted. Details
and the table are in [history/known-limits-v1.3.0.md](history/known-limits-v1.3.0.md).
