# Validation status

| Claim | Status |
|---|---|
| Detection logic works against the modelled threats | **Demonstrated in simulation** (docs/EVALUATION.md) |
| Engine runs in real time on a laptop-class CPU | **Measured** (v1.3.0 engine: 892.3 to 1,263.0 µs/sample on a Windows laptop, `docs/results/weighting_fix/throughput*.{json,txt}`; v1.1.0 engine: 187.7 µs on one cloud core, `docs/results/throughput.json`; companion-computer class untested) |
| ULog / MAVLink round trip is lossless on synthetic logs | **Tested** (synthetic logs written by this repo) |
| Works on real PX4 logs | **Partly validated (false-alarm side only)**: two public PX4 review logs (v1.15.3 and v1.17.0 multicopters, 911 s and 334 s of GPS) replay end to end with every `sensor_gps` field mapped and zero Marsad alarms. No attack is present in either log, the reference velocity is EKF-fused (contaminated) and neither has C/N0. Reproduce: `marsad replay flight1.ulg` and `marsad replay flight2.ulg` (output in `docs/results/real_logs.txt`). See "Real-log results" below. |
| Detects attacks injected into a PX4 SIH log | **Partly (SIH + INJECTED)**, v1.4.0 engine, 230 s window (sitl2): jumps of 50 to 1000 m detected 4/4 at once; drifts of 0.25 m/s and faster detected 4/4 in both velocity modes, median 113.6 s at 0.25 m/s, 42.5 s at 0.5 m/s, 25.5 s at 1 m/s, 15.8 s at 2 m/s, offsets at alarm 18.7 to 27.1 m; 0.1 m/s missed. In the 32 s window (sitl1) only 1 and 2 m/s drifts are detected. See "Prior bound channel and baselines (v1.4.0)" below |
| Compared with reference detectors | **Done for SIMULATED and SIH + INJECTED** with reimplemented baselines (EKF2 style gate, window consistency, signal monitor). A plain window test is faster on drift and false alarms more; Marsad holds a far smaller navigation error after a jump or replay. `docs/BASELINES.md`. No baseline was run in PX4 itself and none was scored on a REAL LOG |
| Works on a real flight controller | **NOT validated** |
| ROS 2 node | A CI job runs `scripts/ros2_smoke.py` with a real rclpy runtime under ROS 2 humble on synthetic messages; it passes since 2026-10-17. Never run on a robot |
| Real GNSS spoofing/jamming data | **NOT used** |
| Dashboard / API / MCP | Tested with the simulator and scripted clients; not security-audited |
| Container image | A CI job builds the `Dockerfile` and smoke tests the API in it; it passes since 2026-10-17 |

## Real-log results

Two public logs from review.px4.io (CC-BY), run with `marsad inspect` / `marsad replay`:

* Both parse; `latitude_deg`/`longitude_deg`/`altitude_msl_m`, `vel_n_m_s`, `jamming_state`, `spoofing_state` etc. were found with the current schema.
* Marsad stayed TRUSTED for 100% of both flights (1,245 s of GPS in total).
* In the 911 s log the receiver's own `jamming_state` was 2 (warning) on 7,739 of 9,109 rows. During those rows satellites used (18 to 21), HDOP (0.57 to 0.66), eph (about 0.8 m), fix type (3) and `noise_per_ms` (82 to 98 vs 85 to 97) were indistinguishable from the rows with state 1 (OK); `jamming_indicator` overlapped (22 to 61 vs 23 to 44). These row level figures were read from the log when the replay was first done and are not stored in `docs/results`; `docs/results/real_logs.txt` records 774 s with the PX4 flag raised while Marsad stayed TRUSTED. We read this as a receiver-side warning with no visible effect on position quality, and Marsad correctly did not alarm. This is an interpretation, not ground truth: no one verified the RF environment.
* Not tested by these logs: detection of any real attack, the carry-off check (reference is EKF-fused), the C/N0 detectors (no `satellite_info`), AGC (all zeros in one log; the scaling used for the other is a guess).
* Replay timestamps are vehicle uptime (boot-relative), not time since log start.

## SIH + INJECTED results

**Label: SIH + INJECTED.** A real PX4 v1.18 SIH log (`sitl1.ulg`) with a measurement level position offset added to
the logged GNSS fixes. The PX4 software, its timing and its GNSS stream are real; the vehicle, the receiver and the
reference are simulated. This is not real spoofing and nothing here was received over the air.

