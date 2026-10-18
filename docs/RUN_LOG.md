# Run log, 2026-10-16 to 2026-10-18

## Summary, 2026-10-18 (v1.3.0 run)

1. Done: all seven phases; v1.3.0 tagged on the final commit and released with sitl1.ulg, sitl2.ulg and SHA256SUMS.txt.
2. Docs now present post fix numbers; v1.2.0 numbers appear only labelled as before (README, ONE_PAGER, TECHNICAL_REPORT, EDGE_PROPOSAL, MILESTONES, RESUME_BULLET).
3. Measured (SIH + INJECTED, exploratory): at 0.1 m/s the bias estimator absorbs 79% of a velocity consistent drift (peak z 0.55); with honest velocity peak z 1.06.
4. Measured: 143 tests pass locally (211 s); SHA256 of all four logs recorded in DATA.md.
5. Written: KNOWN_LIMITS.md (cost 21.7 m and 18.8 m at 0.5 m/s), PREREGISTRATION_BIAS.md (proposal only), REAL_DATA_SOURCES.md, REVIEW_FINDINGS addendum.
6. Corrected the brief: post fix offsets are 18.8 to 22.4 m (not 21.7 m at the top); laptop control 738.9 to 1,211.5 us (unrounded).
7. Found: README and EVALUATION reproduce commands would have overwritten published v1.1.0 and v1.2.0 results; fixed.
8. Failed: nothing blocking; one preregistered miss remains (0.25 m/s velocity consistent).
9. Manual: decide on PREREGISTRATION_BIAS.md (implement or drop).
10. Manual: confirm free access to the IEEE DataPort UAV Attack Dataset before using it (page states both free account and subscription).
11. Manual: remove the repository topic gps-spoofing-data; regenerate the dashboard screenshot.
12. Manual: the review.px4.io identifiers of flight1 and flight2 were never recorded; recover them with download_logs.py --uuid if needed.

## Addendum, 2026-10-18: status of the 2026-10-16 summary

* Item 5 (defect found, engine not changed) is resolved: the evidence weighting fix was preregistered
  (PREREGISTRATION_WEIGHTING.md, commit 5756142), made in commit 8c7b858 and scored in VALIDATION.md.
* Item 10 (decide on the weighting fix) is resolved: the fix was made and is released in v1.3.0.
* Items 3 and 4 describe the v1.2.0 engine and stay as recorded; post fix numbers are in docs/results/weighting_fix/.

## Summary (2026-10-16 to 2026-10-18, v1.2.0 run)

1. Done: all six phases. Preregistered predictions, ran SIH + INJECTED evaluations on sitl1 (32 s window) and a new clean 300 s SIH flight, sitl2 (230 s window), fixed CI, wrote the proposal seed, ran a hostile review, wrote the resume entry, tagged and released v1.2.0.
2. Measured (SIH + INJECTED): jumps of 50, 200, 1000 m detected 4/4 on the first attacked fix in both logs; clean logs silent.
3. Measured (SIH + INJECTED): drifts of 0.5 to 2 m/s missed 0/4 in 32 s; in 230 s detected 4/4 after median 98.1 to 204.6 s at median offsets of 77.1 to 186.8 m; 0.1 and 0.25 m/s missed.
4. Predictions: sitl1 6 of 10 Marsad rows missed (all drifts); sitl2 1 miss (0.5 m/s detected though predicted missed). Gate baseline matched every prediction.
5. Found (exploratory): drift evidence is weighted by the gap to the previous sample of any kind, so a 125 Hz reference dilutes 8 Hz GNSS evidence to about 6%. Engine not changed.
6. Measured (REAL LOG): zero alarms over 911 s and 334 s of two public PX4 flights; output now stored in docs/results/real_logs.txt.
7. CI: docker and ros2 jobs had failed on every run since 2026-10-11; both fixed; all seven jobs pass.
8. Changed outside docs: `--no-faults` flag, drift rates 0.1 and 0.25 added to the sih_inject.py case list, new script sih_diagnose.py, CI file, version string 1.2.0.
9. Failed: first WSL start timed out (second attempt worked); first ros2 CI fix was insufficient (second fix worked).
10. Manual: decide on the evidence weighting fix (changes v1.1.0 numbers; preregister it first).
11. Manual: remove the repository topic `gps-spoofing-data`; regenerate the dashboard screenshot.
12. Manual: keep sitl2.ulg safe (only copy is in the working clone and in the WSL PX4 log folder); the older local checkout was not touched.
13. Manual: review docs/EDGE_PROPOSAL.md before sending it anywhere; it claims no affiliation and names no individuals.

