# Validation status

| Claim | Status |
|---|---|
| Detection logic works against the modelled threats | **Demonstrated in simulation** (docs/EVALUATION.md) |
| Engine runs in real time on a laptop-class CPU | **Measured** (~185 µs/sample; companion-computer class untested) |
| ULog / MAVLink round trip is lossless on synthetic logs | **Tested** (synthetic logs written by this repo) |
| Works on real PX4 logs | **Partly validated (false-alarm side only)**: two public PX4 review logs (v1.15.3 and v1.17.0 multicopters, 911 s and 334 s of GPS) replay end to end with every `sensor_gps` field mapped and zero Marsad alarms. No attack is present in either log, the reference velocity is EKF-fused (contaminated) and neither has C/N0. See "Real-log results" below. Original wording: **NOT validated** — no real log has been run. `sensor_gps` field names checked against PX4's published message docs, **not** against a real log; other topics still from memory (see ADAPTERS.md "known unknowns") |
| Detects attacks injected into a real PX4 SIH log | **Partly (SIH + INJECTED)**: jumps of 50 to 1000 m detected 4/4 at once. Drifts: 0/4 in a 32 s window (sitl1); in a 230 s window (sitl2) 0.5 to 2 m/s detected 4/4 but only after median latencies of 98.1 to 204.6 s and offsets of 77.1 to 186.8 m, and 0.1 and 0.25 m/s missed. A defect in evidence weighting at mixed sample rates is the likely cause. See "SIH + INJECTED results" below |
| Works on a real flight controller | **NOT validated** |
| ROS 2 node | Stub-tested locally; a CI job runs `scripts/ros2_smoke.py` under ROS 2 humble (first result not yet observed) |
| Real GNSS spoofing/jamming data | **NOT used** |
| Dashboard / API / MCP | Tested with the simulator and scripted clients; not security-audited |
| Container image | `Dockerfile` provided; a CI job builds and exercises it (first result not yet observed) |

## Real-log results

Two public logs from review.px4.io (CC-BY), run with `marsad inspect` / `marsad replay`:

* Both parse; `latitude_deg`/`longitude_deg`/`altitude_msl_m`, `vel_n_m_s`, `jamming_state`, `spoofing_state` etc. were found with the current schema.
* Marsad stayed TRUSTED for 100% of both flights (1,245 s of GPS in total).
* In the 911 s log the receiver's own `jamming_state` was 2 (warning) on 7,739 of 9,109 rows. During those rows satellites used (18–21), HDOP (0.57–0.66), eph (~0.8 m), fix type (3) and `noise_per_ms` (82–98 vs 85–97) were indistinguishable from the rows with state 1 (OK); `jamming_indicator` overlapped (22–61 vs 23–44). We read this as a receiver-side warning with no visible effect on position quality, and Marsad correctly did not alarm. This is an interpretation, not ground truth: no one verified the RF environment.
* Not tested by these logs: detection of any real attack, the carry-off check (reference is EKF-fused), the C/N0 detectors (no `satellite_info`), AGC (all zeros in one log; the scaling used for the other is a guess).
* Replay timestamps are vehicle uptime (boot-relative), not time since log start.

## SIH + INJECTED results

**Label: SIH + INJECTED.** A real PX4 v1.18 SIH log (`sitl1.ulg`) with a measurement level position offset added to
the logged GNSS fixes. The PX4 software, its timing and its GNSS stream are real; the vehicle, the receiver and the
reference are simulated. This is not real spoofing and nothing here was received over the air.

Reproduce: `python scripts/sih_inject.py sitl1.ulg --out docs/results/sih_inject.json` (console output in
`docs/results/sih_inject.txt`). Predictions were committed before the run in
[PREREGISTRATION_SIH.md](PREREGISTRATION_SIH.md).

Setup: log cut at 77 s (before the receiver fault at about 78 s), attack from 45 s (32 s window), reference =
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

Reproduce: `python scripts/sih_diagnose.py sitl1.ulg --out docs/results/sih_diagnose.json` (console output in
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

### Long clean flight (sitl2.ulg, 230 s attack window)

**Label: SIH + INJECTED.** `sitl2.ulg` is a second PX4 SIH flight, flown for this purpose with no fault injection:
`scripts/sitl_flight.py --no-faults`, a 300 s square at 5 m/s and 10 m altitude, so the vehicle turns through every
heading every 2 minutes. Before use it was checked with `marsad inspect` and `scripts/sitl_timeline.py sitl2.ulg 10`:
fix type 3 on all 3,212 fixes, GNSS error against ground truth at most 0.30 m (median 0.10 m), and Marsad TRUSTED on
all 51,615 samples (`docs/results/sitl2_timeline.txt`).

Reproduce: `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_inject_long.json`
(console output in `docs/results/sih_inject_long.txt`, about 17 minutes). Predictions were committed before the run
in the addendum of [PREREGISTRATION_SIH.md](PREREGISTRATION_SIH.md). The case list gained 0.1 and 0.25 m/s drifts for
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
beat. In a state trace of the 2 m/s north case the state goes from TRUSTED to DEGRADED at 158.4 s and to DENIED at
159.4 s and stays DENIED until the log is cut (`docs/results/sih_diagnose_long.txt` shows the same case every 4 s).

Exploratory check, same as for sitl1 and again not preregistered:
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

## The path from here

1. **Real-log replay (first priority).** Run `marsad inspect <log.ulg>` on any PX4 log from a real flight (open
   logs exist, e.g. from the PX4 flight review database). Fix field mappings. Check false-alarm rate on genuine
   flights, including GNSS-degraded ones. Success = zero unexplained DENIED events on clean flights.
2. **Real interference logs.** Any logged episode of known jamming/spoofing (with ground truth from a controlled
   test, or a cooperating range). Measure detection latency against the PX4 `jamming_state`/`spoofing_state`
   flags the receiver itself reports.
3. **PX4 SITL in the loop.** Inject measurement-level GNSS faults through the GPS sensor simulation, run the
   MAVLink adapter live, measure latency end to end.
4. **Companion computer, advisory only.** Raspberry Pi / Jetson reading MAVLink from a real autopilot on the
   bench. No closed loop.
5. **Closed loop in a controlled, authorised environment** (an operator or range that is licensed to perform the
   test). Trust state selects the navigation source under a mission policy.
6. **Port the core to C++/Rust** only if the budget requires it.

Nothing beyond step 0 (this repository) is claimed.