Reproduce (at tag v1.2.0; the current engine writes post fix results, so use `docs/results/weighting_fix/` paths at HEAD): `python scripts/sih_inject.py sitl1.ulg --out docs/results/sih_inject.json` (console output in
`docs/results/sih_inject.txt`). Predictions were committed before the run in
[PREREGISTRATION_SIH.md](research/PREREGISTRATION_SIH.md).

Disclosure: `scripts/sih_inject.py`, including its sitl1 defaults (`--end 77`, `--t-attack 45`), was committed on
2026-10-11, before the preregistration. The repository does not record whether it had been run on sitl1 before
then. The preregistration therefore guards against tuning during this run (none was done: no threshold, preset or
case was changed for sitl1), not against earlier exposure to the log.

Setup: log cut at 77 s (before the PX4 GPS failure that `sitl_flight.py` injected at about 78 s, a SITL FAULT that is
excluded here), attack from 45 s (32 s window), reference =
`vehicle_local_position_groundtruth` velocity, preset `uav_multirotor`, each case at 4 headings. Latency is from 45 s;
"0.0 s" means the alarm came on the first attacked GNSS fix.

| attack | Marsad detected | Marsad median latency | offset at alarm | gate baseline detected | baseline median latency |
|---|---|---|---|---|---|
| none (clean log) | 0 non TRUSTED samples | | | 0 non TRUSTED samples | |
| drift 0.5 m/s, velocity consistent | 0/4 | | | 0/4 | |
| drift 0.5 m/s, velocity not consistent | 0/4 | | | 0/4 | |
| drift 1.0 m/s, velocity consistent | 0/4 | | | 0/4 | |
| drift 1.0 m/s, velocity not consistent | 0/4 | | | 0/4 | |
| drift 2.0 m/s, velocity consistent | 0/4 | | | 0/4 | |
| drift 2.0 m/s, velocity not consistent | 0/4 | | | 0/4 | |
| jump 50 m | 4/4 | 0.0 s | 50 m | 4/4 | 0.0 s |
| jump 200 m | 4/4 | 0.0 s | 200 m | 4/4 | 0.0 s |
| jump 1000 m | 4/4 | 0.0 s | 1000 m | 4/4 | 0.0 s |

### Against the preregistered predictions

* **Hits (4 of 10 Marsad rows):** no alarm on the clean log; all three jumps detected 4/4 within 1 s.
* **Misses (6 of 10 Marsad rows):** every drift case. I predicted 4/4 with latencies between 2 and 25 s; the result
  was 0/4 in all six, including 2 m/s, where the injected offset reaches about 54 m by the end of the log.
* **Gate baseline: 10 of 10 as predicted** (all drifts missed, all jumps caught).
* The two extra predictions (offset at alarm under 15 m; slower drifts take longer) cannot be scored because no
  drift was detected.

### Why the drifts were missed (exploratory, not preregistered)

Reproduce (at tag v1.2.0): `python scripts/sih_diagnose.py sitl1.ulg --out docs/results/sih_diagnose.json` (console output in
`docs/results/sih_diagnose.txt`). This analysis was done after seeing the miss. The engine was not changed.

* The drift detector does respond. During the 2 m/s drift its z score rises from 0.02 before the attack to 7.31 at
  76 s (the evidence threshold is z = 2), but P(nominal) only falls from 0.961 to 0.919, so the state never leaves
  TRUSTED.
* The likely cause is the sample structure. In this log the reference (groundtruth velocity) arrives as 9,213
  samples at a median gap of 0.008 s and GNSS as 612 samples at a median gap of 0.124 s. The inertial detector
  multiplies its evidence by the time since the previous sample of any kind, about 0.008 s, instead of the time
  since the previous GNSS fix, so drift evidence accrues at roughly 0.008 / 0.124, about 6%, of the intended rate.
  The repository's own simulator puts GNSS and reference in the same 5 Hz sample, which is why the simulated
  evaluation never exposed this.
* As a check of that explanation, the same cases were fed at the GNSS epoch rate only (groundtruth velocity
  attached to each fix, 612 samples). Then Marsad detected 2 m/s drift 4/4 (median 16.3 s velocity consistent,
  15.7 s not consistent) and 1 m/s drift 4/4 (27.6 s and 25.5 s), still missed 0.5 m/s in the 32 s window, and
  raised no alarm on the clean log. The gate baseline stayed at 0/4 for every drift.
