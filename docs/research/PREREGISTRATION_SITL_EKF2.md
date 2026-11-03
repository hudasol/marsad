# Preregistration: PX4's own EKF2 in the loop

Written on 2026-11-03 (UTC+4), before any run of this study. Label for every number here: **SITL EKF2**.

## Question

When the position fixes that PX4's EKF2 consumes are shifted (jump or carry off drift), what does EKF2 itself do, and
what does Marsad v1.4.0 do on the same flight when its reference is EKF2's fused velocity, which is what a real
deployment would have? Earlier results used either simulator truth (SIH + INJECTED) or a logged EKF velocity computed
from clean fixes (REAL LOG + INJECTED arm a). This study removes that optimism: the reference is dragged along by the
spoofed fixes, as in a real attack.

## Design

* PX4 is built from the pinned commit with a small patch (`scripts/px4_sensor_gps_sim_offset.patch`, 5 parameters
  `SIM_SPF_*`) that adds a position offset, and optionally a matching velocity offset, to the fixes published by the
  simulated receiver module `sensor_gps_sim`. EKF2, the controllers and the logger are unmodified. The offset is a
  measurement edit; no RF is generated or transmitted. The patch is a change to a simulator module, so the result is
  a statement about EKF2 behaviour on shifted fixes, not about any real receiver.
* Vehicle: SIH quadrotor (`sihsim_quadx`), flown by `scripts/sitl_ekf2_spoof.py` in a fixed square at 5 m/s,
  240 s, onset at 60 s after the vehicle reaches its first leg. The same flight is flown without any offset.
* Cases: jump 50, 200, 1000 m; drift 0.25, 0.5, 1.0, 2.0 m/s (10 s ramp) with the velocity offset on and off; four
  headings (0, 90, 180, 270). 44 attack runs and 4 clean runs (one per heading slot, same pattern).
* The logged `sensor_gnss` (shifted fixes) and PX4's EKF2 outputs are written to a ULog by PX4's logger. Marsad
  replays the ULog with `uav_multirotor`. Two reference arms, never pooled: (a) EKF2 fused velocity
  (`vehicle_local_position`), the realistic one; (b) simulator truth velocity, as in SIH + INJECTED.
* Simulator speed factor may be raised for wall clock reasons; it is recorded. Results use log time.

## Metrics

* Marsad detection (first non TRUSTED sample at or after the onset), latency, offset at alarm, per run. Unit: run.
  Proportions with Clopper Pearson 95% intervals; n is 4 per case, so intervals are wide and are stated.
* EKF2 response: first `estimator_aid_src_gnss_pos` / `_vel` rejection after the onset, longest rejection run,
  `cs_gnss_fault` seen, and the horizontal distance between EKF2's position estimate and the simulator truth at 60 s
  after the onset (how far EKF2 was carried).
* Baselines on the same logs: the plain gate, `ekf2_gate_ref`, `window`, `stack`.
* Clean runs: Marsad and baseline alarms.
* Number of primary comparisons: 6 (below).

## Baselines

Simple: plain gate. Competitor: EKF2 itself (its own rejection and fault flags) and `window` consistency.

## Predictions

| id | prediction |
|---|---|
| E1 | jump of 1000 m: EKF2's estimate is within 50 m of the shifted position 60 s after the onset in at least 3 of 4 runs (EKF2 accepts the spoof after its reset). Can fail if the fusion timeout does not reset |
| E2 | velocity consistent drift at 1.0 m/s: EKF2 shows no rejection run of 1 s or longer in at least 3 of 4 runs |
| E3 | arm (a), velocity consistent drift at 1.0 m/s: Marsad detects in at most 2 of 4 runs within 180 s, while arm (b) detects in 4 of 4 |
| E4 | jumps of 200 m and 1000 m: Marsad detects in 4 of 4 runs in both arms |
| E5 | clean runs: no Marsad alarm in 4 of 4 runs, both arms |
| E6 | arm (a), velocity consistent drift at 0.25 m/s: Marsad detects in at most 1 of 4 runs |

