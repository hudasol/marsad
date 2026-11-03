# Preregistration: attacks injected into real flights

Written on 2026-11-03 (UTC+4), before any injection was run on the real corpus. The clean replay of the corpus
(`PREREGISTRATION_REAL_CORPUS.md`) was started before this file but its engine output had not been used to set any
number below. Label for every number here: **REAL LOG + INJECTED**. The flights, their GNSS noise, timing, dropouts
and receiver quirks are real. The attacks are position and velocity offsets added to the logged fixes by the same
generators as `scripts/sih_inject.py`. Nothing is transmitted and no RF is generated.

## Question

On real PX4 flights, how often and how quickly does v1.4.0 Marsad leave TRUSTED after a GNSS position jump or a
carry off drift is injected, compared with the baselines of `docs/BASELINES.md`, and how far has the vehicle been
carried by then?

## Where the world is synthetic, and who wrote what

* The attack is synthetic: a single constant offset (jump) or a ramp then constant rate offset (drift). It is not a
  recording of a spoofer. Real receivers under a real attack may behave differently (lock transitions, C/N0 changes,
  satellite count changes) and none of that is represented here.
* The method (Marsad) and the attack generators share an author. The generators are the ones that were used in
  `docs/results/sih_inject.json`; they are not tuned further here.
* The reference arm (a) is optimistic. The logged EKF2 velocity was computed from the original, uninjected GNSS, so
  it does not follow the injected offset. In a real attack the EKF2 would fuse the spoofed fixes and its velocity
  would be dragged along (this is the contamination described in `docs/KNOWN_LIMITS.md`). Arm (a) is therefore an
  upper bound on detection from the reference check and is labelled that way wherever it is used.

## Data and seeds

* Flights: the scoring set of the real corpus (design subset excluded), restricted to flights with at least 300 s of
  fixes of type 3 or better and with a clean start: no non TRUSTED Marsad sample in the 30 s before the onset in the
  uninjected replay (flights that fail this are counted and listed, and are excluded from the detection denominators
  of every method). Expected n: 40 to 80 flights. If fewer than 40 flights qualify, the result is reported as
  underpowered and no interval is narrowed by pooling.
* Onset: drawn uniformly between 30% and 60% of the scored span, from a generator seeded with
  `sha256(log_id + case + heading)`. The attack lasts until the end of the log, which is at least 120 s.
* Cases: jump of 50 m, 200 m, 1000 m; drift at 0.25, 0.5, 1.0, 2.0 m/s with a 10 s ramp, each in two velocity
  modes (velocity consistent, where the same rate is added to the receiver velocity, and position only). Four
  headings (0, 90, 180, 270 degrees). That is 44 injections per flight.
* Reference arms, never pooled: (a) the logged EKF fused velocity, the upper bound described above; (b) an
  independent reference (optical flow, visual odometry or wheel odometry from the manifest) on the flights that
  carry one. Arm (b) is reported with its own n and is expected to be small.
* Presets: `uav_multirotor` for multirotors, `uav_fixedwing` for fixed wing and VTOL, as in the clean replay.

## Metrics

* Detection: the first sample at or after the onset that is not TRUSTED (Marsad) or not TRUSTED (baseline). The unit
  is the flight: a flight counts as detected for a case if at least 3 of the 4 headings are detected (a majority
  rule fixed here); the per injection counts are also stored. Proportions carry Clopper Pearson 95% intervals.
* Latency: seconds from onset to detection, median over detected flights, with a 95% bootstrap interval (10,000
  resamples over flights, fixed seed 20261103).
* Offset at alarm: the injected offset in metres at the moment of the first alarm (the distance the vehicle's
  position solution has already been carried).
* Position handed to the vehicle: the share of detected injections where Marsad was DENIED (no position offered)
  at the first alarm versus DEGRADED.
* False alarms before onset: flights with any non TRUSTED sample between the start and the onset, per method.
* Paired comparison with each baseline: exact McNemar test on per flight detection, per case family.
* By hardware and PX4 release minor version: counts only, descriptive.
* Number of primary comparisons: 9 (the predictions below). Everything else is exploratory.

## Baselines

Simple baseline: the plain gate (`gate`). Competitor: `ekf2_gate_ref` (EKF2 style innovation gate with the
reference check) and `window` (window consistency), plus `stack` (any of the three). All as in `docs/BASELINES.md`.

## Predictions

