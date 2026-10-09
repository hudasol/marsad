# Validation status

| Claim | Status |
|---|---|
| Detection logic works against the modelled threats | **Demonstrated in simulation** (docs/EVALUATION.md) |
| Engine runs in real time on a laptop-class CPU | **Measured** (~185 µs/sample; companion-computer class untested) |
| ULog / MAVLink round trip is lossless on synthetic logs | **Tested** (synthetic logs written by this repo) |
| Works on real PX4 logs | **Partly validated (false-alarm side only)**: two public PX4 review logs (v1.15.3 and v1.17.0 multicopters, 911 s and 334 s of GPS) replay end to end with every `sensor_gps` field mapped and zero Marsad alarms. No attack is present in either log, the reference velocity is EKF-fused (contaminated) and neither has C/N0. See "Real-log results" below. Original wording: **NOT validated** — no real log has been run. `sensor_gps` field names checked against PX4's published message docs, **not** against a real log; other topics still from memory (see ADAPTERS.md "known unknowns") |
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
