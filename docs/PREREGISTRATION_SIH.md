# Preregistration: SIH + INJECTED evaluation on sitl1.ulg

Written on 2026-10-16 at 05:09 (AST), **before** `scripts/sih_inject.py` was run on `sitl1.ulg` by this author.
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
