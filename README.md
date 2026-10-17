# Marsad (مرصد)

**Position-trust layer for autonomous systems and decision platforms.**

Marsad answers one question: *can I believe this position?* It detects GNSS jamming and spoofing, separates
"GNSS is degraded" from "GNSS is lying", scores the integrity of positions coming from vehicles and from
multi-source tracks, explains its reasoning, and recommends a fallback navigation mode. The core is
hardware-independent and standard-library only; it speaks PX4 ULog, MAVLink and ROS 2, serves a REST/SSE API and an
operator dashboard, and exposes an **MCP server** so AI agents and decision platforms can use it as a tool.

![dashboard](docs/img/dashboard-spoof-drift.png)
<sub>Operator dashboard during a SIMULATED carry-off: what GNSS said (purple), what Marsad advises (orange), what was real (white).</sub>

> **Independence notice.** Marsad is an independent open-source project. It is not affiliated with, endorsed by, or
> sponsored by EDGE Group, the Technology Innovation Institute (TII), the Advanced Technology Research Council (ATRC), or
> any of their entities.
>
> **Validation status (v1.2.0).** The results table below is SIMULATED (measurement level generator). Beyond it:
> two unmodified public PX4 flights replay with zero alarms (REAL LOG, no attack present), and attacks added to real
> PX4 SIH logs are scored against simulator truth (SIH + INJECTED): jumps are caught at once, but drifts of 0.5 m/s or
> faster are caught only after median latencies of 98.1 to 204.6 s, at median offsets of 77.1 to 186.8 m, and 0.25 m/s
> or slower is not caught at all in a 230 s window.
> Nothing has been run on a real flight controller or on real interference data. See
> [docs/VALIDATION.md](docs/VALIDATION.md) for exactly what is and is not demonstrated.

## Why this exists

Public reporting from March 2026 describes navigation interference affecting more than 1,100 commercial ships within
a day in UAE, Qatari, Omani and Iranian waters, with vessel positions displaced onto land and airports (sources in
[docs/EDGE_PROPOSAL.md](docs/EDGE_PROPOSAL.md)). The hardest case is
**carry-off spoofing**: a slow drift that stays under the sanity checks autopilots use for noise and faults, because
a navigation filter absorbs slow drift as real motion. Navigation without GNSS exists. What is missing is the layer
that **decides when to switch to it**, and, one level up, a way for a decision platform to stop inheriting poisoned
positions from the tracks it fuses.

## What it does

| Module | For | Output |
|---|---|---|
| **Vehicle trust** | Autopilots, companion computers, robots | Trust score, `TRUSTED / DEGRADED / DENIED`, recommended navigation action, fallback position, human-readable evidence |
| **Track trust** | Decision-support platforms, C2, AI agents | Per-track and per-source trust with reasons: plausibility, replay, forbidden zones, circle-pattern signature, cross-source disagreement, source-level common-mode offset |
| **Interference map** | Mission planners | Hex-binned, time-decayed interference confidence (GeoJSON) |
| **MCP server** | AI agents | `assess_vehicle_window`, `score_track`, `list_distrusted_tracks`, `explain_state`, … |

## Results (SIMULATED, held-out seeds, 30 per scenario)

| | Marsad | simplified autopilot-style gate |
|---|---|---|
| Position takeover (jump / replay) detected | 100%, median **0.1 s** | 100%, 0.1 s, but accepts the spoofed position again after its latch: median error **430 m** vs **8 m** |
| Stealth carry-off (no power signature) detected | **100%**, median 58 s | **0%** |
| Carry-off with power signature detected | 100% | 0% |
| Navigation error, stealth carry-off (median of max) | **20 m** (raw GNSS 145 m) | 144 m |
| Jamming (hard / soft) detected | 100% / 100%, 2.4 s / 5.0 s | 100% / 100% |
| Signal obstruction → DENIED | **0%** of runs | 100% |
| Multipath → DENIED | **3%** of runs (1 of 30) | 77% |
| Nominal flights with any alarm | 0% | 0% |
| Engine cost | 187.7 µs / sample on one cloud core, stdlib only | |

**Where it does not work** (reported in [docs/EVALUATION.md](docs/EVALUATION.md)): without an independent motion
reference carry-off detection falls to 53% (labelled `spoofing_unclassified`) and there is no fallback position; drifts of 0.1 m/s are detected in only ~50% of runs and 0.05 m/s never; an attack at power-up has no clean baseline; in soft jamming the simple baseline's latency is lower
(4.1 s vs 5.0 s) and its navigation error is equal (11 m); on real PX4 SIH logs drift detection is far slower than in
simulation ([docs/VALIDATION.md](docs/VALIDATION.md)). Track-trust results (precision/recall 1.00 on simulated scenes) come from a simulator and detectors
with the same author and should be read accordingly ([docs/TRACKS.md](docs/TRACKS.md)).

## Design in one picture

```
 ULog / MAVLink / ROS 2 / simulator ──► adapters ──► NavSample stream (GNSS fix + independent velocity reference)
                                                       │
                     signal · kinematic · inertial/reference · timing detectors  → log-likelihood evidence
                                                       │
                recursive multi-hypothesis fusion (environmental, jamming, spoof-jump, spoof-drift, replay)
                                                       │
        state machine (hysteresis, anchor rewind, re-acquisition verified against dead-reckoning)
                                                       │
            TrustReport ──► MAVLink (advisory) · ROS 2 · REST/SSE · MCP · dashboard · interference map
```

## Quick start

