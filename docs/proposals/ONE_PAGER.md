# Marsad (مرصد): can I believe this position?

**Problem.** Public reporting in 2026 describes widespread GNSS interference in Gulf waters (sources in EDGE_PROPOSAL.md). Jamming is visible; spoofing is not, and slow "carry-off"
spoofing passes the sanity checks autopilots use. Fallback navigation exists, but nothing reliably *decides when
to switch*. Decision platforms inherit poisoned positions the same way.

**What it is.** A position-trust layer with two modules on one core:
**Vehicle trust** (autopilot / robot / companion computer: trust score, TRUSTED·DEGRADED·DENIED, recommended navigation
mode, evidence) and **Track trust** (decision platforms, C2, AI agents: per-track and per-source trust with reasons,
fleet interference map). Hardware-independent core, PX4/MAVLink/ROS 2 adapters, REST/SSE, operator dashboard, MCP server.

**Why it is different.** It separates *degraded* from *lying* using an independent motion reference, remembers an
attack until GNSS agrees with dead-reckoning again (no silent re-trust), and explains every verdict.

**Evidence (SIMULATED, held-out).** Abrupt spoofing detected in 0.1 s; stealth carry-off in 100% of runs (median 58 s)
vs 0% for a simplified autopilot gate; navigation error 20 m (median of max) against 145 m for raw GNSS in stealth carry-off;
obstruction never denied, multipath in 1 of 30 runs. Standard-library core; 892.3 to 1,263.0 µs per sample on a
Windows laptop (v1.3.0 engine).
**REAL LOG:** zero alarms over 1,245 s of two public PX4 flights (no attack present). **SIH + INJECTED** (v1.3.0 engine): jumps
caught at once; drifts of 0.5 to 2 m/s caught after median latencies of 15.7 to 48.3 s at median offsets of 18.8 to
22.4 m in a 230 s window (v1.2.0 before the weighting fix: 98.1 to 204.6 s, 77.1 to 186.8 m).

**Honest limits.** No flight controller, no real interference data; without an independent reference carry-off
detection falls to 53%; drift of 0.1 m/s detected in only about half of runs, 0.05 m/s never (SIMULATED); on PX4 SIH logs a
velocity consistent drift of 0.25 m/s and any drift of 0.1 m/s are not caught in 230 s (SIH + INJECTED). See
VALIDATION.md and KNOWN_LIMITS.md.

**Next (needs partners).** Review the bias estimator (KNOWN_LIMITS.md), replay partner logs, advisory companion computer,
controlled-range test with an anchor operator. Apache-2.0, independent of EDGE Group, TII and ATRC.
