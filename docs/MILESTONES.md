# Milestones

Every row is an annotated git tag on the public repository (`git tag -n1` lists them). GitHub Releases exist for
`v1.1.0` and `v1.2.0`.

| tag | commit | content |
|---|---|---|
| `v0.0.1-plan` | `d6b14e1` | docs: add build plan, README and Apache-2.0 license |
| `v0.1.0` | `92de2c9` | v0.1.0: core trust engine, detectors, fusion, state machine, simulator, benchmark harness |
| `v0.3.0` | `c05766b` | v0.3.0: track-trust module, fleet interference map and multi-source track simulator |
| `v0.4.0` | `0e4ff4a` | v0.4.0: PX4 ULog, MAVLink and ROS 2 adapters, synthetic ULog writer, replay/inspect CLI |
| `v0.6.0` | `6156e60` | v0.5.0/v0.6.0: REST+SSE service, MCP server, operator dashboard; serve/mcp CLI |
| `v1.0.0` | `4638548` | docs+eval: held-out evaluation, ablations, detectability sweep, figures, technical report |
| `v1.1.0` | `1f17c9f` | replay delay estimator, reference-quality gate, slow bias estimation, soft-jam tuning, Docker/ROS 2 CI jobs, fresh-seed evaluation |
| `v1.2.0` | last commit of the 2026-10-17 run (`git rev-list -n1 v1.2.0`) | real PX4 log replay (false alarm side), PX4 v1.18 adapter fields, SIH + INJECTED evaluation on two PX4 SIH logs with preregistered predictions and an exploratory diagnosis, `--no-faults` SITL flight, CI fixes (docker and ros2 jobs now pass), proposal seed and review documents |

## v1.2.0 changelog

* **Real PX4 logs (REAL LOG, no attack).** Two public PX4 flights replay end to end with zero Marsad alarms
  (false alarm side only; see VALIDATION.md).
* **PX4 v1.18 support.** The ULog adapter reads the renamed `sensor_gnss` / `vehicle_gnss` topics.
* **SIH + INJECTED evaluation.** `scripts/sih_inject.py` adds a measurement level offset to a real PX4 SIH log and
  scores Marsad and the gate baseline against simulator truth. Predictions were committed before each run
  (`docs/PREREGISTRATION_SIH.md`). Results: jumps detected 4/4 at once; drifts missed in a 32 s window; in a 230 s
  window drifts of 0.5 m/s and faster detected only after 98.1 to 204.6 s (median) and 0.25 m/s or slower missed.
* **Known defect found.** The inertial detector weights evidence by the time since the previous sample of any kind,
  so a fast reference stream dilutes GNSS drift evidence. `scripts/sih_diagnose.py` documents it. Not fixed in this
  release because fixing it changes engine behaviour and the v1.1.0 results.
* **Tools.** `scripts/sitl_flight.py --no-faults`, `scripts/sitl_timeline.py`, `scripts/dump_gnss.py`.
* **CI.** The docker smoke test (invalid container name) and the ros2 job (pip in `ros:humble` built an `UNKNOWN`
  wheel) are fixed; all seven jobs pass.
* **Docs.** README status, VALIDATION.md, EDGE_PROPOSAL.md, REVIEW_FINDINGS.md, RUN_LOG.md.
* **No change** to engine behaviour, thresholds, detectors or the v1.1.0 numbers in `docs/results`.
