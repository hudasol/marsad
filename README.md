# Marsad (مرصد)

**Position-trust layer for autonomous systems and decision platforms.**

Marsad answers one question: *can I believe this position?* It detects GNSS jamming and spoofing, scores the integrity of positions coming from vehicles and from multi-source tracks, explains its reasoning, and recommends a fallback navigation mode. It is PX4/MAVLink-native, hardware-independent at its core, and exposes an MCP interface so AI agents and decision platforms can use it as a tool.

> **Status: v0.0.1-plan (under active construction).** The architecture and evaluation method are specified in [`plan.md`](plan.md). This README is updated with measured results as milestones land. Nothing below is claimed as measured until a tagged release says so.

> **Independence notice.** Marsad is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by the Technology Innovation Institute (TII), the Advanced Technology Research Council (ATRC), or any of their entities.

---

## Why this exists

GNSS interference in the Gulf is no longer an anomaly. Public reporting from 2026 describes hundreds of jamming incidents off the UAE coast, vessel positions displaced onto airports and inland sites, and aircraft affected. The nastiest case is **carry-off spoofing**: a slow, gradual drift that stays under the sanity checks autopilots use to catch noise and faults.

An autonomous vehicle that cannot tell *"GNSS is degraded"* from *"GNSS is lying"* either keeps flying on a false position or abandons good GNSS for no reason. Navigation without GNSS exists. What is missing is the layer that **decides when to switch to it**. A decision platform that fuses tracks has the same problem one level up: it inherits every poisoned position unless something scores each track.

## What it does

| Module | For | Output |
|---|---|---|
| **Vehicle trust** | Autopilots, companion computers, robots | Trust score, `TRUSTED / DEGRADED / DENIED` state, recommended navigation mode, evidence |
| **Track trust** | Decision-support platforms, C2, AI agents | Per-track trust score with reasons (plausibility, spoof signatures, cross-source disagreement) |
| **Fleet interference map** | Mission planners | Hex-binned, time-decayed interference confidence |

Every verdict carries **human-readable evidence**, so an operator or downstream agent can see why a position was distrusted.

## Design in one picture

```
 ULog / MAVLink / ROS 2 / simulator ──► adapters ──► NavSample stream
                                                       │
                       signal · kinematic · inertial · time detectors
                                                       │
                      recursive multi-hypothesis fusion (nominal, jamming,
                       spoof-jump, spoof-drift, replay)
                                                       │
                    trust state machine (hysteresis) + evidence ──► TrustReport
                                                       │
                      MAVLink · ROS 2 · REST/SSE · MCP tools · dashboard
```

## Principles

- **Hardware-independent core.** Plain timestamped measurements in, trust report out. The same engine runs on a drone, a ground robot, a boat, or a server scoring tracks.
- **Onboard-friendly.** Constant time and memory per sample, NumPy-only core, designed to be portable to C++/Rust.
- **Explainable.** No verdict without evidence.
- **Honestly evaluated.** Results are labelled *simulated* or *real-log replay*, produced with fixed seeds, compared against a documented baseline, and failures are reported alongside successes.

## What it is not

- Not a GNSS receiver or RF analyser.
- Not a substitute for authenticated GNSS or controlled-reception antennas; it complements them where they are absent.
- **Not an attack tool.** The simulator models attacks at the measurement level only. There is no RF signal generation, SDR code, or spoofing waveform synthesis in this repository.
- Does not attribute interference to any actor.

## Roadmap

| Tag | Content |
|---|---|
| `v0.0.1-plan` | Plan, README, license |
| `v0.1.0` | Core engine, detectors, fusion, state machine, simulator and attack library |
| `v0.2.0` | Benchmark harness, baseline, metrics, calibration |
| `v0.3.0` | Track-trust module, fleet interference map |
| `v0.4.0` | ULog, MAVLink, ROS 2 adapters, CLI |
| `v0.5.0` | REST/SSE service, MCP server |
| `v0.6.0` | Operator dashboard |
| `v1.0.0` | CI, container, docs, technical report, final benchmark |

## Path to real hardware

1. PX4 software-in-the-loop with GNSS-attack scenarios, logs replayed through Marsad.
2. Companion computer reading MAVLink from a real flight controller, advisory only.
3. Closed loop: trust state selects the navigation source under a mission policy, tested in a controlled and authorised environment.
4. Port the core to a compiled language if budgets require it.

Steps beyond the simulator are documented, not claimed. See [`plan.md`](plan.md) section 8.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
