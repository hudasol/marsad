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

Scored 2026-11-03 (UTC+4). The trial engine (changes 1 to 3) was run once on the 101 scoring flights, on the held out SIMULATED family and on the design subset. Label: REAL LOG for the corpus rows, SIMULATED for the held out rows. Results are in `docs/results/cadence_trial_real_corpus/`, `docs/results/cadence_trial_design_c12/`, `docs/results/cadence_trial_design_c123/` and `docs/results/cadence_trial_simulated/`. The code diff is `docs/research/patches/cadence_trial.patch` and the tests are in `docs/research/patches/cadence_trial_tests.txt`.

| Row | Result | Verdict |
|---|---|---|
| C1 | `check_heldout.py` style comparison shows 480 differing fields; jam_soft denial share moved as expected, but 7 spoofing runs have a first alarm 0.2 s later and one `spoof_drift_ref_outage` run changed its label from drift to jump | MISS |
| C2 | design subset: 9 of 30 flights with an alarm with changes 1 and 2, and 9 of 30 with changes 1 to 3 (was 10); predicted at most 7 | MISS |
| C3 | scoring set: 62 of 101 flights 100% TRUSTED (61.4%, 95% interval 51.2% to 70.9%); predicted at least 68 | MISS |
| C4 | scoring set: 38 of 101 flights with a DENIED sample (37.6%, interval 28.2% to 47.8%); predicted at most 32 | MISS |
| C5 | plain gate alarms on 25 of 101 flights, Marsad on 39 (47 with v1.4.0); the gate still alarms on fewer | HIT |
| C6 | not run: the REAL LOG + INJECTED study was run with the v1.4.0 engine only, because the trial was not adopted (see below) | NOT SCORED |

Other measured changes. Alarm episodes per flight hour rose from 3.03 to 4.17, which is worse: the denial was split into more, shorter episodes. The paired comparison with the plain gate did not change in direction (McNemar exact p 0.009 with 20 flights where only Marsad alarms and 6 where only the gate alarms, against 25 and 3 before).

Kill criteria. The amended criterion required that no attack scenario lose detection. Seven held out spoofing runs have a first alarm one tick (0.2 s) later, their alarm fraction fell by about 0.05 percentage points, and one label changed. These are small, but they are in the direction the criterion forbids, so I read it as triggered. Where the wording is ambiguous the weaker claim is taken.

Decision. The engine change is not adopted. The release engine keeps v1.4.0 behaviour, the working tree changes were removed in the same step, and the diff is kept as a record. The study is reported as a partial negative: the mechanism diagnosis was right for 8 flights (54 to 62 flights fully trusted) but it did not reach the predicted size, did not improve the design subset beyond one flight, and the largest group of alarms (fix loss under 3 s on 1 Hz receivers, 26 flights) is still present in the corpus numbers of the release. This matters for the headline: the real flight false alarm rate reported in the README is the v1.4.0 value.

Not independent: the causes were diagnosed on the scoring flights as well as on the design subset, so C3 and C4 were partly in sample and would be expected to look better than a fresh set. They still missed.

## Amendment 1, 2026-11-03: a third change, found on the design subset

Before any scoring flight was run with the new engine, the design subset was replayed with changes 1 and 2
(`docs/results/cadence_trial_design_c12/`). Flights with an alarm fell from 10 to 9 of 30, so prediction C2 (at most 7)
was missed on the design data. Reading the four flights that stayed alarmed (`HNBQ_KAKUTEH7`, `AUAV_H9`, `HEX_MBV2`,
`ED_ASBNN`; all in the design subset) showed a mechanism I had attributed to the reacquisition cap but that is simpler:
the engine says P(nominal) is 0.96 and still stays DENIED or DEGRADED for the whole flight.

Cause: the dwell timer that lets the state recover (`_down_since`) is cleared on every tick that carries no GNSS fix,
because a tick without a fix cannot "verify re-acquisition". In a PX4 log the reference arrives between fixes, so about
nine ticks in ten carry no fix at 1 Hz and the timer is cleared before it can run. The simulator and the SIH logs used
in earlier packages put a fix in nearly every sample, so the defect never showed there.

Change 3: a tick without a fix carries no new information for the recovery decision. It neither starts nor clears the
dwell timer, and the decision is taken only on ticks with a fix. A failed verification on a fix still clears the timer.

Consequences stated in advance:

* This changes behaviour wherever a simulated or injected run has isolated invalid fixes while the state is recovering
  (the jamming and obstruction scenarios). Time to recover after such a scenario may become shorter. The SIMULATED
  tables are therefore regenerated in the commit that makes the change, and `check_heldout.py` is expected to show
  differences. The kill criterion on `check_heldout.py` is replaced for this change by: no attack scenario may lose
  detection (latency of first alarm and fraction of attack time alarmed for the spoofing scenarios must not fall), and no
  nominal or benign scenario may gain an alarm.
* SIH + INJECTED results of `sitl1.ulg` and `sitl2.ulg` cannot be regenerated here (the logs are not in this
  environment); their tables stay labelled as produced by the v1.4.0 engine.
* Prediction C2 is not amended; its miss on the design subset stays on the record and C3 and C4 are scored as
  written, on the scoring set, with all three changes.
