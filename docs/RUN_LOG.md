# Run log, 2026-10-16

## Summary

(written at the end of the run)

## Log

Times are local (AST, UTC+3).

* 05:03 Working folder: fresh clone of hudasol/marsad into `Downloads/projects/Marsad/marsad`. The older checkout in `Documents/marsad-git` was left untouched (its only local change was line endings in `scripts/sitl_flight.py`). Decision: work in a clean clone so nothing in the old checkout is altered.
* 05:04 Copied `flight1.ulg`, `flight2.ulg`, `sitl1.ulg` and `sitl_events.txt` from the old checkout into the clone (copies, originals kept). They are not committed.
* 05:05 Python: the `python` alias is the Windows Store stub; used `py -3.13 -m venv .venv` and `pip install -e ".[dev]"`.
* 05:06 Found that annotated tag `v1.1.0` already exists on `1f17c9f` on the remote, so task 3a only needs `v1.2.0`.
* 05:20 Wrote `docs/PREREGISTRATION_SIH.md` before running `scripts/sih_inject.py`.
