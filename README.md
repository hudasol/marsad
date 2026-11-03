# Marsad (مرصد)

Advisory position trust for GNSS. Marsad takes a GNSS stream and an independent motion reference, decides whether the
position can be believed, separates a degraded signal from a false one, and recommends what to do next. It is a
research prototype, and this page leads with where it falls short.

[![CI](https://github.com/hudasol/marsad/actions/workflows/ci.yml/badge.svg)](https://github.com/hudasol/marsad/actions/workflows/ci.yml)
Apache-2.0 · Python 3.10+ · version 1.5.0 · [changelog](CHANGELOG.md)

![dashboard](docs/img/dashboard-spoof-drift.png)
<sub>Operator dashboard during a SIMULATED carry off: what GNSS reported (magenta), what Marsad advises (blue, orange
while it advises the reference), what was true (white).</sub>

> Marsad is an independent open source project. It is not affiliated with or endorsed by EDGE Group, the Technology
> Innovation Institute or the Advanced Technology Research Council.

## Problem

An autopilot gates GNSS against its own filter, and a filter absorbs slow drift as real motion. A spoofer that moves
the position at a fraction of a metre per second therefore never trips the check. Navigation without GNSS exists. The
missing piece is the layer that decides when to switch to it, and, one level up, a way for a decision platform to stop
inheriting positions it cannot trust.

## What it does

| module | for | output |
|---|---|---|
| vehicle trust | autopilots, companion computers, robots | trust score, `TRUSTED / DEGRADED / DENIED`, recommended action, fallback position, evidence |
| track trust | decision support, C2, agents | per track and per source trust with reasons |
| interference map | mission planning | hex binned, time decayed confidence as GeoJSON |
| MCP server | AI agents | `assess_vehicle_window`, `score_track`, `list_distrusted_tracks`, `explain_state` |

The core engine uses only the standard library. Interfaces: PX4 ULog, MAVLink (advisory output only), ROS 2, a REST and
SSE service with a dashboard, and the MCP server.

## Results

Every number carries one label, defined in [docs/VALIDATION.md](docs/VALIDATION.md) before the run that produced it. The
full account, with the preregistrations and the misses, is in [docs/EVIDENCE.md](docs/EVIDENCE.md).

### What does not work yet

* **False alarms on real flights (REAL LOG).** On 101 public PX4 flights with no attack, Marsad was fully TRUSTED on 54
  (53.5%, 95% interval 43.3% to 63.5%) and reached DENIED on 46.
  <!-- claim docs/results/real_corpus/summary.json R1_all_trusted/k 54 -->
  The main causes are lost fixes on 1 Hz receivers and start up. All seven preregistered predictions for this study missed.
  A later attempt to fix the two largest causes reached 62 of 101 against a target of 68 and was not adopted.
* **A reference that follows the spoofer (SITL EKF2).** With PX4's own EKF2 velocity as the reference, a drift whose
  velocity agrees with its position was detected in 0 of 4 runs at every rate from 0.25 to 2.0 m/s, by Marsad and by every
  baseline, while the EKF2 rejected nothing. n is 4 runs per cell.
* **A plain window test does as well (REAL LOG + INJECTED).** With attacks added to 52 real flights (the reference being
  the logged EKF2 velocity, an optimistic bound), a sliding window consistency test detected as many drifts as Marsad and
  was faster at every rate: median 57.6 s against 111.8 s at 0.25 m/s, and 18.5 s against 25.5 s at 1.0 m/s.
  <!-- claim docs/results/real_injected/summary.json arms/ekf/cases/drift_0.25_velcons/window/median_latency_s 57.6 -->
  23 of 75 eligible flights could not be used because Marsad was already alarmed before the onset.

### What it does (labels as stated)

| result | label | n |
|---|---|---|
| jumps of 50 to 1000 m detected in about 0.4 s, by Marsad and by every baseline | REAL LOG + INJECTED | 52 flights |
| position only drift at 0.5 m/s or more detected in 19 to 62 s | SITL EKF2 | 4 runs per cell |
| velocity consistent drift at 0.25 to 2.0 m/s detected with an uncontaminated reference | REAL LOG + INJECTED | 52 flights |
| reference bias up to 0.15 m/s tolerated, failure at 0.30 m/s | SIH + INJECTED | 4 flights per cell |
| five attack kinds specified from the literature detected, no false alarm before onset | SIMULATED (LITERATURE) | 30 runs per kind |

The SIMULATED families share an author with the engine, so they read as regression tests. SEALED_README_PLACEHOLDER

### Against reference detectors (SIMULATED, held out, 30 seeds per scenario)

This is the v1.4.0 table, kept because it is the only place the detectors are compared on scenarios with no
real data behind them. Share of runs detected, median latency in seconds. The baselines are described in
[docs/BASELINES.md](docs/BASELINES.md).

| scenario | Marsad | EKF2 style gate + reference | window consistency | signal monitor |
|---|---|---|---|---|
| position jump | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 87% / 5.5 |
| replay | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 27% / 0.5 |
| carry off drift | 100% / 27.1 | 53% / 24.2 | 100% / 22.6 | 0% |
| stealth carry off | 100% / 58.0 | 0% | 100% / 43.0 | 0% |
| carry off, reference outage | 100% / 41.1 | 43% / 53.5 | 100% / 53.7 | 0% |
| carry off, no reference | 53% / 33.1 | 27% / 22.8 | 87% / 31.1 | 0% |
| hard jamming | 100% / 2.4 | 100% / 8.0 | 100% / 8.0 | 100% / 0.7 |

| | Marsad | EKF2 style gate + reference | window consistency | signal monitor |
|---|---|---|---|---|
| position handed to the vehicle after a jump (median of max error, m) | **8** | 430 | 430 | 430 |
| position handed to the vehicle after replay (m) | **10** | 711 | 164 | 712 |
| nominal runs with any alarm | 0% | 0% | 23% | 0% |
| multipath runs with any alarm | 3% | 33% | 60% | 100% |
| obstruction runs with any alarm / share of time not trusted | 100% / 85% | 60% / 23% | 73% / 23% | 100% / 95% |

The window test is faster than Marsad on drift and does better without a reference, but it false alarms on nominal
simulated flights and cannot classify. The error rows compare what each system hands to the vehicle: the baselines raise
a flag and keep following GNSS, Marsad also recommends a fallback position, so that lead comes from having a fallback at
all.

### Limits

Nothing has run on a real flight controller other than PX4 software in the loop, or on real interference. Drift below
0.25 m/s is not detected. Without an independent reference Marsad finds 53% of simulated drifts. The full list is in
[docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md) and the plan in [docs/ROADMAP.md](docs/ROADMAP.md).

## Install

```bash
git clone https://github.com/hudasol/marsad && cd marsad
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

The core needs nothing beyond the standard library. Extras: `sim` (numpy, for the simulator and benchmark), `adapters`
(pyulog and pymavlink), `api` (the service) and `mcp` (the MCP server). `dev` installs all of them with the test and
lint tools.

## Use

Command line:

```bash
marsad demo spoof_drift_stealth --seed 4          # state transitions with evidence (SIMULATED)
marsad inspect flight.ulg                         # which fields a PX4 log provides
marsad replay flight.ulg --config site.json       # score a log, optional JSON config
marsad monitor udpin:0.0.0.0:14550                # live MAVLink; --out for advisory output
marsad serve                                      # dashboard and API on http://127.0.0.1:8000
marsad mcp                                        # MCP server on stdio
marsad bench --split heldout --seeds 30           # benchmark
```

Library:

```python
from marsad import TrustEngine, preset, NavSample, GnssFix, RefMotion

engine = TrustEngine(preset("uav_multirotor"))
report = engine.update(
    NavSample(
        t=12.4,
        gnss=GnssFix(t=12.4, lat=24.45, lon=54.38, ve=8.1, vn=2.0, cn0_mean=41.0, cn0_std=3.1, n_sats=13, agc=0.31),
        ref=RefMotion(t=12.4, ve=8.0, vn=2.1),  # visual odometry, optical flow, wheel odometry
    )
)
print(report.state, report.trust, report.action, report.summary)
```

A runnable version is in [examples/](examples/). Configuration files are described in
[docs/ADAPTERS.md](docs/ADAPTERS.md).

## How it works

```
 ULog / MAVLink / ROS 2 / simulator -> adapters -> NavSample stream (GNSS fix + independent velocity reference)
                                                       |
                  signal, kinematic, inertial, timing detectors -> log likelihood evidence
                                                       |
            recursive multi hypothesis fusion (environment, jamming, jump, drift, replay)
                                                       |
      state machine (hysteresis, anchor rewind, re-acquisition checked against dead reckoning)
                                                       |
        TrustReport -> MAVLink (advisory) · ROS 2 · REST/SSE · MCP · dashboard · interference map
```

The drift detector compares the GNSS displacement over several windows with the integral of the reference velocity. It
carries a slow estimate of the reference bias, and also tests against the uncorrected integral with a fixed bound so
that the estimate cannot absorb a drift. The method and its predictions are in
[docs/research/PREREGISTRATION_PRIOR_BOUND.md](docs/research/PREREGISTRATION_PRIOR_BOUND.md).

## Reproducing the tables

```bash
python scripts/run_eval.py --out docs/results/prior_bound                    # SIMULATED tables, ablation, detectability
python scripts/run_baselines.py --marsad docs/results/prior_bound/heldout.json
python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out out.json  # SIH + INJECTED
python scripts/sih_baselines.py sitl2.ulg --end 290 --t-attack 60 --marsad out.json --out base.json
```

The `.ulg` logs are not in git. `flight1.ulg` and `flight2.ulg` are public logs from review.px4.io; `sitl1.ulg` and
`sitl2.ulg` are PX4 SIH runs made with `scripts/sitl_flight.py` and attached to the GitHub release. Checksums and
download steps are in [docs/DATA.md](docs/DATA.md). Results of earlier versions are kept under `docs/results/`.

## Documentation

[Evidence](docs/EVIDENCE.md) · [Validation](docs/VALIDATION.md) · [Baselines](docs/BASELINES.md) · [Known limits](docs/KNOWN_LIMITS.md) ·
[Roadmap](docs/ROADMAP.md) · [Evaluation](docs/EVALUATION.md) · [Technical report](docs/TECHNICAL_REPORT.md) ·
[Adapters](docs/ADAPTERS.md) · [Track trust](docs/TRACKS.md) · [API](docs/API.md) · [MCP](docs/MCP.md) ·
[Dashboard](docs/DASHBOARD.md) · [Data](docs/DATA.md) · [Index](docs/README.md) · [Contributing](CONTRIBUTING.md) ·
[Security](SECURITY.md) · [Proposal seed](docs/proposals/EDGE_PROPOSAL.md)

## Scope

Marsad is not a GNSS receiver or RF analyser, not a substitute for authenticated GNSS, not an attack tool (the
simulator works at the measurement level and there is no signal generation in this repository), and it does not
command vehicles. The MAVLink reporter emits trust values and status text only, and a test enforces that. It does not
attribute interference to any actor.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
