# Marsad — Build Plan

> Position-trust layer for autonomous systems and decision platforms.
> This document is the source of truth for scope, architecture, milestones and the honesty rules for what we claim.

Status: **v1.0.0 built** (this document was written as the plan; results and status live in README.md and docs/EVALUATION.md).

---

## 1. Problem statement

Autonomous vehicles and the decision platforms that consume their data cannot reliably tell the difference between:

- **GNSS is degraded** (jamming, multipath, loss of satellites), and
- **GNSS is lying** (spoofing, meaconing/replay, slow "carry-off" drift).

The consequence is asymmetric. A vehicle that cannot detect a lie keeps navigating on a false position. A vehicle that cannot detect honest degradation abandons good GNSS for no reason. In both cases the fallback navigation (vision-based, inertial, terrain-referenced) is only as useful as the **decision to switch to it**.

The Gulf region is one of the most interference-heavy environments in the world. Public reporting from early 2026 describes hundreds of jamming incidents off the UAE coast in a single period, vessel positions displaced onto airports and inland sites, and aircraft affected. Autopilot sanity checks are designed for noise and sensor faults, not for an adversary who stays under the thresholds, which is exactly what carry-off spoofing does.

Decision platforms have the same problem one layer up. A platform that fuses tracks from several feeds inherits every poisoned position unless something scores each track's physical plausibility and cross-source agreement.

## 2. What Marsad is

A **trust engine** with two modules on a shared core:

| Module | Consumer | Question it answers |
|---|---|---|
| **Vehicle trust** | Autopilot / companion computer / robot | "Can I believe my own GNSS position right now, and what should I navigate on?" |
| **Track trust** | Decision-support platforms, C2, agents | "Can I believe this track's position, and why or why not?" |

Both emit a calibrated trust score, a discrete trust state, a recommended action, and **human-readable evidence**. Evidence matters: operators and downstream agents must be able to see *why* a position was distrusted.

Marsad also exposes a **fleet layer** that aggregates trust events into an interference map, so the next mission can route around hot spots.

### Non-goals (stated up front)

- Not a GNSS receiver and not an RF signal analyser. It consumes receiver-reported and vehicle-reported measurements.
- Not a replacement for authenticated GNSS (Galileo OSNMA, GPS M-code, CNAV authentication) or controlled-reception-pattern antennas. It complements them and is useful precisely where they are absent.
- Not an attack tool. The simulator models attacks **at the measurement level only** (what the receiver would report). There is no RF signal generation, no SDR code, no spoofing waveform synthesis anywhere in this repository.
- Not attributing interference to any actor. The tooling is about resilience.

## 3. Design principles

1. **Hardware-independent core.** Plain timestamped measurements in, trust report out. No dependency on PX4, ROS or any vehicle. The same engine runs on a drone, a ground robot, a boat, or a server scoring tracks.
2. **Adapters at the edges.** ULog replay, MAVLink, ROS 2, REST, MCP. Moving to real hardware means writing or configuring an adapter, not touching the core.
3. **Onboard-friendly.** Constant time and memory per sample, fixed-size state, no heavy dependencies in the core (NumPy only). We measure latency and memory so a later C++/Rust port or companion-computer deployment is realistic.
4. **Explainable by construction.** Every state change carries the evidence that caused it.
5. **Honest evaluation.** Every reported number is labelled with how it was produced (simulation vs. replay of real logs). Benchmarks compare against a documented baseline, use fixed seeds, and report failures, not only successes.
6. **Product, not a script.** Typed code, tests, CI, packaging, container, docs, a dashboard, versioned releases.

## 4. Architecture

```
                         ┌────────────────────────────────────────────────┐
  ULog replay ─┐         │                  marsad core                    │
  MAVLink live ─┼─ adapters ─►  NavSample stream                          │
  ROS 2 topics ─┤         │        │                                       │
  Simulator ────┘         │        ▼                                       │
                          │  Detectors (signal, kinematic, inertial,       │
                          │             time)  → likelihood tables         │
                          │        │                                       │
                          │        ▼                                       │
                          │  Fusion: recursive multi-hypothesis Bayes      │
                          │  H = {nominal, jamming, spoof-jump,            │
                          │       spoof-drift, replay}                     │
                          │        │                                       │
                          │        ▼                                       │
                          │  Trust state machine (hysteresis) + evidence   │
                          │        │                                       │
                          └────────┼───────────────────────────────────────┘
                                   ▼
          TrustReport → MAVLink out · ROS 2 out · REST/SSE · MCP tools · dashboard

  Tracks ──► Track trust (plausibility, cross-source, spoof signatures) ─► same report shape
  Events ──► Fleet interference map (hex grid, time-decayed)
```