## Log

Times are local (UTC+4, matching the commit timestamps).

* 05:03 Working folder: fresh clone of hudasol/marsad into a new folder. The older local checkout was left untouched (its only local change was line endings in `scripts/sitl_flight.py`). Decision: work in a clean clone so nothing in the old checkout is altered.
* 05:04 Copied `flight1.ulg`, `flight2.ulg`, `sitl1.ulg` and `sitl_events.txt` from the old checkout into the clone (copies, originals kept). They are not committed.
* 05:05 Python: the `python` alias is the Windows Store stub; used `py -3.13 -m venv .venv` and `pip install -e ".[dev]"`.
* 05:06 Found that annotated tag `v1.1.0` already exists on `1f17c9f` on the remote, so task 3a only needs `v1.2.0`.
* 05:09 Wrote `docs/PREREGISTRATION_SIH.md` before running `scripts/sih_inject.py`.
* 05:10 Committed the preregistration and `.gitignore` (`*.ulg`, `sitl_events.txt`) and pushed. Decision: keep flight logs out of git; they are large and are the owner's data.
* 05:10 Ran `python scripts/sih_inject.py sitl1.ulg --out docs/results/sih_inject.json` (2 min 13 s). Result: clean log 0 alarms; jumps 50, 200, 1000 m detected 4/4 at 0.0 s; all six drift cases 0/4 for Marsad. Six preregistered Marsad predictions missed.
* 05:12 Added `--no-faults` to `scripts/sitl_flight.py`; default unchanged. The final "clear fault" command is only sent when faults were configured.
* 05:13 Diagnosis (exploratory): drift z score rises to 7.31 during a 2 m/s drift but P(nominal) only falls to 0.919. Reference samples arrive every 0.008 s and GNSS every 0.124 s, and the inertial detector weights evidence by the gap to the previous sample of any kind. Fed at the GNSS epoch rate, 2 m/s is detected 4/4 (about 16 s) and 1 m/s 4/4 (about 26 s).
* 05:15 Decision: committed the diagnosis as a separate script, `scripts/sih_diagnose.py`, so the numbers are reproducible. It changes only the input stream; the engine, thresholds and v1.1.0 results are untouched. This is outside the literal task list and is flagged here as a scope decision.
* 05:16 Test suite: 140 passed in 547 s (the task list expected 137; the three extra tests are `tests/test_sih_inject.py`).
* 05:17 First WSL start failed (`Wsl/Service/CreateInstance/CreateVm/0x800705b4`, timeout). Second attempt at 05:19 started the VM.
* 05:21 PX4 SIH started headless (`HEADLESS=1 make px4_sitl sihsim_quadx` with stdin from a FIFO), ready in 12 s, `commander takeoff`, then `python3 scripts/sitl_flight.py --no-faults` (exit 0, 302.4 s), `commander land`, disarmed after 16 s. Log `2026-10-16/01_21_34.ulg` copied to `sitl2.ulg` (93 MB).
* 05:30 Work paused; resumed on 2026-10-17 at 23:28.
* 23:30 Checked `sitl2.ulg`: `marsad inspect` parses it; `sitl_timeline.py sitl2.ulg 10` shows TRUSTED throughout; over all 3,212 fixes the GNSS error against ground truth is at most 0.30 m (median 0.10 m); 0 non TRUSTED samples of 51,615. Accepted. Saved to `docs/results/sitl2_timeline.txt`.
* 23:34 Wrote and committed a preregistration addendum for the long run before running it.
* 23:35 Changed only the case list in `scripts/sih_inject.py` to drift rates 0.1, 0.25, 0.5, 1 and 2 m/s (flagged change). Consequence: rerunning the sitl1 command now prints two extra rows (0.1 and 0.25 m/s); the existing rows are unchanged.
* 23:35 Started `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_inject_long.json`. The planned numbers were kept: attack window 230 s, during the offboard square (offboard from about 32 s to about 322 s uptime).
* 23:37 CI: every run on main since 2026-10-11 failed in two jobs. docker: `Invalid container name (m)`; fixed by naming the container `marsad-ci`. ros2: pip 22 in `ros:humble` cannot do a PEP 660 editable install; fixed by a non editable install. Docker Desktop is not running locally, so only what the logs show was fixed. test, core is stdlib only and bench smoke were passing.
* 23:40 Found a GitHub Release for v1.1.0 already exists; only v1.2.0 is needed. Repository topic `gps-spoofing-data` is misleading (no real spoofing data in the repository); left unchanged because changing repository settings was not asked for; listed in the review findings.
* 23:42 Sources for the proposal, all opened: OCCRP news item of 5 March 2026; EASA page on GNSS outages and alterations (SIB 2022-02R4); ZAWYA/TradeArabia article based on BBC reporting. A CNN syndication page had no body text and is not cited.
* 23:46 First ros2 CI fix (non editable install) still failed: the stock pip 22 / setuptools 59 built an `UNKNOWN-0.0.0` wheel. Second fix upgrades pip and setuptools first; ros2 passes from commit 2493d31 on.
* 23:48 Version string bumped to 1.2.0 in `pyproject.toml` and `src/marsad/__init__.py` (no engine change).
* 23:52 Long run finished (17 min): 0.1 and 0.25 m/s 0/4; 0.5 m/s 4/4 (204.6 s, 159.1 s); 1 m/s 4/4 (112.3 s, 110.1 s); 2 m/s 4/4 (98.4 s, 98.1 s); jumps 4/4 at 0.0 s; clean 0. One preregistered miss (0.5 m/s).
* 23:53 Exploratory diagnosis on sitl2 at the GNSS epoch rate: 0.5 m/s 4/4 at 48.2 s and 42.5 s; 1 m/s 27.2 s and 25.5 s; 2 m/s 16.2 s and 15.7 s.
* 23:54 Checked a possible transient alarm: the 2 m/s north and east cases go to DEGRADED and then DENIED and stay there; the latency is not a transient.
* 23:55 README status, independence notice (EDGE Group added) and roadmap updated; MILESTONES rewritten with a v1.2.0 changelog.
* 23:56 Wrote docs/EDGE_PROPOSAL.md from the three opened sources and numbers in docs/results only.
* 23:57 Replayed flight1.ulg and flight2.ulg with `marsad replay` and stored the output (REAL LOG); figures match VALIDATION.md (911 s and 334 s, TRUSTED 100%).
* 23:58 README "For reviewers" section with one reproduce command per table.
* 23:59 Wrote docs/RESUME_BULLET.md. The SIH drift results are weak, so the second line states them as a limitation found.
* 00:00 Hostile review by a reviewer that had not seen the work: 31 findings. Fixed the documentation and label items; logged the rest with reasons in docs/REVIEW_FINDINGS.md. No dead relative links remain.
* 00:12 Final commit of the run; annotated tag v1.2.0 placed on it and pushed; GitHub Release v1.2.0 created and the empty v1.1.0 release notes filled from MILESTONES.md.

