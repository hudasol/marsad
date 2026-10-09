# Marsad (مرصد) — can I believe this position?

**Problem.** GNSS interference is routine in the Gulf. Jamming is visible; spoofing is not, and slow "carry-off"
spoofing passes the sanity checks autopilots use. Fallback navigation exists, but nothing reliably *decides when
to switch*. Decision platforms inherit poisoned positions the same way.

**What it is.** A position-trust layer with two modules on one core:
**Vehicle trust** (autopilot / robot / companion computer: trust score, TRUSTED·DEGRADED·DENIED, recommended navigation
mode, evidence) and **Track trust** (decision platforms, C2, AI agents: per-track and per-source trust with reasons,
fleet interference map). Hardware-independent core, PX4/MAVLink/ROS 2 adapters, REST/SSE, operator dashboard, MCP server.

**Why it is different.** It separates *degraded* from *lying* using an independent motion reference, remembers an
attack until GNSS agrees with dead-reckoning again (no silent re-trust), and explains every verdict.

**Evidence (simulated, held-out).** Abrupt spoofing detected in 0.1 s; stealth carry-off in 100% of runs (median 53 s)
vs 0% for a simplified autopilot gate; navigation error held to ~20 m while raw GNSS error grows to hundreds of
metres; obstruction/multipath never denied. 46 µs per sample, standard-library core.

**Honest limits.** Simulation only; real PX4 logs not yet replayed; no independent reference → no carry-off detection;
drift below ~0.15 m/s undetectable. See VALIDATION.md.

**Next (needs partners).** Real-log replay, SITL, advisory companion computer, controlled-range test with an
anchor operator. Apache-2.0, independent of TII/ATRC.