### 4.1 Vehicle trust — detectors

Each detector looks at one physical consistency and outputs a **likelihood table** over the hypotheses. The fusion layer multiplies them, so independent weak evidence accumulates into confident decisions.

| Detector | Signal | Helps distinguish |
|---|---|---|
| Signal quality | C/N0 level and spread across satellites, AGC level, satellite count, fix quality, receiver jamming/spoofing indicators when available | jamming (level drops, AGC rises) vs spoofing (suspiciously uniform, high C/N0) |
| Kinematic | Position jumps vs reported velocity, velocity vs position derivative, acceleration plausibility for the vehicle class | simple spoofing, replay discontinuities |
| Inertial / alternative velocity | GNSS velocity and integrated position vs an independent reference (IMU dead reckoning, optical flow, visual odometry, wheel odometry, airspeed + heading); CUSUM on the accumulated residual | slow carry-off drift that stays under per-sample gates |
| Time consistency | GNSS time vs monotonic clock, discontinuities, replay lag | meaconing / replay |

### 4.2 Fusion

Recursive Bayes over a small hypothesis set with a **sticky Markov prior** (attacks persist, they do not flicker). Likelihoods are tempered to avoid over-confidence, and a floor prevents any hypothesis from being driven to exactly zero. Output: posterior, trust score = P(nominal), calibrated against simulation (reliability diagram reported in the benchmark).

### 4.3 Trust state machine

`TRUSTED → DEGRADED → DENIED`, with separate enter/exit thresholds, minimum dwell times and a hold-off to prevent chatter. Each state maps to a recommended action:

| State | Recommended action |
|---|---|
| TRUSTED | Use GNSS normally |
| DEGRADED | Inflate GNSS covariance / reduce weight; prefer alternative navigation where available |
| DENIED | Stop using GNSS; switch to alternative navigation; hold or return per mission policy |

### 4.4 Track trust

Scores one track at a time and across tracks:

- speed/acceleration plausibility by track class (vessel, aircraft, ground, unknown)
- teleport / discontinuity detection
- reported speed/course vs position-derived speed/course
- circle-pattern signature (tight constant-radius loops)
- exclusion zones supplied by the user (for example "no vessels here")
- cluster collapse (many tracks reporting near-identical positions)
- cross-source disagreement for the same identity

### 4.5 Fleet interference map

Hex-binned, time-decayed aggregation of trust events with a confidence per cell. Used for mission routing hints. Works on synthetic data in this repository; real data would be supplied by the operator.

## 5. Evaluation plan (how we avoid fooling ourselves)

**Scenario matrix** (seeded, reproducible): nominal flights with realistic noise; jamming (ramp, step, partial, intermittent); spoof-jump at several magnitudes; carry-off drift at several rates; replay/meaconing with several delays; combined and low-signal-quality-but-honest cases (hard negatives). Vehicle classes: multirotor, fixed-wing, ground vehicle.

**Baseline:** a fixed-threshold detector modelled on the kind of per-sample sanity gating autopilots use (fix quality, velocity/position innovation gates). Documented in `docs/VALIDATION.md`, including its limits. We do **not** claim to reproduce any specific autopilot's behaviour.

**Metrics:**
- detection latency (time from attack onset to DENIED/DEGRADED)
- miss rate (attack never detected)
- false alarms per flight hour (nominal and hard-negative scenarios)
- **max undetected position error** — the damage done before detection (the number that matters operationally)
- time in wrong state
- calibration (reliability diagram, Brier score)
- compute: per-sample latency and memory

**Labelling rules:** every result in the README, reports and docs states *simulated*, with scenario count, seed count and software version. Results from replaying real logs will be reported separately and only if real logs are provided.

