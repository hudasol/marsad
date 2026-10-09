# Marsad: a position-trust layer for autonomous systems

Huda Mueen · v1.0.0 · Independent open-source project, not affiliated with or endorsed by TII, ATRC or any of their entities.
All quantitative results are from measurement-level simulation (see EVALUATION.md and VALIDATION.md).

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
2026 interference in the Gulf (vessel positions displaced onto airports; circle-pattern anomalies) is the
motivating case.

## 2. Approach

**Four detectors** emit log-likelihood-ratio evidence against five hypotheses
(`environmental_degradation`, `jamming`, `spoofing_jump`, `spoofing_drift`, `replay_meaconing`) relative to nominal:

| detector | looks at | sees |
|---|---|---|
| signal | C/N0 level and spread, satellite count, AGC, fix loss | jamming vs obstruction (AGC separates them); spoofer-like uniform power |
| kinematic | position innovation vs velocity-propagated prediction; position vs reported-velocity consistency; reverts | takeover jumps; multipath excursions are cancelled when they snap back |
| inertial/reference | GNSS displacement vs integrated independent velocity over 5/15/45/120 s windows, normalised by a noise+bias bound | **carry-off** that never trips an innovation gate |
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

On held-out scenarios (30 seeds each): 100% detection of jumps, replay, hard/soft jamming and both kinds of carry-off (fresh seeds, v1.1.0);
median latency 0.1 s for abrupt events, 2–5 s for jamming, 27–58 s for
carry-off. A simplified autopilot-style gate detects the abrupt events but **none** of the carry-off runs, and after
its latch expires re-accepts spoofed positions (median error 430 m vs 8 m for Marsad on a jump). Obstruction never reaches DENIED and multipath did in 1 of 30 runs
under Marsad (the gate baseline denies 100% / 77% of runs). Replay is labelled as replay with an estimated delay. The track module scores
precision/recall 1.00 on simulated multi-source scenarios (including a 3–15 km AIS-style common offset attributed to
the right source), with the caveat that its simulator and detectors share an author. Full tables, ablations and a
carry-off detectability sweep are in EVALUATION.md.

## 4. Failure regimes (reported, not hidden)

* **No independent reference:** carry-off without a power signature is undetectable; 53% detection (power-signature
  cases only) and no fallback position (`HOLD_AND_ALERT`).
* **Slow carry-off below the reference bias bound:** 0.1 m/s is not detected; 0.15 m/s only sometimes.
* **Attack at power-up:** no clean baseline.
* **Coordinated attack on the reference sensor.**
* **`replay` is never labelled as replay** (it looks like a jump after onset); the coarse class is right.
* **Where the baseline wins:** in soft jamming its navigation error and latency are slightly better.

## 5. What it takes to make this real

Run the PX4 adapters on real logs (field names and units are unverified; ADAPTERS.md lists the unknowns), measure the
false-alarm rate on genuine flights, calibrate against receiver-reported jamming/spoofing flags, then SITL, then an
advisory companion computer, then closed loop in an authorised environment (VALIDATION.md). An operational demo needs a vehicle,
an operator who will use the output, and range time; the software side is ready for that.

## 6. Ethics and scope

Defensive, advisory only; no RF or waveform code; no attribution of interference; Apache-2.0.
