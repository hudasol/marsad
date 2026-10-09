# Validation status

| Claim | Status |
|---|---|
| Detection logic works against the modelled threats | **Demonstrated in simulation** (docs/EVALUATION.md) |
| Engine runs in real time on a laptop-class CPU | **Measured** (46 µs/sample; companion-computer class untested) |
| ULog / MAVLink round trip is lossless on synthetic logs | **Tested** (synthetic logs written by this repo) |
| Works on real PX4 logs | **NOT validated** — no real log has been run. Field names and units are from public docs and memory (see ADAPTERS.md "known unknowns") |
| Works on a real flight controller | **NOT validated** |
| ROS 2 node | **Stub-tested only**; never run under rclpy |
| Real GNSS spoofing/jamming data | **NOT used** |
| Dashboard / API / MCP | Tested with the simulator and scripted clients; not security-audited |
| Container image | `Dockerfile` provided; see MILESTONES.md for whether it was built |

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