| id | prediction (arm a, scoring set) |
|---|---|
| J1 | jump of 200 m and of 1000 m: Marsad detects in at least 95% of flights (each) |
| J2 | jump of 50 m: Marsad detects in at least 80% of flights. This can fail: 50 m is close to the noise gates on poor receivers |
| D1 | velocity consistent drift at 1.0 m/s and 2.0 m/s: Marsad detects in at least 70% of flights, median latency under 60 s |
| D2 | position only drift at 0.5 m/s: Marsad detects in at least 70% of flights. This can fail through the receiver velocity noise on some boards |
| D3 | velocity consistent drift at 0.25 m/s: Marsad detects in fewer than 50% of flights within the remaining flight. This is a prediction of a limit |
| C1 | the window consistency baseline detects fewer velocity consistent drifts at 0.5 m/s than Marsad by at least 30 percentage points |
| C2 | the plain gate detects 0% of velocity consistent drifts at 1.0 m/s (it does not see slow drift) |
| F1 | at most 10% of flights have any Marsad alarm before onset (a restatement of the clean replay on this subset) |
| O1 | median offset at alarm for the 1.0 m/s position only drift is under 60 m |

## Risks named in advance

* Flights from receivers at 1 Hz or with long gaps may show alarms before onset (see Amendment 2 of the corpus
  preregistration). They are excluded from the denominators as stated, and counted.
* Mixed detection by hardware: a few boards with unusual velocity noise may dominate the misses.
* Runtime: 44 injections per flight on every method may be too slow on one worker. If so, the per flight set of
  injections is run in a fixed order and stopped at a wall clock budget; the number of flights completed is stated.
  No flight is skipped selectively.

## Kill criteria

None; this is a measurement. A missed prediction is reported with its cause.

## Outcome

Scored 2026-11-03 (UTC+4) from `docs/results/real_injected/summary.json` and `summary.md`, engine v1.4.0 behaviour.
Label: **REAL LOG + INJECTED**. The two reference arms are reported separately and never pooled.

Population. 101 scoring flights were run. 24 had less than 300 s of fixes of type 3 or better, 2 had no reference for the
independent arm, and **23 of the remaining 75 (31%) were not TRUSTED in the 30 s before the earliest onset in the
uninjected replay** and were excluded as designed. This is the real flight false alarm problem showing up as a loss of
test flights: the detection numbers below are for the 52 flights on which Marsad starts out trusted. Arm (a), the logged
EKF fused velocity, has n = 52. Arm (b), an independent reference, has n = 2 scored flights (6 run), so it supports no
claim and is not interpreted.

Arm (a) is an optimistic upper bound for every method that uses the reference: the logged velocity came from the
uninjected fixes and does not follow the injected offset. SITL EKF2 (see `PREREGISTRATION_SITL_EKF2.md`) is the study
in which the reference is dragged.

| Row | Result (arm a, n = 52) | Verdict |
|---|---|---|
| J1 | jump 200 m: 52 of 52 (95% interval 93% to 100%); jump 1000 m: 52 of 52 | HIT |
| J2 | jump 50 m: 52 of 52 | HIT |
| D1 | velocity consistent drift 1.0 m/s: 52 of 52, median latency 25.5 s; 2.0 m/s: 52 of 52, 15.7 s | HIT |
| D2 | position only drift 0.5 m/s: 52 of 52, median latency 41.9 s | HIT |
| D3 | velocity consistent drift 0.25 m/s: 45 of 52 (87%, interval 74% to 94%), median latency 111.8 s; predicted fewer than 50% | MISS |
| C1 | window detects 52 of 52 at 0.5 m/s velocity consistent, Marsad 52 of 52; predicted a gap of at least 30 points | MISS |
| C2 | plain gate detects 2 of 52 at 1.0 m/s velocity consistent (4%); predicted 0 | MISS (by two flights) |
| F1 | Marsad alarm before onset in 2 of 52 scored flights (4%), at most 10% predicted | HIT, but carried by the exclusion above |
| O1 | position only drift 1.0 m/s: median offset at alarm 20 m, under 60 m | HIT |

Reading. D3 and C1 are the interesting misses. On real flight logs with a logged (uncontaminated) reference Marsad
detects 0.25 m/s drift far more often than predicted, and the simple window test detects everything Marsad does and
sooner: median latency 57.6 s against 111.8 s at 0.25 m/s, 31.6 s against 42.3 s at 0.5 m/s, 18.5 s against 25.5 s at
1.0 m/s, 12.0 s against 15.7 s at 2.0 m/s (velocity consistent). The paired test at 0.25 m/s favours the window test
(exact McNemar p 0.016, 7 flights detected by the window test only, none by Marsad only). The window test is not
evaluated for false alarms on the 23 excluded flights; its pre onset alarm count on the 52 scored flights is 3, against 2
for Marsad. Marsad's value over the window test on this study is therefore not detection speed; it is classification and
a fallback position, neither of which this study measures. Comparisons: nine preregistered rows, with every other
cell in `summary.md` exploratory (about 90 McNemar tests were computed; they are not corrected and are descriptive).

The EKF2 style gate with the reference check (`ekf2_gate_ref`) detects 3 of 52 at 0.25 m/s and 48 of 52 at 0.5 m/s, with
a median latency of 80 s, and is the closest to the vehicle's own behaviour among the baselines. With a reference that
does not follow the spoofed fixes it detects drift of 1.0 m/s and above in nearly every flight.
