# Preregistration: a real flight corpus for false alarms and agreement with the flight controller

Written on 2026-11-03 (UTC+4). Only five pilot logs were downloaded before this file was committed, to check that the
parser reads them; their identifiers are listed in `docs/results/real_corpus/manifest.csv`. No engine output on the
corpus had been looked at when the predictions below were fixed. Label for every number here: **REAL LOG**.

## Question

How often does the v1.4.0 engine leave TRUSTED on public PX4 flights that contain no deliberate attack, across PX4
versions and hardware, and how do its non TRUSTED episodes compare with the accept and reject decisions of PX4's own
EKF2 on the same flights?

## Data and selection (fixed before downloading)

* Source: PX4 Flight Review public logs (CC BY), metadata from `https://review.px4.io/dbinfo`
  (485,588 entries on 2026-11-03), files from `https://cdn.logs.px4.io/<log_id>.ulg`. Log files are never committed.
* Filters on the metadata: estimator EKF2; duration between 240 s and 3,600 s; vehicle type multirotor (quadrotor,
  hexarotor, octorotor) or fixed wing or VTOL; hardware name without `SITL`; PX4 release from v1.13.0 to v1.18.x
  (the GNSS topic is `sensor_gps` from v1.13).
* Draw: seeded random order (seed 20261103) by round robin over (release minor version, hardware). At most 3 logs per
  vehicle identifier, at most 12 per hardware name, at most 40 per release minor version. The adapter must find
  at least 120 s of fixes of type 3 or better; a log that fails this is dropped and the next one in the order is used.
  A log whose size is above 200 MB is skipped. Target: 130 accepted logs, stopping earlier if 6 GB have been
  downloaded (below the 15 GB allowed, to keep room for the PX4 build).
* A second stratum of up to 15 logs whose metadata carries a non empty `error_labels` field, drawn the same way. Its
  results are reported separately and descriptively, because the meaning of the label codes is not documented in the
  metadata.
* Design subset: logs whose SHA256 of the log identifier, read as a number, is divisible by 5 (about 20%) are the
  design subset used only to develop engine changes in the later packages. They are excluded from every scored number
  below. The scoring set is the remaining logs.
* The manifest records log identifier, URL, SHA256, release, hardware, vehicle type, GNSS seconds and which
  independent motion references the log contains (optical flow, visual odometry, wheel odometry, none). It records no
  coordinates.

## Method

* Marsad v1.4.0 (the engine of this repository before any behaviour change) is replayed with `marsad.adapters.ulog`
  and the preset `uav_multirotor` for multirotors, `uav_fixedwing` for fixed wing and VTOL. The reference velocity is
  whatever the adapter selects; it is the EKF fused velocity unless the log carries an independent source, so the
  carry off check is close to blind on most logs. This is stated wherever the result is used.
* The adapter reports the receiver flags `jamming_state` and `spoofing_state` beside the engine output but does not
  feed them into the engine (`adapters/replay.py` only compares them). Agreement with the flags is therefore
  independent of the engine.
* A flight "has an alarm" if any sample is not TRUSTED, and "has a denial" if any sample is DENIED. An alarm episode
  is a maximal run of non TRUSTED samples; episodes closer than 5 s are merged.
* The four baselines of `docs/BASELINES.md` are replayed on the same flights (`scripts/replay_baselines.py` logic).
  Paired comparison with Marsad: McNemar exact test on "has an alarm".
* EKF2 episodes: where the log carries `estimator_aid_src_gnss_pos` and `estimator_aid_src_gnss_vel`, a rejection is a
  sample with `fused` false or `innovation_rejected` true; where it carries `estimator_status_flags`, a fault is
  `cs_gnss_fault` true or `cs_gnss_pos` false while airborne. Topic and field names are checked per release
  against the PX4 source at the pinned commit and recorded in the output.
* Statistics: the unit is the flight; n is stated for every number. Proportions carry Clopper Pearson 95% intervals;
  if the count is zero the upper bound is also given as the rule of three. Stratified by release minor version and by
  hardware. Primary analyses are those in the prediction table; everything else is labelled exploratory. Number of
  primary comparisons: 7.

## Predictions

| id | prediction (scoring set) |
|---|---|
| R1 | at least 85% of flights are 100% TRUSTED (plausible range 75% to 95%) |
| R2 | at most 6% of flights contain any DENIED sample |
| R3 | fewer than 0.5 alarm episodes per flight hour over the whole set |
| R4 | for flights where the receiver reported `jamming_state` of 2 or more for at least 30 s, Marsad stays 100% TRUSTED in at least 80% of them (as it did on the earlier 911 s log). This can fail: a real interference event may change the signal in a way the engine sees |
| R5 | the window consistency baseline has an alarm on at least twice as many flights as Marsad (it alarms in 23% of nominal simulated runs) |
| R6 | EKF2 shows at least one GNSS rejection of 1 s or longer in at least 25% of flights, and fewer than 15% of those flights also have a Marsad alarm within 10 s of it |
| R7 | the Clopper Pearson 95% upper bound on the share of flights with a denial is below 10% for every release minor version with at least 10 scored flights. This can fail through small strata |

## Risks named in advance

* The corpus is dominated by hobby and development airframes in benign environments; zero alarms there says little
  about contested environments. The README states this.
* Logs from boards without C/N0 or with unusual GNSS cadence may expose adapter assumptions. Each is recorded and
  the log stays in the corpus.
* The EKF fused reference makes slow drift undetectable by construction on most logs; these flights test false alarms,
  not detection.

## Kill criteria

None; this is a measurement. Any non TRUSTED flight is reported in the README headline area with its cause class.

## Outcome

Empty until scored.

## Amendment, 2026-11-03

The first paragraph of this file says five pilot logs had been downloaded when it was committed. That was written
ahead of the fact: the pilot download (the first five accepted candidates in the fixed order, 0.30 GB, listed in the
manifest) happened a few minutes after this file was committed and before any engine output on the corpus was
viewed. No prediction was changed. Five other candidates in the same order were dropped by the GNSS rule (no fixes of
type 3 or better), so about half of the drawn logs fail the rule. With the caps in "Data and selection" the drawn list
holds 240 main candidates, so the expected number of accepted logs is about 120, below the target of 130; the
scoring set will be about 96 flights. The caps are not changed.

## Amendment 2, 2026-11-03: scoring starts at the first fix

The pilot showed that every baseline raised a "no GNSS fix" alarm at the start of each log, before the first fix of
type 3 or better (the first 0.6 to 0.9 s, while reference samples arrive first). Counting those samples would
penalise the baselines for a start up artifact. All methods, Marsad included, are therefore scored only from the
first fix of type 3 or better. This definition was fixed after looking at the five pilot logs and before the
remaining logs were downloaded or analysed. One pilot log (a VTOL with a 1 Hz receiver) shows Marsad DENIED for 95%
of its flight after a 1.6 s gap between fixes; it is in the scoring set, it is reported as measured, and it is not
removed.
