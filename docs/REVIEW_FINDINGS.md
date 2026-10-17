# Review findings, v1.2.0

A hostile review of the whole repository was run on 2026-10-17, after the SIH + INJECTED work, by a reviewer who
had not seen how the work was done. It looked for unlabelled claims, numbers that disagree with `docs/results`,
mismatches between docs and code, dead links, stray files and style problems. Only documentation and labels were
changed in response; engine behaviour, thresholds, detectors and the v1.1.0 results were not touched.

**Checked and found consistent:** every held out number in README, EVALUATION, EDGE_PROPOSAL and RESUME_BULLET
against `heldout.md`; the SIH + INJECTED tables against `sih_inject.txt` and `sih_inject_long.txt`; the diagnosis
figures against `sih_diagnose*.txt`; the sitl2 acceptance figures against `sitl2_timeline.txt`; the REAL LOG figures
(911 s + 334 s) against `real_logs.txt`; `detectability.md` against the figure; every README CLI command against
`src/marsad/cli.py`; the 7 CI jobs; the tag hashes in MILESTONES.md. No RF, SDR or waveform code was found.

## Fixed

| # | severity | where | problem | fix |
|---|---|---|---|---|
| 1 | High | README.md, MILESTONES.md, RUN_LOG.md | link to this file before it existed | this file |
| 2 | High | MILESTONES.md, README.md | v1.2.0 described as tagged and released before it was | tag and release created at the end of the run |
| 3 | High | EVALUATION.md ablation table | signal and kinematic rows quoted v1.0.0 ablation numbers (39 s → 103 s, 5% obstruction DENIED, 1.5 s) under a "fresh seeds" heading | rows rewritten from `docs/results/ablation.md` (32.5 s → 48.3 s, obstruction never DENIED, jump 1.4 s, replay 1.6 s, multipath 5% DENIED without the inertial detector); note that ablation uses 20 seeds |
| 4 | High | TECHNICAL_REPORT.md | contradicted itself and EVALUATION (replay "never labelled", 0.1 m/s "not detected", baseline "better" in soft jamming, windows without 240 s, "v1.0.0", "all results simulated") | updated to v1.2.0 figures, labels and the SIH finding |
| 5 | High | ONE_PAGER.md | "real PX4 logs not yet replayed", "no reference → no carry off detection" (it is 53%), "hundreds of metres" | rewritten with labelled REAL LOG and SIH + INJECTED lines |
| 6 | High | ADAPTERS.md | "never run on a real PX4 log", "MarsadNode has never run", missing v1.18 topics | status table, notice, field table and ROS 2 section updated |
| 7 | High | VALIDATION.md | kept the superseded "NOT validated" wording; "first result not yet observed" for CI jobs that now pass; "path from here" listed finished steps | cell cleaned, CI rows updated, path updated |
| 9 | Medium | VALIDATION.md | precise transition times (158.4 s, 159.4 s) not in any results file; row level jamming figures not stored | transition now quoted from the 4 s trace in `sih_diagnose_long.txt`; row level figures marked as not stored, with the stored figure (774 s) added |
| 10 | Medium | README, VALIDATION, ONE_PAGER, EVALUATION | "~185 µs" while `throughput.json` says 187.7 | 187.7 µs everywhere, with the source file |
| 11 | Medium | VALIDATION.md, README.md, ADAPTERS.md, CONTRIBUTING.md | the sitl1 fault at about 78 s called a "real receiver fault"; non canonical labels SYNTHETIC, "real-log" | fault labelled SITL FAULT in VALIDATION; labels changed to SIMULATED and REAL LOG |
| 12 | Medium | EDGE_PROPOSAL.md | "in PX4 logs" and "the real logs" for results that come from SIH logs | now says "the two PX4 SIH logs" |
| 13 | Medium | MCP.md, RUN_LOG.md | a named commercial MCP client as the only example; run log phrased as a report to someone else; local paths | generic MCP host; run log reworded; paths removed |
| 14 | Medium | VALIDATION.md | the preregistration did not disclose that `sih_inject.py` and its sitl1 defaults predate it | disclosure paragraph added |
| 15 | Medium | README.md, TECHNICAL_REPORT.md, ONE_PAGER.md | regional interference claims without a source ("hundreds of jamming incidents", "routine") | replaced with the sourced figures in EDGE_PROPOSAL.md |
| 16 | Medium | plan.md | stale status and many differences from the code | status note added (see "Left alone") |
| 17 | Medium | README.md | garbled soft jamming sentence | "the baseline's latency is lower (4.1 s vs 5.0 s) and its navigation error is equal (11 m)" |
| 18 | Medium | SECURITY.md | said the service binds to 127.0.0.1; the container binds 0.0.0.0 | both documented |
| 20, 21 | Low | README, ADAPTERS, ONE_PAGER, VALIDATION, plan, EVALUATION, TECHNICAL_REPORT | em and en dashes | replaced |
| 22 | Low | README, TECHNICAL_REPORT, EDGE_PROPOSAL | salesy wording ("nastiest", "the software side is ready", "most useful") | reworded |
| 25 | Low | API.md, MCP.md, TECHNICAL_REPORT.md, ONE_PAGER.md | independence notices did not name EDGE Group | added |
| 26 | Low | README.md, CONTRIBUTING.md | test time "~1 min"; measured 547 s | "about 9 min" |
| 27 | Low | RUN_LOG.md, PREREGISTRATION_SIH.md | time zone written as UTC+3; commits are UTC+4 | corrected to UTC+4 (label only; the commit history is the record of order) |
| 28 | Low | README.md | carry off navigation error row did not say which scenario | row now says stealth carry off |
| 29 | Low | API.md, MCP.md | example payload values not marked | marked as illustrative |

