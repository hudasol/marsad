# Known limits (v1.5.0)

This page lists what Marsad still misses or does badly, with the evidence for each item. Every number carries one
label and comes from a file in `docs/results/`. The v1.4.0 version of this page, before the real flight corpus, is kept in
[history/known-limits-v1.4.0.md](history/known-limits-v1.4.0.md); the v1.3.0 analysis is in
[history/known-limits-v1.3.0.md](history/known-limits-v1.3.0.md). The consolidated evidence is in [EVIDENCE.md](EVIDENCE.md).

## 0. Findings of v1.5.0, first because they are the largest

### 0.1 False alarms on real flights

**Label: REAL LOG** (101 scoring flights from PX4 Flight Review, 18.5 flight hours, engine v1.4.0).
Fully TRUSTED on 54 flights (53.5%), a DENIED sample on 46, 3.0 alarm episodes per flight hour. 87 hardware names, so
no per board claim is possible. The largest causes are lost fixes on receivers at 1 Hz and start up before the first
stable fix ([results/real_corpus/causes.json](results/real_corpus/causes.json)). A trial fix for these (engine change
with an adaptive loss timeout) did not reach its target and was not adopted
([research/PREREGISTRATION_CADENCE.md](research/PREREGISTRATION_CADENCE.md)). Two mechanisms were found and are
documented but not fixed: the recovery timer was cleared on ticks without a fix on interleaved streams, and a reacquisition
that cannot be verified after a long outage leaves the state latched (item 5 below still applies).

### 0.2 A reference that follows the spoofed receiver

**Label: SITL EKF2** (4 runs per cell). When the reference is the velocity of the vehicle's own EKF2, which fuses the
spoofed fixes, a drift whose velocity is consistent with its position is not detected at any rate from 0.25 to 2.0
m/s, by Marsad, the plain gate or the window test, and PX4's own innovation check rejected nothing for 1 s or longer.
Position only drift of 0.5 m/s or more is detected. This is the realistic case for most vehicles, and it is a limit of
the information available as much as of the method: the only defence is a reference that is independent of the GNSS
(optical flow, visual odometry, wheel odometry), which 7 of the 139 corpus flights had.

### 0.3 A plain window test is as sensitive and faster

**Label: REAL LOG + INJECTED** (52 flights, reference arm that is an optimistic bound). Window consistency detected
drift at every rate in every flight where Marsad did, and 6 to 54 s sooner. Marsad's case rests on classification, on the
fallback position and on lower false alarms in simulated multipath, none of which was measured on real flights.

### 0.4 Unusable flights

23 of 75 eligible corpus flights were already alarmed before the injected onset and could not be scored, so every
detection table on real flights is conditional on a clean start. That is a bias in favour of the engine.

### 0.5 Reference model errors

**Label: SIH + INJECTED** (4 flights per cell). A reference velocity bias of 0.30 m/s caused a false alarm in 4 of 4
flights, and 0.15 m/s did not. The engine's assumed bound is 0.096 m/s. A scale error of 5% (assumed, no source) and a
composite model with dropouts produced no false alarm in 4 flights; four flights cannot show robustness.

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
method. **SIMULATED** floor: 0.15 m/s in 94 to 100% of runs, 0.1 m/s in 56 to 62%, 0.05 m/s never
(`docs/results/prior_bound/detectability.md`; the 94% cell is a reference bias of 0.08 m/s, 1 of 16 runs lower than v1.3.0).

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
| REAL LOG | The two public flights of v1.3.0 replayed with zero alarms; the 101 flight corpus of v1.5.0 shows the false alarm problem in 0.1. Attacks added to real flights are REAL LOG + INJECTED (section 0.3). |
| SITL FAULT | No PX4 failure injection was scored. |
| Real interference data | None. |
| Real flight controller | None. PX4 software in the loop with a simulated GPS was used (SITL EKF2); no hardware. The MAVLink reporter and the `monitor` command are tested against a pymavlink loopback only. |

## 7. Baselines are reimplementations

The EKF2 style baselines follow the documented PX4 defaults but are not the EKF2 filter. PX4's own EKF2 was run in the
loop in SITL EKF2 (4 runs per cell) and its accept and reject decisions are reported next to them; it is not a
replacement for the baselines on the real logs, where the innovation topics were compared descriptively
([EVIDENCE.md](EVIDENCE.md), section 1).

## Tried and rejected

The adaptive loss timeout and recovery timer change of 2026-11-03 ([research/PREREGISTRATION_CADENCE.md](research/PREREGISTRATION_CADENCE.md)), kept as a patch in `research/patches/`, because it missed its targets and delayed some simulated detections.


The bias estimator guard (2026-10-23), preregistered in [research/PREREGISTRATION_BIAS.md](research/PREREGISTRATION_BIAS.md),
raised false alarms on clean and multipath runs and doubled navigation error after a jump. It was reverted. Details
and the table are in [history/known-limits-v1.3.0.md](history/known-limits-v1.3.0.md).
