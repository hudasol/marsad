# Marsad: a position-trust layer for autonomous systems

Huda Mueen · v1.5.0 · Independent open-source project, not affiliated with or endorsed by EDGE Group, TII, ATRC or any of their entities.
Section 3 is SIMULATED and regression only. The evidence on real PX4 flights, PX4 EKF2 in the loop and an independent
scenario family is in section 4 and in EVIDENCE.md; labels are defined in VALIDATION.md.

## 1. Problem

A GNSS receiver that is jammed tells you it is degraded. A receiver that is spoofed tells you nothing: its
position is wrong and its health indicators look fine. Autopilot sanity checks are tuned to noise and sensor
faults; an adversary who moves the receiver slowly (carry-off) stays below them, because a navigation filter
absorbs slow drift as if it were real motion. Meanwhile, alternatives to GNSS exist (visual odometry, optical
flow, inertial, terrain-referenced) but only help if something **decides when to switch**. The decision problem is:

> Given what the receiver reports and what an independent motion reference says, how likely is it that the
> reported position can be believed, why, and what should the vehicle navigate on?

At the decision-platform level the problem repeats: a system that fuses tracks from several feeds inherits every
poisoned position unless each track's plausibility and cross-source agreement are scored. Public reporting of
2026 interference in the Gulf (vessel positions displaced onto land and airports; sources in EDGE_PROPOSAL.md) is the
motivating case.

## 2. Approach

**Four detectors** emit log-likelihood-ratio evidence against five hypotheses
(`environmental_degradation`, `jamming`, `spoofing_jump`, `spoofing_drift`, `replay_meaconing`) relative to nominal:

| detector | looks at | sees |
|---|---|---|
| signal | C/N0 level and spread, satellite count, AGC, fix loss | jamming vs obstruction (AGC separates them); spoofer-like uniform power |
| kinematic | position innovation vs velocity-propagated prediction; position vs reported-velocity consistency; reverts | takeover jumps; multipath excursions are cancelled when they snap back |
| inertial/reference | GNSS displacement vs integrated independent velocity over 5/15/45/120/240 s windows, normalised by a noise+bias bound | **carry-off** that never trips an innovation gate |
| timing | GNSS clock vs host clock steps, non-monotonic time | replay/meaconing without clock repair |

**Fusion** is a recursive leaky log-odds accumulator per hypothesis with hypothesis-specific memory (spoofing is
remembered longer than obstruction) and priors. Quiet detectors contribute (near) zero, so a missing sensor is never
counted as evidence. **State machine** (TRUSTED / DEGRADED / DENIED) escalates immediately and de-escalates only after
hold times *and* a re-acquisition check: the GNSS must agree with the dead-reckoned continuation of the last trusted
track, whose uncertainty grows with the reference bias bound. If the outage has been too long for that check to be
meaningful, the state stays DEGRADED and the operator must acknowledge ("re-acquisition unverifiable").
**Anchor rewind**: on leaving TRUSTED, the dead-reckoning anchor is rewound to just before the first suspicious
evidence, so detection latency does not contaminate the fallback position.

**Track trust** applies the same idea to platforms: per-class kinematic plausibility, speed/course vs displacement,
cross-source disagreement, flatline/stale replay, forbidden zones, circle-fit signature, and **source-level common-mode
offset** (many tracks of one source displaced consistently against an independent source → blame the source, not 40
tracks). A hex-binned, time-decayed interference map aggregates vehicle and track events.

**Interfaces.** Core: standard-library Python, about 240 us per sample on one cloud core (`docs/results/prior_bound/throughput.json`). Adapters: PX4 ULog, MAVLink, ROS 2. Service:
REST + SSE + dashboard. Agent interface: an MCP server so AI agents and decision platforms can query trust and
explanations as tools. The MAVLink reporter is advisory-only and cannot emit commands (enforced by a test).

## 3. Results (simulated)

