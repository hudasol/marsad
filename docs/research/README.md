# Research record

Engine changes in this project follow one rule: the predictions are committed before the experiment is run, and the
outcome is recorded next to them whether or not they hold.

| file | subject | outcome |
|---|---|---|
| [PREREGISTRATION_SIH.md](PREREGISTRATION_SIH.md) | attacks injected into PX4 SIH logs | scored in [VALIDATION](../VALIDATION.md) |
| [PREREGISTRATION_WEIGHTING.md](PREREGISTRATION_WEIGHTING.md) | evidence weighting at mixed sample rates | adopted in v1.3.0 |
| [PREREGISTRATION_BIAS.md](PREREGISTRATION_BIAS.md) | guard on the reference bias estimator | rejected and reverted |
| [PREREGISTRATION_PRIOR_BOUND.md](PREREGISTRATION_PRIOR_BOUND.md) | prior bound channel in the drift detector | see the outcome section |
| [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md) | findings of an independent review of the repository | open items listed |
| [RUN_LOG.md](RUN_LOG.md) | timestamped log of the v1.3.0 run | historical |

Paths inside the older documents refer to the repository layout at the time they were written (before the files were
moved into this folder).