* This is a defect in how the engine weights evidence when samples arrive at mixed rates, not a property of the
  method. It matters for any real integration where the reference sensor runs faster than GNSS, which is the
  normal case. Fixing it changes engine behaviour and the published v1.1.0 numbers, so it was left for a separate,
  preregistered change.
* The fix was made after v1.2.0; see "Evidence weighting fix" below. The tables in this section are the v1.2.0
  results and are kept unchanged.

### Long clean flight (sitl2.ulg, 230 s attack window)

**Label: SIH + INJECTED.** `sitl2.ulg` is a second PX4 SIH flight, flown for this purpose with no fault injection:
`scripts/sitl_flight.py --no-faults`, a 300 s square at 5 m/s and about 10 m altitude (simulator truth), so the vehicle turns through every
heading every 2 minutes. Before use it was checked with `marsad inspect` and `scripts/sitl_timeline.py sitl2.ulg 10`:
fix type 3 on all 3,212 fixes, GNSS error against ground truth at most 0.30 m (median 0.10 m), and Marsad TRUSTED on
all 51,615 samples (`docs/results/sitl2_timeline.txt`).

Reproduce (at tag v1.2.0): `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_inject_long.json`
(console output in `docs/results/sih_inject_long.txt`, about 17 minutes). Predictions were committed before the run
in the addendum of [PREREGISTRATION_SIH.md](research/PREREGISTRATION_SIH.md). The case list gained 0.1 and 0.25 m/s drifts for
this run; rerunning the sitl1 command therefore prints two extra rows, and the rows above are unchanged.

| attack | Marsad detected | Marsad median latency | median offset at alarm | gate baseline detected |
|---|---|---|---|---|
| none (clean log) | 0 non TRUSTED samples | | | 0 non TRUSTED samples |
| drift 0.1 m/s, velocity consistent | 0/4 | | | 0/4 |
| drift 0.1 m/s, velocity not consistent | 0/4 | | | 0/4 |
| drift 0.25 m/s, velocity consistent | 0/4 | | | 0/4 |
| drift 0.25 m/s, velocity not consistent | 0/4 | | | 0/4 |
| drift 0.5 m/s, velocity consistent | 4/4 | 204.6 s | 99.8 m | 0/4 |
| drift 0.5 m/s, velocity not consistent | 4/4 | 159.1 s | 77.1 m | 0/4 |
| drift 1.0 m/s, velocity consistent | 4/4 | 112.3 s | 107.3 m | 0/4 |
| drift 1.0 m/s, velocity not consistent | 4/4 | 110.1 s | 105.1 m | 0/4 |
| drift 2.0 m/s, velocity consistent | 4/4 | 98.4 s | 186.8 m | 0/4 |
| drift 2.0 m/s, velocity not consistent | 4/4 | 98.1 s | 186.3 m | 0/4 |
| jump 50 m | 4/4 | 0.0 s | 50.0 m | 4/4 (0.0 s) |
| jump 200 m | 4/4 | 0.0 s | 200.0 m | 4/4 (0.0 s) |
| jump 1000 m | 4/4 | 0.0 s | 1000.0 m | 4/4 (0.0 s) |

Against the addendum predictions:

* **Hits:** clean log silent; 0.1 and 0.25 m/s missed (predicted 0/4); 1.0 m/s detected 4/4 at 110.1 and 112.3 s
  (predicted band 60 to 180 s); 2.0 m/s detected 4/4 at 98.1 and 98.4 s (band 40 to 120 s); jumps 4/4 at once; gate
  baseline as predicted in every row.
* **Miss:** 0.5 m/s was detected 4/4 (159.1 and 204.6 s); I predicted it would stay TRUSTED inside 230 s.

Compared with the 32 s window on sitl1, the longer window turns 0/4 into 4/4 for drifts of 0.5 m/s and faster, which
is consistent with the diagnosis: the evidence does build up, only slowly. The cost is visible in the offset column.
A 2 m/s drift is caught only when the GNSS position is about 187 m from the truth, and latency barely shortens from
1 m/s to 2 m/s, which suggests the diluted evidence accrual sets a floor of roughly 100 s that faster drifts cannot
beat. The 4 s trace of the 2 m/s north case in `docs/results/sih_diagnose_long.txt` shows the state TRUSTED at
155.0 s, DEGRADED at 159.0 s and DENIED from 163.0 s until the log is cut, so the alarm is not a brief transient.