On held-out scenarios (30 seeds each): 100% detection of jumps, replay, hard/soft jamming and both kinds of carry-off (fresh seeds, v1.1.0
engine; in the v1.3.0 rerun only the soft jamming rows of the tables changed);
median latency 0.1 s for abrupt events, 2.4 to 4.6 s for jamming (soft jamming 5.0 s before v1.3.0), 27.2 to 58.3 s for
carry-off. A simplified autopilot-style gate detects the abrupt events but **none** of the carry-off runs, and after
its latch expires re-accepts spoofed positions (median error 430 m vs 8 m for Marsad on a jump). Obstruction never reaches DENIED and multipath did in 1 of 30 runs
under Marsad (the gate baseline denies 100% / 77% of runs). Replay is labelled as replay with an estimated delay. The track module scores
precision/recall 1.00 on simulated multi-source scenarios (including a 3 to 15 km AIS-style common offset attributed to
the right source), with the caveat that its simulator and detectors share an author. Full tables, ablations and a
carry-off detectability sweep are in EVALUATION.md.

## 4. Evidence on real flights, and failure regimes (reported, not hidden)

Studies of v1.5.0, each preregistered, with every miss kept ([EVIDENCE.md](EVIDENCE.md)):

* **False alarms on 101 public flights (REAL LOG).** Fully TRUSTED on 54 (53.5%), DENIED at some point on 46, 3.0 alarm
  episodes per flight hour. The main causes are lost fixes on 1 Hz receivers and start up. All seven predictions
  missed. A trial fix reached 62 of 101 and was not adopted.
* **Attacks added to real flights (REAL LOG + INJECTED, 52 flights, optimistic reference).** Jumps are detected in about
  0.4 s by every method. Velocity consistent drift of 0.5 m/s or more is detected in every flight with a median latency of
  42.3 s down to 15.7 s at 2.0 m/s; 0.25 m/s in 45 of 52 flights (111.8 s). A sliding window test detected all of them and
  was faster in every case. 23 of 75 eligible flights were alarmed before the onset and could not be scored.
* **PX4 EKF2 in the loop (SITL EKF2, 4 runs per cell).** When the reference is the EKF2 velocity, which fuses the
  spoofed fixes, velocity consistent drift is not detected at any rate by Marsad or by any baseline, and the EKF2
  itself rejects nothing. Position only drift of 0.5 m/s or more is detected in 19 to 62 s.
* **Imperfect reference (SIH + INJECTED, 4 flights per cell).** A constant reference bias of 0.15 m/s was absorbed; 0.30
  m/s caused false alarms in 4 of 4 flights.
* **Independent scenario family (SIMULATED (LITERATURE)).** Attack kinds specified from published descriptions are
  detected in 30 of 30 development runs each. The family is at the ceiling and does not separate the engine from a
  baseline stack, which was faster.

Other regimes:

* **No independent reference (SIMULATED):** carry-off without a power signature is undetectable; 53% detection (power-signature
  cases only) and no fallback position (`HOLD_AND_ALERT`).
* **Slow carry-off near the reference bias bound:** 0.05 m/s is never detected and 0.1 m/s in 50 to 56% of runs (SIMULATED).
* **Attack at power-up:** no clean baseline.
* **Coordinated attack on the reference sensor.**
* **Replay labelling is late:** at the first alarm a replay carries the coarse spoofing label; `replay_meaconing` is assigned once a delay is confirmed (97% of runs settled, SIMULATED).
* **Where the baseline wins:** in simulated soft jamming its latency is lower (4.1 s vs 4.6 s) and on every real flight drift case the window test is faster ([BASELINES.md](BASELINES.md)).

The earlier account of slow drift on the SIH logs (v1.2.0 to v1.4.0) is in [history/technical-report-v1.4.0-section4.md](history/technical-report-v1.4.0-section4.md).

## 5. What it takes to make this real

The first obstacle is the false alarm rate on real flights (46 of 101 flights reached DENIED), then a reference that
the spoofer cannot influence (optical flow, visual odometry, wheel odometry) and a flight controller on the bench,
then an advisory companion computer, then closed loop in an authorised environment (ROADMAP.md). An operational demo needs a vehicle, an operator who will use the output, and range time.

## 6. Ethics and scope

Defensive, advisory only; no RF or waveform code; no attribution of interference; Apache-2.0.