**Known threat to validity:** the simulator and the detectors are written by the same author. Mitigations: independent noise models and attack parameter ranges separated into a held-out set that is never used while tuning; sensitivity analysis over noise levels; explicit reporting of regimes where detection fails (for example very slow drift below the independent reference's own drift).

## 6. Interfaces

- **Python API:** `TrustEngine.update(sample) -> TrustReport`
- **CLI:** `marsad sim`, `marsad bench`, `marsad replay <log.ulg>`, `marsad serve`, `marsad mcp`
- **REST + SSE:** FastAPI service with OpenAPI schema
- **MCP server:** tools for AI agents and decision platforms (assess position trust, assess a flight log, explain a trust event, interference map, list/run scenarios)
- **MAVLink:** consume `GPS_RAW_INT` and related messages; publish trust as named values and status text
- **ROS 2:** optional node publishing standard message types; tested in CI against a stubbed client library, with a documented path for a real ROS 2 install
- **Dashboard:** operator view with live playback of scenarios, trust timeline, posterior, evidence, benchmark results, interference map

## 7. Technology choices

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.11+ (3.13 supported) | TII's public tooling and AI work is Python-heavy; fast to iterate |
| Numerics | NumPy (core), SciPy (bench/analysis only) | keeps the core light and portable |
| Logs | `pyulog`, `pymavlink` | native PX4 formats |
| Service | FastAPI + Pydantic + Uvicorn | typed schemas, OpenAPI for free |
| Agents | official Python MCP SDK | agent-facing tool surface |
| Quality | pytest, ruff, mypy, GitHub Actions (Linux + Windows) | portability, user develops on Windows |
| Packaging | `pyproject.toml`, extras `[api,mcp,ros2,dev]`, Docker image | clean install paths |
| UI | single-page dashboard served by the API, no build step | easy to run anywhere |

The core is deliberately simple enough to port to C++ or Rust for onboard use. A porting note and a latency/memory budget live in `docs/HARDWARE.md`.

## 8. Path to real hardware (kept in mind from day one)

1. PX4 software-in-the-loop with a GNSS-attack scenario, replaying the produced logs through Marsad.
2. Marsad on a companion computer reading MAVLink from a real flight controller, **advisory only** (publishes trust, does not command).
3. Closed loop: trust state selects navigation source under a mission policy, flight-tested in a controlled, authorised environment.
4. Port the core to a compiled language if latency or memory budgets require it.

Step 1 onward needs real logs or SITL, which this repository documents but does not claim to have completed. See `docs/HARDWARE.md`.

## 9. Milestones and tags

| Tag | Content | Done when |
|---|---|---|
| `v0.0.1-plan` | `plan.md`, README, license | pushed |
| `v0.1.0` | core engine, types, geodesy, detectors, fusion, state machine, simulator with attack library, unit tests | tests green, engine detects basic scenarios |
| `v0.2.0` | benchmark harness, baseline detector, metrics, calibration, report generator | reproducible benchmark with seeds |
| `v0.3.0` | track-trust module, fleet interference map | tests green |
| `v0.4.0` | adapters: ULog, MAVLink, ROS 2 (stub-tested), CLI | synthetic ULog round-trip passes |
| `v0.5.0` | FastAPI service, MCP server | API and MCP tests green |
| `v0.6.0` | dashboard | runs end to end locally |
| `v1.0.0` | CI, Docker, full docs, technical report, final benchmark, README with measured numbers | verified from a clean checkout |

## 10. Risks and honesty log

| Risk | Handling |
|---|---|
| Results come from simulation, not field data | Labelled everywhere; ULog adapter ready for real logs; `docs/VALIDATION.md` states what is and is not established |
| GNSS spoofing detection is a mature research area | Contribution is the arbitration layer, benchmark methodology, explainability, and agent/platform interfaces, not a new detection principle |
| Detector and simulator share an author | Held-out scenario parameters, sensitivity analysis, documented failure regimes |
| PX4 field names verified from memory, not from live docs | Adapter is field-presence-driven with fallbacks; first real log should be used to confirm; tracked in `docs/VALIDATION.md` |
| Sensitive regional context | Framed as resilience; no attribution; measurement-level modelling only; no real interference geodata bundled |
| Independence | README states Marsad is independent and not affiliated with or endorsed by TII, ATRC or any ATRC entity |

## 11. Out of scope for v1.0

Real RF processing, authenticated GNSS handling, hardware flight tests, multi-constellation raw observable processing, and a production-grade security audit. These are listed in `docs/ROADMAP.md`.