```bash
git clone https://github.com/hudasol/marsad && cd marsad
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                   # about 9 min (547 s measured on a laptop)

marsad demo spoof_drift_stealth --seed 4                 # state transitions with evidence (SIMULATED)
marsad serve                                             # dashboard + API at http://127.0.0.1:8000
marsad mcp                                               # MCP server on stdio (see docs/MCP.md)
marsad bench --split heldout --seeds 30                  # reproduce the benchmark
marsad make-log --kind spoof_drift --out sim.ulg         # SIMULATED PX4 style ULog
marsad inspect real_flight.ulg && marsad replay real_flight.ulg   # your own PX4 log
```

Use it as a library:

```python
from marsad import TrustEngine, preset, NavSample, GnssFix, RefMotion

engine = TrustEngine(preset("uav_multirotor"))
report = engine.update(NavSample(t=12.4,
    gnss=GnssFix(t=12.4, lat=24.45, lon=54.38, ve=8.1, vn=2.0, cn0_mean=41.0, cn0_std=3.1, n_sats=13, agc=0.31),
    ref=RefMotion(t=12.4, ve=8.0, vn=2.1)))            # ref = visual odometry / optical flow / odometry
print(report.state, report.trust, report.action, report.summary)
```

## For reviewers

* **What is claimed and what is not:** [docs/VALIDATION.md](docs/VALIDATION.md). Every number carries one label:
  SIMULATED, REAL LOG, SIH + INJECTED or SITL FAULT.
* **Proposal seed:** [docs/EDGE_PROPOSAL.md](docs/EDGE_PROPOSAL.md). **Open review findings:**
  [docs/REVIEW_FINDINGS.md](docs/REVIEW_FINDINGS.md). **Predictions written before the SIH runs:**
  [docs/PREREGISTRATION_SIH.md](docs/PREREGISTRATION_SIH.md).
* **Reproduce each table with one command** (from the repository root, after `pip install -e ".[dev]"`):

| table | label | command | output |
|---|---|---|---|
| Held out, dev, ablation, detectability, throughput (EVALUATION.md, the table above) | SIMULATED | `python scripts/run_eval.py` (about 12 min) | `docs/results/*.md`, `*.json` |
| Real PX4 flights, false alarm side | REAL LOG | `marsad replay flight1.ulg --json docs/results/real_flight1.json` (same for `flight2.ulg`) | `docs/results/real_logs.txt` |
| SIH + INJECTED, 32 s window | SIH + INJECTED | `python scripts/sih_inject.py sitl1.ulg --out docs/results/sih_inject.json` | `docs/results/sih_inject.txt` |
| SIH + INJECTED, 230 s window | SIH + INJECTED | `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_inject_long.json` (about 17 min) | `docs/results/sih_inject_long.txt` |
| Exploratory diagnosis of the drift misses | SIH + INJECTED | `python scripts/sih_diagnose.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_diagnose_long.json` | `docs/results/sih_diagnose_long.txt` |
| Clean SIH flight acceptance check | SIH + INJECTED (control, zero offset) | `python scripts/sitl_timeline.py sitl2.ulg 10` | `docs/results/sitl2_timeline.txt` |

The `.ulg` logs are not stored in git (23 to 190 MB each). `flight1.ulg` and `flight2.ulg` are public logs from
review.px4.io; `sitl1.ulg` and `sitl2.ulg` are PX4 v1.18 SIH runs flown with `scripts/sitl_flight.py`. A new SIH
flight flown with the same script reproduces the method, not the exact published numbers.

## Documentation

[Build plan](plan.md) · [Evaluation](docs/EVALUATION.md) · [Technical report](docs/TECHNICAL_REPORT.md) ·
[One-pager](docs/ONE_PAGER.md) · [Validation status](docs/VALIDATION.md) · [Adapters](docs/ADAPTERS.md) ·
[Track trust](docs/TRACKS.md) · [API](docs/API.md) · [MCP](docs/MCP.md) · [Dashboard](docs/DASHBOARD.md) ·
[Milestones](docs/MILESTONES.md) · [Security & responsible use](SECURITY.md)

## What it is not

- Not a GNSS receiver or RF analyser.
- Not a substitute for authenticated GNSS or controlled-reception antennas; it complements them where they are absent.
- **Not an attack tool.** The simulator models attacks at the measurement level only. There is no RF signal
  generation, SDR code, or spoofing waveform synthesis in this repository.
- Does not command vehicles (the MAVLink reporter can only emit trust values and status text; enforced by a test).
- Does not attribute interference to any actor.

## Roadmap

| Tag | Content |
|---|---|
| `v0.1.0` | Core engine, detectors, fusion, state machine, simulator, benchmark harness |
| `v0.3.0` | Track-trust module, interference map |
| `v0.4.0` | PX4 ULog, MAVLink, ROS 2 adapters |
| `v0.6.0` | REST/SSE service, MCP server, dashboard |
| `v1.0.0` | Held-out evaluation, ablations, CI, container, technical report |
| `v1.1.0` | Replay delay estimator, reference quality gate, slow reference bias estimation, fresh seed evaluation, Docker and ROS 2 CI jobs |
| `v1.2.0` | Real PX4 log replay (false alarm side), PX4 v1.18 adapter fields, SIH + INJECTED evaluation with preregistered predictions, CI fixes |
| unreleased | Evidence weighting fix for mixed sample rates, preregistered (docs/PREREGISTRATION_WEIGHTING.md) and scored in docs/VALIDATION.md and docs/EVALUATION.md; results in docs/results/weighting_fix/ |
| next | Bias estimator review (velocity consistent drift absorption), then advisory companion computer, then closed loop in an authorised range |

All tags are listed in [docs/MILESTONES.md](docs/MILESTONES.md).

## License

Apache-2.0. See [`LICENSE`](LICENSE).