Exploratory check, same as for sitl1 and again not preregistered (at tag v1.2.0):
`python scripts/sih_diagnose.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_diagnose_long.json`. Fed at
the GNSS epoch rate only (2,305 samples), Marsad detects 0.5 m/s drift 4/4 at a median of 48.2 s (velocity consistent)
and 42.5 s (not consistent), 1.0 m/s at 27.2 and 25.5 s, and 2.0 m/s at 16.2 and 15.7 s, with no alarm on the clean
log and the gate baseline at 0/4 throughout. The 1.0 and 2.0 m/s figures agree with the sitl1 exploratory check to
within 0.4 s, which is what one would expect if the evidence weighting, not the flight, sets the latency.

### Limits of this experiment

* **Short window (sitl1).** 32 s of attack. A 0.5 m/s drift has moved only about 14 m by the end. The sitl2 run
  extends the window to 230 s, which is still shorter than the 240 s drift window the engine uses and far shorter
  than the several minutes the simulated evaluation needs for 0.1 m/s.
* **Ideal reference.** Simulator ground truth has no bias, no scale error and no dropouts. Any real visual or
  odometry reference is worse. A positive result here would be an upper bound.
* **Two flights, one vehicle model.** sitl2 flies a full square (all headings); sitl1 was mostly one heading. In sitl1 the vehicle was on the ground until about 16 s, climbed until about 40 s, flew
  north at about 4.6 m/s through most of the attack window and turned east after about 64 s. The 4 headings are
  4 directions of offset on the same flight and the same noise realisation, not 4 independent trials. This holds
  for sitl2 as well.
* **Simulated receiver.** The SIH GNSS model has its own noise; no C/N0, no AGC, no real receiver behaviour.
* **Not real spoofing.** The offset is added to logged numbers. Nothing about how a real receiver reacts to a
  spoofing signal is tested.

## Evidence weighting fix

The defect described in "Why the drifts were missed" was fixed in a separate change after v1.2.0. Predictions were
written and committed first, in [PREREGISTRATION_WEIGHTING.md](research/PREREGISTRATION_WEIGHTING.md) (commit `5756142`),
before any engine code was changed. The engine now scales every piece of evidence that is computed once per GNSS fix
by the time since the previous usable fix (`gnss_dt`, capped at 1.5 s) instead of the time since the previous sample
of any kind. The same defect was found and fixed in the kinematic position/velocity consistency evidence, the per fix
signal evidence, the engine's persistent offset and verified continuity evidence, the reference bias estimator and
the anchor smoothing; the full list is in the preregistration. No threshold or preset was changed.
`tests/test_mixed_rate.py` feeds one synthetic flight co-sampled at 5 Hz and interleaved with a 100 Hz reference; on
the old code the interleaved 2 m/s drift was never detected, on the new code it is detected at 15.8 s against 16.2 s
co-sampled. All 143 tests pass (140 existing, unmodified, and 3 new). The simulated evaluation is reported in
[EVALUATION.md](EVALUATION.md).

Results are in `docs/results/weighting_fix/`. The v1.2.0 files in `docs/results/` are unchanged. Two files in that
folder (`clean_margin.txt` and `engine_diff_heldout_fixed.json`) record the package version as 1.2.0 because they
were produced before the version string was raised to 1.3.0; the engine code in them is the fixed one.

### SIH + INJECTED, sitl1.ulg (32 s window)

**Label: SIH + INJECTED.** Reproduce: `python scripts/sih_inject.py sitl1.ulg --out docs/results/weighting_fix/sih_inject.json`
(console output in `docs/results/weighting_fix/sih_inject.txt`).

| attack | v1.2.0 | predicted | after the fix | median offset at alarm | hit |
|---|---|---|---|---|---|
| none (clean log) | 0 non TRUSTED | 0 | 0 non TRUSTED samples | | yes |
| drift 0.1 m/s (both modes) | 0/4 | 0/4 | 0/4 | | yes, yes |
| drift 0.25 m/s (both modes) | 0/4 | 0/4 | 0/4 | | yes, yes |
| drift 0.5 m/s (both modes) | 0/4 | 0/4 | 0/4 | | yes, yes |
| drift 1.0 m/s, velocity consistent | 0/4 | 4/4, 20 to 32 s | 4/4, 27.8 s | 22.8 m | yes |
| drift 1.0 m/s, velocity not consistent | 0/4 | 4/4, 18 to 32 s | 4/4, 25.5 s | 20.5 m | yes |
| drift 2.0 m/s, velocity consistent | 0/4 | 4/4, 11 to 22 s | 4/4, 16.3 s | 22.6 m | yes |
| drift 2.0 m/s, velocity not consistent | 0/4 | 4/4, 11 to 22 s | 4/4, 15.7 s | 21.3 m | yes |
| jump 50, 200, 1000 m | 4/4, 0.0 s | 4/4, under 1 s | 4/4, 0.0 s | 50, 200, 1000 m | yes |

