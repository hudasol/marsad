# Run log, 2026-10-16

## Summary

(written at the end of the run)

## Log

Times are local (AST, UTC+3).

* 05:03 Working folder: fresh clone of hudasol/marsad into `Downloads/projects/Marsad/marsad`. The older checkout in `Documents/marsad-git` was left untouched (its only local change was line endings in `scripts/sitl_flight.py`). Decision: work in a clean clone so nothing in the old checkout is altered.
* 05:04 Copied `flight1.ulg`, `flight2.ulg`, `sitl1.ulg` and `sitl_events.txt` from the old checkout into the clone (copies, originals kept). They are not committed.
* 05:05 Python: the `python` alias is the Windows Store stub; used `py -3.13 -m venv .venv` and `pip install -e ".[dev]"`.
* 05:06 Found that annotated tag `v1.1.0` already exists on `1f17c9f` on the remote, so task 3a only needs `v1.2.0`.
* 05:09 Wrote `docs/PREREGISTRATION_SIH.md` before running `scripts/sih_inject.py`.
* 05:10 Committed the preregistration and `.gitignore` (`*.ulg`, `sitl_events.txt`) and pushed. Decision: keep flight logs out of git; they are large and are the owner's data.
* 05:10 Ran `python scripts/sih_inject.py sitl1.ulg --out docs/results/sih_inject.json` (2 min 13 s). Result: clean log 0 alarms; jumps 50, 200, 1000 m detected 4/4 at 0.0 s; all six drift cases 0/4 for Marsad. Six preregistered Marsad predictions missed.
* 05:12 Added `--no-faults` to `scripts/sitl_flight.py`; default unchanged. The final "clear fault" command is only sent when faults were configured.
* 05:13 Diagnosis (exploratory): drift z score rises to 7.31 during a 2 m/s drift but P(nominal) only falls to 0.919. Reference samples arrive every 0.008 s and GNSS every 0.124 s, and the inertial detector weights evidence by the gap to the previous sample of any kind. Fed at the GNSS epoch rate, 2 m/s is detected 4/4 (about 16 s) and 1 m/s 4/4 (about 26 s).
* 05:15 Decision: committed the diagnosis as a separate script, `scripts/sih_diagnose.py`, so the numbers are reproducible. It changes only the input stream; the engine, thresholds and v1.1.0 results are untouched. This is outside the literal task list and is flagged here as a scope decision.
* 05:16 Test suite: 140 passed in 547 s (the brief said 137; the three extra tests are `tests/test_sih_inject.py`).
* 05:17 First WSL start failed (`Wsl/Service/CreateInstance/CreateVm/0x800705b4`, timeout). Second attempt at 05:19 started the VM.
* 05:21 PX4 SIH started headless (`HEADLESS=1 make px4_sitl sihsim_quadx` with stdin from a FIFO), ready in 12 s, `commander takeoff`, then `python3 scripts/sitl_flight.py --no-faults` (exit 0, 302.4 s), `commander land`, disarmed after 16 s. Log `2026-10-16/01_21_34.ulg` copied to `sitl2.ulg` (93 MB).
* 05:30 Session interrupted by the owner; resumed on 2026-10-17 at 23:28.
* 23:30 Checked `sitl2.ulg`: `marsad inspect` parses it; `sitl_timeline.py sitl2.ulg 10` shows TRUSTED throughout; over all 3,212 fixes the GNSS error against ground truth is at most 0.30 m (median 0.10 m); 0 non TRUSTED samples of 51,615. Accepted. Saved to `docs/results/sitl2_timeline.txt`.
* 23:34 Wrote and committed a preregistration addendum for the long run before running it.
* 23:35 Changed only the case list in `scripts/sih_inject.py` to drift rates 0.1, 0.25, 0.5, 1 and 2 m/s (flagged change). Consequence: rerunning the sitl1 command now prints two extra rows (0.1 and 0.25 m/s); the existing rows are unchanged.
* 23:35 Started `python scripts/sih_inject.py sitl2.ulg --end 290 --t-attack 60 --out docs/results/sih_inject_long.json`. The user's numbers were kept: attack window 230 s, during the offboard square (offboard from about 32 s to about 322 s uptime).
* 23:37 CI: every run on main since 2026-10-11 failed in two jobs. docker: `Invalid container name (m)`; fixed by naming the container `marsad-ci`. ros2: pip 22 in `ros:humble` cannot do a PEP 660 editable install; fixed by a non editable install. Docker Desktop is not running locally, so only what the logs show was fixed. test, core is stdlib only and bench smoke were passing.
* 23:40 Found a GitHub Release for v1.1.0 already exists; only v1.2.0 is needed. Repository topic `gps-spoofing-data` is misleading (no real spoofing data in the repository); left unchanged because changing repository settings was not asked for; listed in the review findings.
* 23:42 Sources for the proposal, all opened: OCCRP news item of 5 March 2026; EASA page on GNSS outages and alterations (SIB 2022-02R4); ZAWYA/TradeArabia article based on BBC reporting. A CNN syndication page had no body text and is not cited.