## Left alone, with reasons

| # | severity | where | problem | why it was left |
|---|---|---|---|---|
| 8 | Medium | TRACKS.md, README.md, TECHNICAL_REPORT.md | track trust figures (precision/recall 1.00) have no results file or reproduce command | producing new results files is outside a docs and labels pass; the figures are already labelled as simulated with a same author caveat. Next step: add `docs/results/tracks.*` from `marsad.tracks.sim.evaluate` |
| 11 (part) | Medium | `scripts/sih_inject.py`, `sih_inject*.txt` | the script prints "SIH log + injected attack" rather than the canonical "SIH + INJECTED", and its help text calls the fault "real" | changing the script would change the published console output; the meaning is the same. Fix with the next code change |
| 16 (part) | Medium | plan.md | NumPy core, `marsad sim`, Python 3.11+, ruff/mypy/Windows CI, extras, tags v0.2.0/v0.5.0, HARDWARE.md, ROADMAP.md | plan.md is the historical plan; a status note now says the code and README win, rather than rewriting history |
| 19 | Medium | `src/marsad/api/texts.py` | the MCP `limits` text says Marsad has not been validated on real flight logs | source code string, outside a docs pass; it errs on the side of understatement |
| 23 | Low | `scripts/trace.py`, `scripts/dump_gnss.py` | small debug helpers, not referenced | kept as the author's working tools; they do not affect results |
| 24 | Low | `docs/img/dashboard-spoof-drift.png`, DASHBOARD.md | screenshot shows version 0.1.0 and an older footer; README caption says orange and DASHBOARD.md says blue for the advised track | regenerating screenshots needs the dashboard running in a browser; left for the next UI pass |
| 25 (part) | Low | `texts.py`, `dashboard/index.html` | independence notice in code does not name EDGE Group | source code, outside a docs pass |
| 28 (part) | Low | EVALUATION.md | reference bias "up to 0.06/0.08" while the generator clips at 1.2 times that | needs a check of the generator and possibly a results change; noted for the next evaluation |
| 30 | Low | plan.md | lists tags that were never created | covered by the plan.md status note |
| 31 | Low | GitHub repository topics | topic `gps-spoofing-data` suggests real spoofing data | repository settings were not in scope; recommended for removal by the owner |
| none | Low | `docs/results/*.md` | en dash placeholders written by `scripts/run_eval.py` | generated files from published results; changing them would alter the v1.1.0 results. Fix in the script before the next run |

## Found while running the SIH evaluation (most important)

The inertial detector weights its evidence by the time since the previous sample of any kind. When the reference
arrives faster than GNSS (about 125 Hz against 8 Hz in the PX4 SIH logs), drift evidence accrues at roughly 6% of
its intended rate. This is why drifts were missed in a 32 s window and caught only after about 100 s or more in a
230 s window. Fixing it changes engine behaviour and the v1.1.0 numbers, so it is left for a separate,
preregistered change (VALIDATION.md, "Why the drifts were missed").