## Log, 2026-10-18 (v1.3.0 run)

* 11:51 Pulled main (weighting fix commits 5756142 to 8f0e89d, all authored without trailers). Read the state documents.
* 11:53 Grep for stale wording found the pre fix SIH numbers (98.1 to 204.6 s) presented as current in README, ONE_PAGER, TECHNICAL_REPORT, EDGE_PROPOSAL, MILESTONES and RESUME_BULLET.
* 11:54 Decision: the brief quoted "18.8 to 21.7 m" for the post fix median offsets of drifts of 0.5 m/s and faster; docs/results/weighting_fix/sih_inject_long.txt gives 18.8 to 22.4 m (21.7 m is the 0.5 m/s velocity consistent case alone), and 18.8 to 22.8 m if sitl1 is included. The documents use 18.8 to 22.4 m for the 230 s window.
* 11:54 Decision: the brief quoted the laptop throughput control as "739 to 1,212 us"; throughput_control.txt gives 738.9 to 1,211.5 us. The documents use the unrounded values.
* 11:54 README reproduce table pointed the current engine at the v1.2.0 output files, which would overwrite published results; repointed to docs/results/weighting_fix/.
* 11:55 Phase 1 commits: README, MILESTONES, ONE_PAGER, TECHNICAL_REPORT, EDGE_PROPOSAL, outcome pointers in both preregistrations, EVALUATION soft jamming line.
* 11:56 Phase 2: ran `python scripts/bias_trace.py sitl2.ulg --rate 0.1` (25 s) to measure the 0.1 m/s miss rather than argue it; new file docs/results/weighting_fix/bias_trace_sitl2_0.1.txt (exploratory, SIH + INJECTED). Velocity consistent: estimate reached -0.079 m/s (79% of the drift), peak z 0.55. Velocity honest: estimate near zero, peak z 1.06.
* 11:57 Wrote docs/KNOWN_LIMITS.md. Decision: cost stated as 21.7 m (velocity consistent) and 18.8 m (honest velocity) for the slowest drift caught in both modes, 0.5 m/s.
* 11:58 Decision: wrote a possible engine change (a guard on fast moving bias estimates) as docs/PREREGISTRATION_BIAS.md with predictions, and did not implement it, as instructed. Letting the estimator learn on every fix was considered and not proposed.
* 12:00 Phase 3: SHA256 of the four logs computed with sha256sum; docs/DATA.md written from each log's ULog header (PX4 v1.18.0 beta build fe24ec22 for both SIH logs, v1.15.3 and v1.17.0 for the real logs). The review.px4.io identifiers of flight1 and flight2 were never recorded; DATA.md says so instead of inventing them. A SHA256SUMS.txt for the two SIH logs was built and verified locally.
* 12:00 Decision: tag and release at the end of the run so the v1.3.0 tag sits on the final commit; the version bump and changelog were committed now.
* 12:01 Phase 4: version 1.3.0 committed; v1.3.0 changelog written in MILESTONES.md.
* 12:02 Phase 5: resume entry rewritten with post fix numbers. Decision: median offset quoted as 18.8 to 22.4 m (230 s window), not the 18.8 to 21.7 m in the brief, which does not match the results file.
* 12:04 Phase 6: surveyed public sources; opened every linked page; downloaded nothing. Found one directly readable source with real RF attacks on a real receiver (IEEE DataPort UAV Attack Dataset, 683.88 MB, access terms ambiguous: free account or subscription), several raw I/Q sets that need a software receiver first, and excluded one subscription dataset. No log identifier with jamming_state 2 or 3 was verified, so none is given; the method to find one is described.
* 12:05 Phase 7: hostile review started by a reviewer that had not seen the work; full test suite run in parallel: 143 passed in 211 s.
* 12:12 Review returned 28 findings (4 High, 11 Medium, 13 Low). Main ones: throughput 187.7 us presented as the current engine cost; reproduce commands in EVALUATION and VALIDATION that would overwrite published results. Fixed the documentation and label items in 12 per document commits; logged the rest with reasons in the REVIEW_FINDINGS addendum.
* 12:17 Decision: the v1.3.0 engine cost is quoted as 892.3 to 1,263.0 us on a Windows laptop (control range and the run_eval figure for the fixed engine), with the v1.1.0 cloud core figure labelled as such.
* 12:18 Final commit of the run; annotated tag v1.3.0 placed on it and pushed; GitHub Release v1.3.0 created from the MILESTONES changelog with sitl1.ulg, sitl2.ulg and SHA256SUMS.txt attached; CI checked on the tagged commit.
