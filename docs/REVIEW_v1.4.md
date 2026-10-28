# Marsad cold review, v1.4

A review written from the position of an engineer who had not seen the project before opening the repository. The score is out of 10.

## Score

| Area | Score | Note |
|---|---|---|
| Problem framing and scope | 8 | The claim is narrow and the label on every number says where it came from. |
| Evidence and method | 8 | Preregistered predictions, held out seeds, misses recorded. |
| Baselines | 7 | Four real baselines on the same scenarios. Real log coverage is still thin. |
| Engine correctness | 6.5 | Fail open on a bad first fix and a state leak in `reset()` were found. Both are fixed. |
| Service and security | 6 | Open by default bind, chunked body bypass and no audit trail were found. All fixed. |
| Code structure | 5.5 | `TrustEngine.update` is one long method with constants inside it. Open. |
| Tests and CI | 7 | Good coverage of behaviour. No type checking and no coverage gate yet. |
| Dashboard | 6.5 | Worked, but looked templated. Rebuilt with a flat palette and a space time view. |
| Documentation | 7 | Accurate after cleanup. Some repetition of labels in the README. |
| **Overall** | **6.5** | Before the changes in this round. |

## Findings and status

| Finding | Status |
|---|---|
| A non finite or out of range first GNSS fix passed straight into the local frame | Fixed. `_clean_fix`, rejection counter, 12 new tests |
| `reset()` kept detector state from the previous run | Fixed. All detectors rebuilt |
| Overlapping demo starts leaked a replay loop | Fixed. Lock around start and stop |
| The API bound to a public address without a key | Fixed. Refused unless `--insecure` is given |
| A chunked request body bypassed the size cap | Fixed. Byte counting ASGI middleware |
| Acknowledgements were not recorded | Fixed. `GET /v1/audit` |
| Cost claim in the report had no measurement behind it | Fixed. Measured figure used |
| README left out two scenario rows | Fixed |
| Nothing checked that published numbers still come out of the code | Fixed. `scripts/check_heldout.py` and a CI job |
| Release workflow did not run the tests | Fixed |
| Dashboard looked generated | Fixed. New palette, one title bar, three.js space time view |
| No content security policy | Fixed. Script and style from self only |
| `TrustEngine.update` is long and holds magic numbers | Open |
| `pop(0)` windows in the kinematic detector | Open |
| Bare `except Exception` and `assert` used as validation in a few modules | Open |
| No type hints or mypy on the core | Open |
| No property based tests or coverage gate | Open |
| Workflow actions are pinned by tag, not by commit | Open |
| Acknowledge uses the same key as read access | Open |

## Plan for the open items

1. Split `update` into stages (input cleaning, reference integration, evidence, state, learning). Move the constants into `EngineConfig`. Gate every step on `scripts/check_heldout.py` so the held out output stays byte identical.
2. Switch the detector windows to `collections.deque`.
3. Replace `assert` checks with explicit errors and narrow the broad exception handlers.
4. Add type hints to the core and run mypy in CI.
5. Add hypothesis tests for the engine input path and a coverage threshold.
6. Pin action versions by commit and add a separate credential for acknowledgements.
