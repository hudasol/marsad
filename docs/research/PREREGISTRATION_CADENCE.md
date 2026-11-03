# Preregistration: receiver cadence and start up false alarms (engine change)

Written on 2026-11-03 (UTC+4), after the real corpus replay (`PREREGISTRATION_REAL_CORPUS.md`, Outcome) and before any
engine change. Label for every number here: **REAL LOG** unless stated.

## Question

Can two small changes remove the alarms that the real corpus showed on flights where nothing was wrong, without
changing any result on the simulated and injected studies?

## What the corpus showed (exploratory, not preregistered)

`scripts/real_corpus_causes.py` records the evidence behind the first non TRUSTED sample of every flight that has one
(50 flights in the scoring set including the error labelled stratum; 10 in the design subset).

| first alarm | scoring set | design subset |
|---|---|---|
| fix loss shorter than 3 s, receiver at about 1 Hz (one missed epoch, gap of 1.5 to 2.9 s) | 25 + 1 at a faster rate | 1 |
| fix loss of 3 s or more | 13 | 6 |
| position far from the integrated reference ("gnss_vs_reference_drift") | 8 | 2 |
| signal down, obstruction like, or AGC rise | 3 | 1 |

Two mechanisms explain most of the first two rows. They were read from the design subset and from the log of one
scoring flight.

1. **Cadence.** `gnss_gap_timeout` is 1.5 s, a number chosen for a receiver at 5 Hz. Many logs come from receivers at
   1 Hz, and one missed epoch gives a 2 s gap. The engine goes DENIED at once and the evidence of a jammer accrues.
   Two design flights come from receivers at about 0.17 Hz (a fix every 6 s), where the engine can never be TRUSTED.
2. **Start up.** The engine counts time since its first sample as "no usable fix". A log that starts 20 to 375 s before
   the receiver has a 3D fix accrues tens of seconds of jamming evidence against a hypothesis that was never tested
   (the vehicle had no GNSS to lose), and then needs a long time to recover after the first fix. Scoring began at the
   first 3D fix (Amendment 2), so the recovery time counts as non TRUSTED.

A third mechanism, not touched here, is that once the engine is DENIED with a reference whose integral drifts, the
re-acquisition check (`reacq_cap_m`) can become unverifiable and the engine stays DENIED for the rest of the flight
(40 of the 50 alarmed scoring flights are TRUSTED for less than half of their time). Fixing it means accepting a
position that cannot be verified, which trades detection for fewer alarms, and is recorded in `KNOWN_LIMITS.md`
instead of being changed in this release.

## Design

Change 1, cadence. The gap that counts as loss of fix is `max(gnss_gap_timeout, 3.0 x m)`, where `m` is the median
interval between the last 20 usable fixes (before 5 fixes have been seen, `m` is treated as 0 and the timeout is
unchanged). A receiver at 5 Hz or faster keeps 1.5 s exactly. Constants: `gap_cadence_factor = 3.0`,
`gap_cadence_window = 20`, `gap_cadence_min_fixes = 5`, all in `EngineConfig`.

Change 2, start up. Until the first usable fix has been seen, the engine does not accrue fix loss evidence (it reports
DENIED with no fix, as before, but the posterior is not driven toward jamming by a period in which GNSS never
existed). `lost` still holds the state at DENIED until a usable fix arrives.

Both changes act only where the old code could not have behaved the same: a simulated run at 5 Hz that has a fix at its
first sample is byte identical by construction, and the test suite and `scripts/check_heldout.py` verify it.

## Data

* Development: the design subset of the real corpus (30 flights, 10 with an alarm) and the unit tests. Nothing else.
* Evaluation, once: the 101 scored flights, the 16 receiver flag flights are a subset of them; the engine is not
  changed after this evaluation.
* No simulated seeds are used for tuning. `check_heldout.py` is a regression check.

## Baselines

The v1.4.0 result on the same flights (Outcome of `PREREGISTRATION_REAL_CORPUS.md`) and the plain gate.

## Predictions

| id | prediction |
|---|---|
| C1 | `check_heldout.py` shows 0 differences, and the dev benchmark, the SIH + INJECTED tables and the REAL LOG + INJECTED undisturbed starts are unchanged where the receiver is at 5 Hz or faster |
| C2 | design subset: flights with any alarm fall from 10 of 30 to at most 7 |
| C3 | scoring set: flights 100% TRUSTED rise from 54 of 101 (53.5%) to at least 68 of 101 (67%). This can fail because the stuck DENIED mechanism is untouched |
| C4 | scoring set: flights with a DENIED sample fall from 46 of 101 to at most 32 of 101 |
| C5 | scoring set: the plain gate still alarms on fewer flights than Marsad (the gap narrows but does not close); stated so that a result in which Marsad alarms on fewer flights than the gate is read as a surprise |
| C6 | REAL LOG + INJECTED detection of a 200 m jump is not lower than with v1.4.0 at the 95% level (the change only relaxes a timeout) |

## Risks named in advance

* A longer timeout delays the denial when a 1 Hz receiver really loses its fix by up to 3 s.
* The median interval is learned from the receiver itself, so a spoofer that slows the fix rate could stretch the
  timeout. The cap is therefore `gap_cadence_cap_s = 6.0`, the loss timeout never exceeds 6 s.
* Two mechanisms are fixed while a third is not; the headline false alarm rate will stay high.

## Kill criteria

Revert the engine change (new commit) if any of the following holds: `check_heldout.py` shows a difference; any
SIH + INJECTED row changes; the REAL LOG + INJECTED jump detection falls by more than 2 percentage points; the design
subset gets worse (more flights with an alarm than before).

## Outcome

Empty until scored.
