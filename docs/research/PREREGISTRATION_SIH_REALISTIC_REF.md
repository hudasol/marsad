# Preregistration: SIH flights with an imperfect reference

Written on 2026-11-03 (UTC+4), before any run of this study. Label for every number here: **SIH + INJECTED**, with the
reference replaced by simulator truth plus an error model. The flights are the four clean runs of the SITL EKF2 study
(`PREREGISTRATION_SITL_EKF2.md`, runs `clean_h0` to `clean_h270`, same PX4 build, no offset); no earlier SIH log is
used because `sitl1.ulg` and `sitl2.ulg` are not in this environment.

## Question

In the earlier SIH + INJECTED studies the reference was the simulator's exact velocity plus 0.1 m/s of noise, which
flatters every method. How do detection and false alarms of v1.4.0 change when the reference carries the kinds of
error a real visual or optical flow source has: bias, drift, scale error, noise, dropouts and latency?

## Where the world is synthetic

The vehicle, receiver, truth and the attack are simulated (SIH). The reference error models are mine. Their ranges
are partly from the literature and partly assumed, and each row says which.

| model id | error added to the truth velocity | range | source |
|---|---|---|---|
| `exact` | none beyond 0.1 m/s noise (the earlier setup) | | the earlier studies |
| `bias_low` | constant bias vector, random heading | 0.03 m/s | below the preset bound of 0.08 m/s |
| `bias_bound` | constant bias vector | 0.096 m/s (1.2 times the bound) | the bound is the preset `ref_bias_bound` |
| `bias_high` | constant bias vector | 0.15 m/s | above the bound (ASSUMED stress) |
| `bias_vhigh` | constant bias vector | 0.30 m/s | above the bound (ASSUMED stress) |
| `walk` | random walk bias, 0.002 m/s per root second | reaches about 0.03 m/s after 240 s | ASSUMED |
| `scale_vio` | velocity scaled by 1.0 + 0.0236 (random sign) | drift of 0.29% to 2.36% of path length | Qin, Li, Shen, "VINS-Mono", Sec. IX (0.29% on a 62 m MAV loop, 0.88% without loop closure on 700 m, 2.36% for OKVIS) |
| `scale_flow` | velocity scaled by 1.0 + 0.05 (random sign) | 5% | ASSUMED; I found no number in the PX4 documentation page that I could open |
| `realistic` | bias 0.03 m/s, walk, scale 1%, noise 0.15 m/s, dropouts of 2 to 10 s about every 60 s, latency 0.1 s | | combination; dropouts and latency ASSUMED |

The VINS-Mono paper was opened at <https://arxiv.org/pdf/1708.03852> on 2026-11-03.

## Design

* Four clean SIH flights (240 s of square flight at 5 m/s, 8 Hz GNSS, EKF2 inside PX4). The reference is replaced by
  `vehicle_local_position_groundtruth` velocity, decimated to 20 Hz to bound run time (declared; the engine does not
  depend on the reference rate, as shown in `docs/results/sih_diagnose.json`), then the error model is applied.
* Per model and per flight (heading k of the flight is its own heading, so n is 4 per cell): no attack, a
  velocity consistent drift at 0.5 and 1.0 m/s, a position only drift at 1.0 m/s, and a 200 m jump. Onset at 60 s of
  square flight.
* Methods: Marsad v1.4.0 (`uav_multirotor`), plus the plain gate, `ekf2_gate_ref` and `window` baselines.
* Metrics: false alarm (any non TRUSTED sample before the onset, or in the whole flight when there is no attack),
  detection in the 180 s after the onset, latency, offset at alarm. n is 4 per cell; intervals are Clopper Pearson and
  are wide, which is stated wherever a share is quoted. No comparison is claimed from a single cell.
* Number of primary comparisons: 5 (below).

## Predictions

| id | prediction |
|---|---|
| M1 | `exact`, `bias_low`, `bias_bound`: no non TRUSTED sample in any of the 4 no attack flights |
| M2 | `bias_high` and `bias_vhigh`: a false alarm in at least 3 of 4 no attack flights for each (the bias exceeds the bound). This can fail only if the bias estimator absorbs it |
| M3 | velocity consistent drift at 1.0 m/s with `bias_bound`: detected in at least 3 of 4 flights |
| M4 | `scale_vio`: no false alarm in the 4 no attack flights, and velocity consistent drift at 1.0 m/s detected in at least 3 of 4 |
| M5 | `realistic`: at least one false alarm in the 4 no attack flights (dropouts and latency are outside what the engine was built for) |

## Risks named in advance

* Four flights per cell; any share is one of 0, 0.25, 0.5, 0.75, 1.
* The four flights share one flight pattern and one PX4 build.

## Kill criteria

None; this is a measurement. A cell that fails its prediction is reported as a miss.

## Outcome

Empty until scored.
