# Marsad: a position-trust layer for autonomous systems

Huda Mueen · v1.3.0 · Independent open-source project, not affiliated with or endorsed by EDGE Group, TII, ATRC or any of their entities.
Section 3 is SIMULATED. Results on real PX4 logs (REAL LOG) and on PX4 SIH logs with injected offsets
(SIH + INJECTED) are in VALIDATION.md and summarised in section 4.

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

**Interfaces.** Core: standard-library Python, O(log n) per sample. Adapters: PX4 ULog, MAVLink, ROS 2. Service:
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

## 4. Failure regimes (reported, not hidden)

* **No independent reference (SIMULATED):** carry-off without a power signature is undetectable; 53% detection (power-signature
  cases only) and no fallback position (`HOLD_AND_ALERT`).
* **Slow carry-off near the reference bias bound:** 0.05 m/s is never detected and 0.1 m/s in 50 to 56% of runs (SIMULATED).
* **Attack at power-up:** no clean baseline.
* **Coordinated attack on the reference sensor.**
* **Replay labelling is late:** at the first alarm a replay carries the coarse spoofing label; `replay_meaconing` is assigned once a delay is confirmed (97% of runs settled, SIMULATED).
* **Where the baseline wins (SIMULATED):** in soft jamming its latency is lower (4.1 s vs 4.6 s), although its navigation error is
  higher (11 m vs 9 m) since v1.3.0.
* **Slow drift on real PX4 SIH logs (SIH + INJECTED):** v1.2.0 diluted drift evidence when the reference (about 125 Hz)
  arrived faster than GNSS (about 8 Hz) and caught drifts of 0.5 to 2 m/s only after median latencies of 98.1 to
  204.6 s. The preregistered fix in v1.3.0 brings this to 15.7 to 48.3 s at median offsets of 18.8 to 22.4 m in a 230 s
  window. Still missed: a velocity consistent drift of 0.25 m/s, because the reference bias estimator absorbs 34.8%
  of it before the drift evidence starts, and any drift of 0.1 m/s (KNOWN_LIMITS.md).

## 5. What it takes to make this real

Two real PX4 flights now replay with zero alarms and two SIH logs have been scored with injected offsets
(VALIDATION.md), and the evidence weighting fix has been scored against its preregistration. Next: review the bias
estimator (KNOWN_LIMITS.md), replay more real logs including GNSS degraded ones,
calibrate against receiver-reported jamming/spoofing flags, then an advisory companion computer, then closed loop in
an authorised environment. An operational demo needs a vehicle, an operator who will use the output, and range time.

## 6. Ethics and scope

Defensive, advisory only; no RF or waveform code; no attribution of interference; Apache-2.0.