### SIH + INJECTED, sitl2.ulg (230 s window)

**Label: SIH + INJECTED.** Reproduce:
`python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/weighting_fix/sih_inject_long.json`
(console output in `docs/results/weighting_fix/sih_inject_long.txt`, 16 minutes).

| attack | v1.2.0 | predicted | after the fix | median offset at alarm | hit |
|---|---|---|---|---|---|
| none (clean log) | 0 non TRUSTED | 0 | 0 non TRUSTED samples | | yes |
| drift 0.1 m/s (both modes) | 0/4 | 0/4 | 0/4 | | yes, yes |
| drift 0.25 m/s, velocity consistent | 0/4 | 4/4, 70 to 200 s | **0/4** | | **no** |
| drift 0.25 m/s, velocity not consistent | 0/4 | 4/4, 70 to 200 s | 4/4, 113.6 s | 27.1 m | yes |
| drift 0.5 m/s, velocity consistent | 4/4, 204.6 s | 4/4, 35 to 70 s | 4/4, 48.3 s | 21.7 m | yes |
| drift 0.5 m/s, velocity not consistent | 4/4, 159.1 s | 4/4, 30 to 65 s | 4/4, 42.5 s | 18.8 m | yes |
| drift 1.0 m/s, velocity consistent | 4/4, 112.3 s | 4/4, 20 to 40 s | 4/4, 27.3 s | 22.3 m | yes |
| drift 1.0 m/s, velocity not consistent | 4/4, 110.1 s | 4/4, 18 to 38 s | 4/4, 25.5 s | 20.5 m | yes |
| drift 2.0 m/s, velocity consistent | 4/4, 98.4 s | 4/4, 11 to 25 s | 4/4, 16.2 s | 22.4 m | yes |
| drift 2.0 m/s, velocity not consistent | 4/4, 98.1 s | 4/4, 11 to 25 s | 4/4, 15.7 s | 21.4 m | yes |
| jump 50, 200, 1000 m | 4/4, 0.0 s | 4/4, under 1 s | 4/4, 0.0 s | 50, 200, 1000 m | yes |

Against the preregistration:

* **P1 (sitl1): 14 of 14 Marsad rows hit. P2 (sitl2): 13 of 14 hit, 1 miss** (0.25 m/s, velocity consistent).
* **P3 hit:** median offset at alarm 18.8 to 22.8 m for every detected drift of 0.5 m/s and faster (v1.2.0: 77.1 to
  186.8 m).
* **P4 hit:** latency is ordered 0.25 > 0.5 > 1.0 > 2.0 m/s in each velocity mode, among the detected cases.
* **P5 hit:** the gate baseline is identical to v1.2.0 in every row of both logs.
* The latencies agree with the exploratory GNSS epoch rate feed of v1.2.0 (`sih_diagnose*.txt`) to within 0.2 s in
  every case that feed detected, as the preregistration argued they should.

**Why 0.25 m/s velocity consistent was missed (exploratory, post hoc).** Reproduce:
`python scripts/bias_trace.py sitl2.ulg` (output in `docs/results/weighting_fix/bias_trace_sitl2.txt`). While the
drift z score is below 1, the engine keeps learning the reference velocity bias by comparing the reference velocity
with the GNSS velocity. A velocity consistent spoofer shifts the GNSS velocity together with the position, so the
estimator learned a northward bias of -0.087 m/s, 34.8% of the 0.25 m/s drift, before the z score passed 1 between
95 and 115 s. Integrating the bias corrected reference then hides that part of the drift, and the peak z score stayed
at 1.80, below the evidence threshold of 2. In the velocity not consistent mode the GNSS velocity is honest, the
estimate stayed at 0.000 m/s north and the drift was caught. The trace also shows that the estimator had only 47 s
of learning when it stopped, short of the 150 s that enables the tighter bias bound, because it learns only on fixes
that share a sample with the reference (1,145 of 2,305 fixes in this log). Both effects were named as risks in the
preregistration. They are properties of the bias estimator, not of the weighting fix, and are left for a separate
change.

