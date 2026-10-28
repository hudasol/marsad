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

**Status after v1.2.0: fixed.** The weighting was changed in a separate, preregistered change
([PREREGISTRATION_WEIGHTING.md](PREREGISTRATION_WEIGHTING.md)); the same defect was found and fixed in the kinematic,
signal and engine evidence and in the bias estimator. Scored results are in VALIDATION.md ("Evidence weighting fix")
and EVALUATION.md; the v1.1.0 and v1.2.0 results in `docs/results/` are unchanged. The fix also exposed a separate
limitation of the bias estimator (it can absorb part of a velocity consistent drift), which is left open.

## Addendum, 2026-10-18: review before v1.3.0

A second hostile review was run after the evidence weighting fix and the documentation update, by a reviewer that
had not seen the work. It confirmed that every post fix number in README, EDGE_PROPOSAL, ONE_PAGER,
TECHNICAL_REPORT, RESUME_BULLET, KNOWN_LIMITS and DATA matches `docs/results/weighting_fix/`, that no relative link is
dead, that there are no em or en dashes, emojis or attribution problems, and that 143 tests collect (all 143 pass
locally, 211 s).

### Fixed

| severity | where | problem | fix |
|---|---|---|---|
| High | README, EDGE_PROPOSAL, ONE_PAGER, VALIDATION, EVALUATION | 187.7 µs (v1.1.0 engine, cloud core) shown as the current engine cost; laptop range omitted the 1,263.0 µs `run_eval.py` figure | v1.3.0 engine quoted as 892.3 to 1,263.0 µs on a Windows laptop, v1.1.0 cloud figure labelled as such |
| High | EVALUATION.md | reproduce command without `--out` would overwrite the published v1.1.0 files | marked "at tag v1.1.0", current command given with `--out docs/results/weighting_fix` |
| Medium | VALIDATION.md | v1.2.0 reproduce commands would overwrite v1.2.0 files if run at HEAD | each marked "at tag v1.2.0" |
| Medium | README.md | `marsad bench --seeds 30` described as reproducing the benchmark (it uses seeds 0 to 29, the tables use 5000+) | comment corrected |
| Medium | MILESTONES.md, TECHNICAL_REPORT.md | "only soft jamming changed" while two JSON only values also moved | scoped to the tables, JSON changes named |
| Medium | EDGE_PROPOSAL.md | version 1.2.0; "real PX4 simulation in hardware log" suggested a flight controller | version 1.3.0; "PX4 software in the loop log using the SIH simulator" |
| Medium | RESUME_BULLET.md, VALIDATION.md | offset range 18.8 to 22.8 m not scoped (the 0.25 m/s honest case alarmed at 27.1 m) | scoped to drifts of 0.5 m/s and faster |
| Medium | README.md | "Where it does not work" mixed labels; "real PX4 SIH logs" | labels inline, "real" removed |
| Low | KNOWN_LIMITS, VALIDATION, TECHNICAL_REPORT, EVALUATION | rounded figures (about 35%, 739, 1,182, 892, 1,212, 46 µs) | exact values (34.8%, 738.9, 1,181.8, 892.3, 1,211.5, 45.7 µs) |
| Low | README.md | test time 547 s measured with 140 tests | 211 s for 143 tests, measured in this run |
| Low | DATA.md, VALIDATION.md | timestamps and "10 m altitude" without a stated basis | pyulog first and last timestamps; altitude from simulator truth |
| Low | README, DATA, VALIDATION | clean SIH logs labelled three different ways, none canonical | "SIH + INJECTED (zero offset)" everywhere in prose; `clean_margin.txt` keeps its generated wording |
| Low | VALIDATION.md | "z passed 1 at about 95 s" (trace: 0.94 at 95 s, 1.20 at 115 s) | "between 95 and 115 s" |
| Low | VALIDATION.md | two post fix result files stamped with package version 1.2.0 | note added: produced before the version bump, engine code is the fixed one |
| Low | plan.md | status v1.2.0; language choice justified by a named institution; independence line without EDGE Group | updated |
| Low | README.md | reproduce rows printed to the console without saying how the `.txt` files were written | output redirects added; rows for `clean_margin.py` and `bias_trace.py --rate 0.1` added |

### Left alone, with reasons

| severity | where | problem | why |
|---|---|---|---|
| Medium | README.md, TECHNICAL_REPORT.md, TRACKS.md | track trust figures (precision/recall 1.00, 3 to 15 km) have no results file | unchanged from the first review (finding 8); needs a new results run, outside a docs pass |
| Medium | GitHub repository topics | `gps-spoofing-data` still set | repository settings are the owner's; recommended for removal |
| Low | EVALUATION.md | 84.7%, 47.5 s, 48.1 s, 20.3 s are conventionally rounded from the JSON (84.666, 47.456, 48.086, 20.268) | standard rounding to the precision shown, not exaggeration; left as written in the post fix evaluation |
| Low | README.md, DATA.md | sizes "about 23 to 190 MB" (189.86 MB) | marked "about"; DATA.md gives exact byte counts |
| Low | README.md | run times (12, 39 and 16 minutes) taken from EVALUATION and VALIDATION rather than a results file | operational guidance, not results |
| Low | VALIDATION.md | 15.8 s and 16.2 s in the mixed rate test, "about 10 times faster" | asserted by `tests/test_mixed_rate.py` and the sample counts in PREREGISTRATION_WEIGHTING.md; not separate result files |
| Low | REVIEW_FINDINGS.md (first review) | promised script fixes (en dash placeholders in `run_eval.py` output, "real" fault wording in `sih_inject.py`) not made in the weighting fix | still open; script output changes would alter generated result files; moved here as left alone for v1.3.0 |
| Low | README.md, DASHBOARD.md | caption colour mismatch, stale screenshot | needs a browser session with the dashboard; unchanged |
| Low | `src/marsad/api/texts.py` | MCP limits text understates the REAL LOG result | source code string; it understates rather than overstates |
| Low | docs/EDGE_PROPOSAL.md file name | names EDGE Group | the owner chose the name; the content disclaims any affiliation |
| Low | DATA.md, MILESTONES.md | describe the v1.3.0 release and its assets before they exist | the release is created at the end of this run; checked afterwards |