## Risks named in advance

* The PX4 build or the MAVLink parameter path may not give a working onset at the intended time. If a route does not
  work after three attempts the study is reported as not completed with the reason, and nothing from it is claimed.
* SIH timing, noise and receiver model are simulated; four runs per cell is a small n.
* Marsad and the patch share an author.

## Kill criteria

None; this is a measurement.

## Outcome

Scored on 2026-11-03 (UTC+4) with the v1.4.0 engine (commit b25b502, run from a separate checkout so that later engine
changes did not enter). 48 runs (44 attack, 4 clean) at a simulator speed factor of 6, PX4 `fe24ec22` with the offset
patch. Files: `docs/results/sitl_ekf2/{runs.json,summary.md}`. The PX4 logs (70 MB each, 3.3 GB) are not committed.
Label: **SITL EKF2**. n is 4 per cell, so every share is one of 0, 0.25, 0.5, 0.75, 1 with a wide interval.

| id | prediction | measured | result |
|---|---|---|---|
| E1 | jump of 1000 m: EKF2's estimate within 50 m of the shifted position 60 s after onset in at least 3 of 4 runs | EKF2 position error against truth was 1000 m at 60 s in 4 of 4 runs, i.e. EKF2 sat on the shifted position (it rejected the fixes for a few seconds, then accepted them) | **HIT** |
| E2 | velocity consistent drift at 1.0 m/s: no EKF2 rejection run of 1 s or longer in at least 3 of 4 runs | 0 of 4 runs had a rejection run of 1 s or longer; EKF2 was carried 55 m at 60 s | **HIT** |
| E3 | arm (a), velocity consistent drift at 1.0 m/s: Marsad detects in at most 2 of 4 runs, arm (b) in 4 of 4 | arm (a) 0 of 4, arm (b) 4 of 4 | **HIT** |
| E4 | jumps of 200 m and 1000 m: Marsad detects in 4 of 4 runs in both arms | 4 of 4 in both arms, at 0.0 to 0.1 s | **HIT** |
| E5 | clean runs: no Marsad alarm in 4 of 4 runs, both arms | 0 of 4 alarms in either arm; no baseline alarm before any onset | **HIT** |
| E6 | arm (a), velocity consistent drift at 0.25 m/s: Marsad detects in at most 1 of 4 runs | 0 of 4 | **HIT** |

What the study shows, beyond the table: when the reference is EKF2's own fused velocity, which the spoofed fixes
drag along, Marsad v1.4.0 detected none of the 16 velocity consistent drift runs at 0.25 to 2.0 m/s, whereas it
detected all 16 with the simulator truth reference. Position only drifts were detected at 0.5, 1.0 and 2.0 m/s in 4 of 4
runs each (median latency 62.0, 34.6 and 19.4 s) and not at 0.25 m/s. The window consistency and stack baselines
gave the same detections as Marsad on position only drifts at 0.5 m/s and above and none on velocity consistent
drifts. The plain gate detected no drift at all. EKF2 itself never rejected a drifting fix for 1 s or longer. Jumps of 50
to 1000 m were detected by every method within 0.1 s, while EKF2 accepted the shifted position after rejecting it for a
few seconds. This is the central limit of the approach and goes into the README headline area: with a reference that
is derived from the same fixes, a velocity consistent carry off is invisible.

Deviation, 2026-11-03: the preregistration said the simulator speed factor "may be raised"; it was raised from 1 to 6,
and one earlier test run at speed 3 (a jump of 200 m, heading 0) was used only to check the pipeline and is not in the
results. A first version of the driver set integer parameters with the wrong bit pattern, so no offset was applied in
the first two test runs; this was found before any scored run and fixed in `scripts/sitl_ekf2_spoof.py`.
