# Research record

Engine changes in this project follow one rule: the predictions are committed before the experiment is run, and the
outcome is recorded next to them whether or not they hold.

| file | subject | outcome |
|---|---|---|
| [PREREGISTRATION_SIH.md](PREREGISTRATION_SIH.md) | attacks injected into PX4 SIH logs | scored in [VALIDATION](../VALIDATION.md) |
| [PREREGISTRATION_WEIGHTING.md](PREREGISTRATION_WEIGHTING.md) | evidence weighting at mixed sample rates | adopted in v1.3.0 |
| [PREREGISTRATION_BIAS.md](PREREGISTRATION_BIAS.md) | guard on the reference bias estimator | rejected and reverted |
| [PREREGISTRATION_PRIOR_BOUND.md](PREREGISTRATION_PRIOR_BOUND.md) | prior bound channel in the drift detector | see the outcome section |
| [PRIOR_ART.md](PRIOR_ART.md) | prior art survey for the v1.5.0 claims | reference |
| [PREREGISTRATION_BASELINE_LOCK.md](PREREGISTRATION_BASELINE_LOCK.md) | baseline lock before v1.5.0 | scored late, one miss |
| [PREREGISTRATION_REAL_CORPUS.md](PREREGISTRATION_REAL_CORPUS.md) | public flights, no attack | all seven predictions missed |
| [PREREGISTRATION_REAL_INJECTED.md](PREREGISTRATION_REAL_INJECTED.md) | attacks added to real flights | six of nine hit |
| [PREREGISTRATION_SITL_EKF2.md](PREREGISTRATION_SITL_EKF2.md) | PX4 EKF2 in the loop | six of six hit; the finding is a limit |
| [PREREGISTRATION_SIH_REALISTIC_REF.md](PREREGISTRATION_SIH_REALISTIC_REF.md) | degraded reference models | three of five hit |
| [PREREGISTRATION_CADENCE.md](PREREGISTRATION_CADENCE.md) | receiver cadence and start up change | not adopted, four of six missed |
| [PREREGISTRATION_LITERATURE.md](PREREGISTRATION_LITERATURE.md) | independent scenario family and sealed split | dev 7 of 8 hit; sealed 2 of 3 hit |
| [SCENARIOS_LITERATURE.md](SCENARIOS_LITERATURE.md) | the literature scenario family | specification |
| [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md) | findings of an independent review of the repository | open items listed |
| [RUN_LOG.md](RUN_LOG.md) | timestamped log of the v1.3.0 run | historical |

Paths inside the older documents refer to the repository layout at the time they were written (before the files were
moved into this folder).