### REAL LOG replays and false alarm margin

**Label: REAL LOG** (flight1, flight2: unmodified public PX4 flights, no attack, EKF fused reference).
Reproduce: `marsad replay flight1.ulg --json docs/results/weighting_fix/real_flight1.json` and the same for
`flight2.ulg` (console output in `docs/results/weighting_fix/real_logs.txt`).

**P6 hit:** Marsad stays TRUSTED for 100% of both flights (911 s and 334 s), as in v1.2.0, although GNSS driven
evidence now accrues about 10 times faster on these logs.

`python scripts/clean_margin.py` (output in `docs/results/weighting_fix/clean_margin.txt`) measures how close the
engine comes to leaving TRUSTED on the four clean logs, with the v1.2.0 engine and with the fixed engine. The sitl rows
are SIH logs without any injection.

| log | label | min P(nominal), v1.2.0 | min P(nominal), fixed | max drift z, v1.2.0 | max drift z, fixed |
|---|---|---|---|---|---|
| sitl1.ulg (to 77 s) | SIH + INJECTED (zero offset) | 0.960 | 0.965 | 0.03 | 0.03 |
| sitl2.ulg (to 290 s) | SIH + INJECTED (zero offset) | 0.960 | 0.966 | 0.08 | 0.08 |
| flight1.ulg | REAL LOG | 0.961 | 0.966 | 1.17 | 1.18 |
| flight2.ulg | REAL LOG | 0.960 | 0.965 | 0.25 | 0.25 |

DEGRADED starts below P(nominal) 0.5 and drift evidence accrues above z = 2. The margin did not shrink: the
"GNSS agrees with the reference" evidence also accrues at its intended rate now, which keeps P(nominal) slightly
higher. This is still the false alarm side only; the flights contain no attack and their reference is contaminated.

## Prior bound channel and baselines (v1.4.0)

**Labels: SIMULATED, SIH + INJECTED.** The change and its predictions were committed before any engine code
([research/PREREGISTRATION_PRIOR_BOUND.md](research/PREREGISTRATION_PRIOR_BOUND.md)); the outcome table there lists
ten hits, three misses (two of them on rows that improved) and one row not scored.

* The velocity consistent 0.25 m/s drift on `sitl2.ulg`, missed by v1.3.0, is detected 4/4 with a median of 113.6 s
  (`docs/results/prior_bound/sih_inject_long.txt`). 0.1 m/s is still missed, as predicted.
* SIMULATED held out results are unchanged in detection and latency; `spoof_drift_stealth` is 58.0 s (58.3 s before).
  Nominal and obstruction runs reach DENIED in 0% of runs and multipath in 3%
  (`docs/results/prior_bound/heldout.md`).
* One detectability cell got worse: reference bias 0.08 m/s, drift 0.15 m/s, 100% to 94% (15 of 16 runs).
* Engine cost on one cloud core: 243 us per sample (`docs/results/prior_bound/throughput.json`; a different machine
  from the Windows laptop figures above, so the two are not comparable).
* Not run: REAL LOG replay of the v1.4.0 engine. `marsad replay flight1.ulg` and `flight2.ulg` still need to be run
  by the author, who holds the files.

## The path from here

1. **Detection gaps** are ranked in [ROADMAP.md](ROADMAP.md). Real-log replay on clean flights is done (two logs, v1.3.0
   engine); more logs, including GNSS degraded ones, and a replay of the v1.4.0 engine are still needed.
2. **Real interference logs.** Any logged episode of known jamming/spoofing (with ground truth from a controlled
   test, or a cooperating range). Measure detection latency against the PX4 `jamming_state`/`spoofing_state`
   flags the receiver itself reports.
3. **PX4 SITL in the loop.** Offline SIH logs are done (above). Still to do: run the MAVLink adapter live against
   SITL and measure latency end to end.
4. **Companion computer, advisory only.** Raspberry Pi / Jetson reading MAVLink from a real autopilot on the
   bench. No closed loop.
5. **Closed loop in a controlled, authorised environment** (an operator or range that is licensed to perform the
   test). Trust state selects the navigation source under a mission policy.
6. **Port the core to C++/Rust** only if the budget requires it.

Nothing beyond what the tables above report is claimed.
