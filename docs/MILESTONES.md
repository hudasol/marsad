# Milestones

Every row is an annotated git tag on the public repository (`git tag -n1` lists them). GitHub Releases exist for
`v1.1.0`, `v1.2.0` and `v1.3.0`.

| tag | commit | content |
|---|---|---|
| `v0.0.1-plan` | `d6b14e1` | docs: add build plan, README and Apache-2.0 license |
| `v0.1.0` | `92de2c9` | v0.1.0: core trust engine, detectors, fusion, state machine, simulator, benchmark harness |
| `v0.3.0` | `c05766b` | v0.3.0: track-trust module, fleet interference map and multi-source track simulator |
| `v0.4.0` | `0e4ff4a` | v0.4.0: PX4 ULog, MAVLink and ROS 2 adapters, synthetic ULog writer, replay/inspect CLI |
| `v0.6.0` | `6156e60` | v0.5.0/v0.6.0: REST+SSE service, MCP server, operator dashboard; serve/mcp CLI |
| `v1.0.0` | `4638548` | docs+eval: held-out evaluation, ablations, detectability sweep, figures, technical report |
| `v1.1.0` | `1f17c9f` | replay delay estimator, reference-quality gate, slow bias estimation, soft-jam tuning, Docker/ROS 2 CI jobs, fresh-seed evaluation |
| `v1.2.0` | `52397e1` | real PX4 log replay (false alarm side), PX4 v1.18 adapter fields, SIH + INJECTED evaluation on two PX4 SIH logs with preregistered predictions and an exploratory diagnosis, `--no-faults` SITL flight, CI fixes (docker and ros2 jobs now pass), proposal seed and review documents |
| `v1.3.0` | last commit of the 2026-10-18 run (`git rev-list -n1 v1.3.0`) | evidence weighting fix for mixed sample rates (preregistered, engine behaviour change), post fix SIH + INJECTED, REAL LOG and SIMULATED results, known limits, bias estimator proposal (not implemented), data checksums and simulator logs as release assets |

## v1.3.0 changelog

* **Engine behaviour change: evidence weighting at mixed sample rates.** Evidence computed once per GNSS fix is now
  scaled by the time since the previous usable fix (capped at 1.5 s) instead of the time since the previous sample of
  any kind. This affects the drift, position/velocity consistency and per fix signal evidence, the persistent offset
  and verified continuity evidence, the reference bias estimator and the anchor smoothing. No threshold or preset
  changed. Predictions were committed first (`docs/PREREGISTRATION_WEIGHTING.md`, commit `5756142`); the change is
  commit `8c7b858`. A new test (`tests/test_mixed_rate.py`) failed on the old code; 143 tests pass.
* **SIH + INJECTED, `sitl1.ulg`, 32 s window:** drifts of 1 and 2 m/s detected 4/4, median 15.7 to 27.8 s
  (v1.2.0: 0/4); 0.5 m/s and slower 0/4; jumps of 50 to 1000 m 4/4 on the first attacked fix. 14 of 14 predictions hit.
* **SIH + INJECTED, `sitl2.ulg`, 230 s window:** drifts of 0.5 to 2 m/s detected 4/4, median 15.7 to 48.3 s at median
  offsets of 18.8 to 22.4 m (v1.2.0: 98.1 to 204.6 s and 77.1 to 186.8 m); 0.25 m/s with honest GNSS velocity 4/4,
  median 113.6 s. 13 of 14 predictions hit.
* **The miss:** 0.25 m/s velocity consistent drift, 0/4 (predicted 4/4), and 0.1 m/s in both modes, 0/4 (predicted).
  The reference bias estimator absorbs part of a velocity consistent drift (`docs/KNOWN_LIMITS.md`). A guard is
  proposed with predictions in `docs/PREREGISTRATION_BIAS.md` and is not implemented.
* **REAL LOG:** both public flights stay TRUSTED for 100% of 911 s and 334 s; the false alarm margin did not shrink
  (minimum P(nominal) 0.966 for flight1, was 0.961; 0.965 for flight2, was 0.960).
* **SIMULATED:** in the tables only soft jamming changed (held out latency 5.0 → 4.6 s, navigation error 11 → 9 m); every
  scenario without fix dropouts is bitwise identical to the previous engine in a same machine control; in the JSON the
  hard jamming recovery time and the obstruction time not TRUSTED also moved slightly (EVALUATION.md).
* **Throughput control (prediction P7e missed).** The published 187.7 µs per sample is a cloud core figure from
  v1.1.0. On a Windows laptop, a same machine control timed both engines alternately at 738.9 to 1,211.5 µs per
  sample (v1.2.0 engine 738.9 to 1,181.8 µs, fixed engine 892.3 to 1,211.5 µs); `run_eval.py` reported 1,263.0 µs on
  the same laptop. The difference is the machine, not the change; the control cannot resolve differences below
  about 10%.
* **Data:** `docs/DATA.md` gives SHA256 checksums and provenance for all four logs; `sitl1.ulg`, `sitl2.ulg` and
  `SHA256SUMS.txt` are attached to this release.
* **Scripts:** `run_eval.py --out` (new results no longer overwrite published ones) with a Windows main guard and
  UTF-8 output; `bias_trace.py`, `clean_margin.py`, `engine_diff.py`, `throughput.py`.
* **Docs:** KNOWN_LIMITS.md, PREREGISTRATION_BIAS.md, DATA.md, REAL_DATA_SOURCES.md; README, ONE_PAGER,
  TECHNICAL_REPORT, EDGE_PROPOSAL and RESUME_BULLET use post fix numbers with the v1.2.0 numbers labelled as before.
* **Not changed:** thresholds, presets, and every published result file of v1.1.0 and v1.2.0 in `docs/results/`.

## v1.2.0 changelog

* **Real PX4 logs (REAL LOG, no attack).** Two public PX4 flights replay end to end with zero Marsad alarms
  (false alarm side only; see VALIDATION.md).
* **PX4 v1.18 support.** The ULog adapter reads the renamed `sensor_gnss` / `vehicle_gnss` topics.
* **SIH + INJECTED evaluation.** `scripts/sih_inject.py` adds a measurement level offset to a real PX4 SIH log and
  scores Marsad and the gate baseline against simulator truth. Predictions were committed before each run
  (`docs/PREREGISTRATION_SIH.md`). Results: jumps detected 4/4 at once; drifts missed in a 32 s window; in a 230 s
  window drifts of 0.5 m/s and faster detected only after 98.1 to 204.6 s (median) and 0.25 m/s or slower missed.
* **Known defect found.** The inertial detector weights evidence by the time since the previous sample of any kind,
  so a fast reference stream dilutes GNSS drift evidence. `scripts/sih_diagnose.py` documents it. It was left
  as it was in this release because fixing it changes engine behaviour and the v1.1.0 results; it is fixed in v1.3.0
  (see the v1.3.0 changelog).
* **Tools.** `scripts/sitl_flight.py --no-faults`, `scripts/sitl_timeline.py`, `scripts/dump_gnss.py`.
* **CI.** The docker smoke test (invalid container name) and the ros2 job (pip in `ros:humble` built an `UNKNOWN`
  wheel) are fixed; all seven jobs pass.
* **Docs.** README status, VALIDATION.md, EDGE_PROPOSAL.md, REVIEW_FINDINGS.md, RUN_LOG.md.
* **No change** to engine behaviour, thresholds, detectors or the v1.1.0 numbers in `docs/results`.
