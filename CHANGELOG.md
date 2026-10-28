# Changelog

All notable changes to Marsad. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/). Result labels (SIMULATED, REAL LOG, SIH + INJECTED,
SITL FAULT) are explained in [docs/VALIDATION.md](docs/VALIDATION.md).

## [Unreleased]

### Added
* Comparison baselines in `marsad.bench.baselines`: an EKF2 style gate (PX4 documented defaults), a sliding window
  INS/GNSS consistency test, a receiver power monitor and their union, each with and without access to the
  independent reference where that matters. Scored on held out SIMULATED scenarios and on injected SIH attacks
  ([docs/BASELINES.md](docs/BASELINES.md)).
* `scripts/calibrate_baselines.py`, `scripts/run_baselines.py`, `scripts/sih_baselines.py`.

### Changed
* The drift detector also tests the uncorrected reference integral against the prior bias bound
  ([docs/PREREGISTRATION_PRIOR_BOUND.md](docs/PREREGISTRATION_PRIOR_BOUND.md)).
* `marsad.bench.baseline` is now `marsad.bench.baselines` (`GateBaseline` is unchanged and still exported from
  `marsad.bench`).

## [1.3.0] - 2026-10-18

### Fixed
* Evidence weighting at mixed sample rates. Per fix evidence is scaled by the time since the previous usable fix
  (capped at 1.5 s), not by the time since the previous sample of any kind. With a 125 Hz reference and 8 Hz GNSS,
  drift evidence had accrued at about 6% of its intended rate. Preregistered
  ([docs/PREREGISTRATION_WEIGHTING.md](docs/PREREGISTRATION_WEIGHTING.md)); regression test `tests/test_mixed_rate.py`.

### Added
* `docs/KNOWN_LIMITS.md`, `docs/DATA.md` (checksums and provenance), simulator logs as release assets.
* `scripts/bias_trace.py`, `clean_margin.py`, `engine_diff.py`, `throughput.py`; `run_eval.py --out`.

### Results
* SIH + INJECTED: drifts of 0.5 m/s and faster detected in 15.7 to 48.3 s at 18.8 to 22.4 m median offset (was 98.1
  to 204.6 s). 27 of 28 preregistered rows hit; the miss is a velocity consistent 0.25 m/s drift.

## [1.2.0] - 2026-10-18

### Added
* Real PX4 log replay, false alarm side (REAL LOG). PX4 v1.18 `sensor_gnss` / `vehicle_gnss` support in the ULog
  adapter. `scripts/sih_inject.py` (SIH + INJECTED), `sitl_flight.py --no-faults`, `sitl_timeline.py`, `dump_gnss.py`.

### Fixed
* Docker smoke test container name and the ROS 2 job (stale pip in `ros:humble`); all CI jobs pass.

## [1.1.0] - 2026-10-09

### Added
* Replay delay estimator, reference quality gate, slow reference bias estimation, soft jamming tuning, Docker and
  ROS 2 CI jobs, evaluation on fresh seeds.

## [1.0.0] - 2026-10-09

### Added
* Held out evaluation, ablations, detectability sweep, figures, technical report, CI and container.

## [0.6.0] - 2026-10-09

### Added
* REST and SSE service, MCP server, operator dashboard; `marsad serve` and `marsad mcp`.

## [0.4.0] - 2026-10-09

### Added
* PX4 ULog, MAVLink and ROS 2 adapters, synthetic ULog writer, `marsad inspect` and `marsad replay`.

## [0.3.0] - 2026-10-09

### Added
* Track trust module, interference map, multi source track simulator.

## [0.1.0] - 2026-10-09

### Added
* Trust engine, detectors, fusion, state machine, measurement level simulator, benchmark harness.

[Unreleased]: https://github.com/hudasol/marsad/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/hudasol/marsad/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/hudasol/marsad/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/hudasol/marsad/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/hudasol/marsad/compare/v0.6.0...v1.0.0
[0.6.0]: https://github.com/hudasol/marsad/compare/v0.4.0...v0.6.0
[0.4.0]: https://github.com/hudasol/marsad/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/hudasol/marsad/compare/v0.1.0...v0.3.0
[0.1.0]: https://github.com/hudasol/marsad/releases/tag/v0.1.0
