# Preregistration: baseline lock for version 1.5.0

Written on 2026-11-03 (UTC+4), before the v1.4.0 engine was replayed on any real flight in this repository.

## Question

Does the v1.4.0 engine, and each reimplemented baseline, stay silent on real PX4 flights that contain no attack, and
does the repository reproduce its own committed held out numbers from a fresh clone?

## Design

* Fresh clone of `hudasol/marsad` at commit `cac46bf`, `pip install -e ".[dev]"`, full test suite, `ruff check`,
  `ruff format --check`, `scripts/check_heldout.py`. Label: SIMULATED for the held out comparison.
* Replay of the engine (`marsad replay`) and of the baselines (`scripts/replay_baselines.py`) on real flights.
  Label: REAL LOG. The original `flight1.ulg` and `flight2.ulg` (SHA256 in DATA.md) are not on the build machine and
  their Flight Review identifiers were never recorded. They are therefore replaced by the corpus of the real flight
  package (`PREREGISTRATION_REAL_CORPUS.md`); the first five logs of that corpus serve as the baseline lock sample.
  The sitl1 and sitl2 clean replays are re run as a second check (label SIH, no attack).

## Predictions

| row | prediction |
|---|---|
| tests | 185 pass, no skips that were not present at v1.4.0 |
| lint | `ruff check` and `ruff format --check` report no findings |
| `check_heldout.py` | 360 runs, 0 differences |
| Marsad on sitl2 clean (full length) | 100% of samples TRUSTED |
| Marsad on each of the five lock logs | 100% of samples TRUSTED, minimum P(nominal) between 0.90 and 0.99 |
| window baseline on the lock logs | at least one of five flights raises an alarm (it alarms in 23% of nominal simulated runs) |

The last row can fail: the real flights may be calm enough that the window test stays silent as well.

## Risks

Real logs from boards with a GNSS receiver that reports a different fix cadence may expose assumptions of the
adapter. Any such finding is recorded and the log is kept in the sample.

## Kill criteria

None; this is a measurement. A non TRUSTED sample on a real log is reported in the README headline area.

## Outcome

Scored 2026-11-03 (UTC+4), late: it was left empty until the review of the release.

| row | result | verdict |
|---|---|---|
| tests | 185 passed at the end of the engineering foundation work | HIT |
| lint | `ruff check` and `ruff format --check` clean | HIT |
| `check_heldout.py` | 0 differences after the engine was split into stages | HIT |
| sitl2 clean, full length | not re run: `sitl2.ulg` is not on the build machine | NOT SCORED |
| Marsad on each of the five lock logs, 100% TRUSTED | one of the five pilot logs, a VTOL with a 1 Hz receiver, was DENIED for 95% of its flight (see Amendment 2 of `PREREGISTRATION_REAL_CORPUS.md`) | MISS |
| window baseline alarms on at least one of five | not scored separately; the 101 flight corpus supersedes the five log sample (window alarmed on 27 of 101 flights) | NOT SCORED |

The false alarm side of this question is answered by the corpus, where the result is a miss.
