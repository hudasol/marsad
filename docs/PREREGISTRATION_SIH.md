# Preregistration: SIH + INJECTED evaluation on sitl1.ulg

Written on 2026-10-16 at 05:09 (UTC+4), **before** `scripts/sih_inject.py` was run on `sitl1.ulg` by this author.
Committed before the run so that the commit history shows the order. No threshold, preset or detector was
changed for this experiment, and none will be changed after seeing the result.

## What is being tested

* **Log.** `sitl1.ulg`, a PX4 v1.18 SIH (simulation in hardware) run. GNSS stream, timing and noise are real PX4
  outputs; the receiver itself is simulated. The log is cut at 77 s, before the real receiver fault at about 78 s.
* **Attack.** A measurement level position offset added to the logged GNSS fixes from 45 s, so the attack window
  is 32 s. Every case is run at 4 headings (north, east, south, west), so n = 4 per case.
* **Reference.** `vehicle_local_position_groundtruth` velocity (simulator truth), not the EKF output.
* **Label.** SIH + INJECTED. This is not real spoofing and not a real receiver.
* **Command.** `python scripts/sih_inject.py sitl1.ulg --out docs/results/sih_inject.json`

## Predictions

Detection means the state leaves TRUSTED at or after the attack start. Latency is measured from 45 s.

| case | Marsad detected (of 4) | Marsad latency band | gate baseline detected (of 4) |
|---|---|---|---|
| clean log, no attack | 0 non TRUSTED samples | n/a | 0 non TRUSTED samples |
| drift 0.5 m/s, velocity consistent | 4 | 5 to 20 s | 0 |
| drift 0.5 m/s, velocity not consistent | 4 | 5 to 25 s | 0 |
| drift 1.0 m/s, velocity consistent | 4 | 3 to 15 s | 0 |
| drift 1.0 m/s, velocity not consistent | 4 | 3 to 15 s | 0 |
| drift 2.0 m/s, velocity consistent | 4 | 2 to 10 s | 0 |
| drift 2.0 m/s, velocity not consistent | 4 | 2 to 10 s | 0 |
| jump 50 m | 4 | under 1 s | 4 (under 1 s) |
| jump 200 m | 4 | under 1 s | 4 (under 1 s) |
| jump 1000 m | 4 | under 1 s | 4 (under 1 s) |

Additional predictions:

1. Position offset at the moment of the Marsad alarm is under 15 m for every drift case.
2. Slower drifts take longer than faster drifts (latency ordered 0.5 > 1.0 > 2.0 m/s within each velocity mode).

## Reasoning behind the predictions

* The reference is simulator truth, so its real bias is near zero while the engine still assumes the preset bound
  (0.08 m/s for `uav_multirotor`; the bias estimator needs 150 s of clean learning and will not have converged by
  45 s). Drifts of 0.5 m/s and faster are well above that bound, so the reference check should fire once the
  10 s ramp has built up a few tenths of a metre per second of disagreement.
* The gate baseline compares each fix with the previous fix propagated by the GNSS velocity. A drift adds at most
  a fraction of a metre per fix, far below its gate of about 10 m, so it should never fire on a drift. A jump of
  50 m or more exceeds that gate on the first attacked fix.
* Uncertainty: the window is short (32 s), the vehicle is flying a square, and the engine has not seen this log
  before. The largest risk to these predictions is the 0.5 m/s cases running out of window, and the
  "velocity not consistent" cases behaving differently from the simulator because SIH GNSS noise differs from the
  simulator's noise model.

## How hits and misses will be scored

A case is a hit if the detected count matches exactly and the median latency falls inside the stated band.
Results are reported in `docs/VALIDATION.md` next to this table, misses included.

## Addendum: long clean flight (sitl2.ulg), written before the run

Written on 2026-10-17 at 23:34 (UTC+4), after the sitl1 result and its diagnosis and before `sih_inject.py` was run on
`sitl2.ulg`. These predictions are therefore informed by the sitl1 miss: the drift evidence is diluted to roughly 6%
of its intended rate because the reference arrives at about 125 Hz and GNSS at about 8 Hz. The engine is unchanged.

* **Log.** `sitl2.ulg`, PX4 SIH, 300 s square at 5 m/s with no fault injection. Checked before use: fix type 3 on
  every fix, GNSS error against ground truth at most 0.30 m, Marsad TRUSTED on every sample.
* **Command.** `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_inject_long.json`
  (attack window 230 s). The case list now also contains drift rates of 0.1 and 0.25 m/s.

| case | Marsad detected (of 4) | Marsad latency band | gate baseline detected (of 4) |
|---|---|---|---|
| clean log, no attack | 0 non TRUSTED samples | n/a | 0 non TRUSTED samples |
| drift 0.1 m/s (both velocity modes) | 0 | n/a | 0 |
| drift 0.25 m/s (both velocity modes) | 0 | n/a | 0 |
| drift 0.5 m/s (both velocity modes) | 0 | n/a | 0 |
| drift 1.0 m/s (both velocity modes) | 4 | 60 to 180 s | 0 |
| drift 2.0 m/s (both velocity modes) | 4 | 40 to 120 s | 0 |
| jump 50, 200 and 1000 m | 4 | under 1 s | 4 (under 1 s) |

Reasoning: with diluted evidence only drifts that build a large z score over the longer windows (up to 240 s) should
accumulate enough evidence inside 230 s. I expect 0.5 m/s and slower to stay TRUSTED, which would mean the long
window does not rescue the slow cases while the evidence weighting defect remains.
