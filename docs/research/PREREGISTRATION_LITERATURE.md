# Preregistration: engine on the literature scenario family and the sealed split

Written on 2026-11-03 (UTC+4), after the family and the runner were committed and after the development run was
started, but before any of its output was opened. Predictions are fixed now and are scored as written. The engine is
the v1.4.0 behaviour (the cadence trial was not adopted, see [PREREGISTRATION_CADENCE.md](PREREGISTRATION_CADENCE.md)).
No engine change is planned on this family, so the sealed run is a measurement, not a test of a tuned system.

## Question

How does the engine behave on attacks specified from published descriptions (Tippenhauer et al. 2011, TEXBAT
pages, a jammer impact study) rather than by its own author, and does the result on the sealed seeds match the
development seeds?

## Where the world is synthetic

Everything here is SIMULATED (LITERATURE). The clean vehicle, receiver and reference come from the first family's
generator, so world and engine still share an author. Only the attack parameters come from outside, and several
mappings from a published quantity to a receiver measurement are marked ASSUMED in
[SCENARIOS_LITERATURE.md](SCENARIOS_LITERATURE.md). A result here is not evidence about any real attack.

## Design

* Family: five attack kinds (`lit_switch`, `lit_takeover`, `lit_time_push`, `lit_equal_power`, `lit_jam_chirp`) and three
  benign kinds (`nominal`, `benign_obstruction`, `benign_multipath`).
* Seeds: development 0 to 29 (30 per kind). Sealed 7000 to 7099 (100 per kind), for this family and for the first
  family's held out generator. The sealed split is run once, by `scripts/run_literature.py --final`, at the end.
* Unit: one simulated run. Detection means any non TRUSTED sample at or after the attack start. A false alarm means
  any non TRUSTED sample in a benign run, or before the attack start in an attack run.
* Intervals: Clopper Pearson 95%. Paired comparisons with the exact McNemar test. Latency medians over runs that were
  detected, with a bootstrap of 10,000 resamples (seed 20261103).
* Simple baseline: the plain gate. Competitor: the sliding window displacement test (`window`). The stack is reported.

## Predictions

Development seeds, n = 30 per kind.

| id | prediction |
|---|---|
| L1 | `lit_switch`: detected in at least 28 of 30 runs (a step of 100 m or more) |
| L2 | `lit_takeover`: detected in at least 24 of 30 runs. This can fail because the slowest carry off (0.05 m/s^2) is slow |
| L3 | `lit_time_push`: detected in at least 20 of 30 runs. This can fail because offsets of 20 to 72 m grow slowly |
| L4 | `lit_equal_power`: detected in at least 24 of 30 runs |
| L5 | `lit_jam_chirp`: detected in at least 27 of 30 runs. This can fail because the AGC rise is smaller than anything the engine was tuned on |
| L6 | `nominal` and `benign_multipath`: no more than 3 of 30 runs with a false alarm each; `benign_obstruction`: alarm in at least 25 of 30 (a real loss of fix is reported, this is the known cost) |
| L7 | the plain gate detects fewer runs than Marsad on `lit_takeover` and on `lit_time_push` |
| L8 | the window baseline has a shorter median latency than Marsad on `lit_takeover` and on `lit_time_push` (as in the earlier injected studies) |

Sealed seeds, n = 100 per kind.

| id | prediction |
|---|---|
| S1 | for each of the five literature kinds, the sealed detection share is not lower than the development share by more than 10 percentage points |
| S2 | first family, held out generator on seeds 7000 to 7099: for each attack kind the detection share is not lower than the share on seeds 5000 onward in `docs/results/heldout.json` by more than 10 percentage points |
| S3 | `nominal` and `benign_multipath`, both families: false alarms in at most 5 of 100 runs |

## Risks named in advance

* Thirty runs per kind give intervals of about 25 percentage points; a prediction near the threshold is weak evidence.
* Detection counts any non TRUSTED sample, so a run that alarms on the benign part of the attack is counted. The
  pre attack false alarm count is reported next to it.
* The thresholds above were chosen from the family description and from earlier results, not from dev output.

## Kill criteria

None for the engine; there is no change to test. The sealed run is not repeated, whatever the result.

## Outcome

Empty until scored.
