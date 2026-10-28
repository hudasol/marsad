# Evaluation

**Everything on this page is SIMULATED.** The scenarios come from `marsad.sim`, a measurement-level
model of what a GNSS receiver and a reference sensor would report. No flight data, no RF, no hardware.
Read the results as "the method works against this threat model", not "Marsad is validated in the field".

Reproduce: at tag v1.1.0, `python scripts/run_eval.py` (about 12 minutes on 4 cores). Raw results: `docs/results/*.json`.
With the current engine use `python scripts/run_eval.py --out docs/results/weighting_fix`; without `--out` the script
writes to `docs/results/` and would overwrite the published v1.1.0 files.

## Method

* **Scenarios (12).** `nominal`; benign: `benign_obstruction`, `benign_multipath`; jamming: `jam_hard`, `jam_soft`;
  spoofing: `spoof_jump`, `spoof_jump_transient`, `spoof_drift` (carry-off with a power signature),
  `spoof_drift_stealth` (no power signature, velocity-consistent), `replay` (meaconing); and two failure-regime
  cases, `spoof_drift_noref` (no reference sensor) and `spoof_drift_ref_outage` (reference lost for 30 to 60 s).
  600 s, 5 Hz, a manoeuvring UAV at 8 to 16 m/s, correlated GNSS error (1.2 m, 30 s correlation), a reference
  velocity sensor with bias up to 0.06 m/s (dev) / 0.08 m/s (held-out).
* **Splits.** Detector thresholds were tuned on the **dev** split only. The **held-out** split uses different
  seeds and *different or more adversarial parameter ranges* (slower and faster carry-off than dev, weaker
  spoofer power, longer replay delays, smaller and larger jumps, larger reference bias). Held-out parameters
  were fixed before the final run, and no threshold was changed after it. Disclosure: one 6-seed smoke run of
  the held-out split was looked at before the final run to check the pipeline; nothing was tuned on it.
* **Baseline.** `marsad.bench.GateBaseline`, a *simplified autopilot-style* gate: fix type, satellite count,
  a 5σ position-innovation gate, a 10 s latch, dead-reckoning on the **same** reference sensor while latched.
  It is a stand-in for common practice, **not PX4's actual implementation**, and it is cheap to beat in places
  by construction. The comparison isolates detection logic, not sensors.
* **Metrics.** Detection = state leaves TRUSTED after onset. Latency = onset to first non-TRUSTED. Navigation
  error = distance between the *recommended* position and truth after onset (what the vehicle would fly on),
  compared with the raw GNSS error and the baseline. False-alarm behaviour on benign scenarios = fraction of time
  not TRUSTED and fraction of runs reaching DENIED. `no-fallback time` = fraction of post-onset time Marsad
  recommended HOLD_AND_ALERT (it has nothing to navigate on).

## Results, held-out split (30 seeds per scenario, fresh seeds)

Version 1.1.0. Seeds were drawn fresh (held-out 5000+, ablation 6000+, sweep 7000+) after the 1.1 changes, because the
v1.0.0 held-out seeds had been seen while those changes were designed. The v1.0.0 results are kept in
`docs/results/v1.0.0/`. Parameters were not re-tuned against these seeds.

| scenario | detected: Marsad | detected: gate baseline | latency med / p90 (s): Marsad | max nav error med (m): Marsad / baseline / raw GNSS | class at first alarm (coarse) / settled (fine) |
|---|---|---|---|---|---|
| jam_hard | 100% | 100% | 2.4 / 4.5 | 6 / 7 / 4 | 93% / 100% |
| jam_soft | 100% | 100% | 5.0 / 6.1 | 11 / 11 / 22 | 83% / 83% |
| spoof_jump | 100% | 100% | 0.1 / 0.2 | **8 / 430 / 430** | 100% / 100% |
| spoof_jump_transient | 100% | 100% | 0.1 / 0.2 | **6 / 269 / 266** | 100% / 100% |
| spoof_drift | 100% | **0%** | 27 / 90 | **18 / 411 / 413** | 100% / 90% |
| spoof_drift_stealth | 100% | **0%** | 58 / 89 | **20 / 144 / 145** | 100% / 100% |
| replay | 100% | 100% | 0.1 / 0.2 | **10 / 712 / 709** | 100% / 97% |
| spoof_drift_noref *(failure regime)* | **53%** | 0% | 33 / 59 | 99 / 243 / 245 (45% of time no fallback) | 100% / 47% |
| spoof_drift_ref_outage *(failure regime)* | 100% | 0% | 41 / 138 | 37 / 121 / 121 (40% no fallback) | 100% / 87% |

| benign scenario | time not-TRUSTED: Marsad | runs reaching DENIED: Marsad | runs reaching DENIED: baseline |
|---|---|---|---|
| nominal | 0% | 0% | 0% |
| benign_obstruction | 85% (DEGRADED) | **0%** | 100% |
| benign_multipath | 2% | **3%** (1 of 30 runs) | 77% |

Changes versus v1.0.0 (same scenarios, different seeds, so small differences are within seed noise): the replay
event is now labelled `replay_meaconing` (with an estimated delay) instead of a position jump; carry-off with a
power signature went from 97% to 100%; soft jamming latency is 5.0 s (was 5.7) and navigation error equals the
baseline's (11 m); the stealth carry-off detection latency did not improve on the median (58 s vs 53 s).
Regressions: one multipath run (3%) now reaches DENIED (was 0 of 30), and engine cost is about four times higher.

Dev split numbers are in `docs/results/dev.md`.

### After the evidence weighting fix (preregistered)

**SIMULATED.** The tables above are v1.1.0 and stay as published. After v1.2.0 the engine was changed so that
evidence computed once per GNSS fix is scaled by the time since the previous usable fix rather than the time since
the previous sample (details in [VALIDATION.md](VALIDATION.md), "Evidence weighting fix"). Predictions for this
evaluation (P7, P8) were committed before the change in [PREREGISTRATION_WEIGHTING.md](research/PREREGISTRATION_WEIGHTING.md).
In the simulator GNSS and reference share one 5 Hz sample, so the change can only matter on the first fix after
samples without a usable fix.

Reproduce: `python scripts/run_eval.py --out docs/results/weighting_fix` (same seeds as v1.1.0; 39 minutes on the
Windows laptop used for this run). Results: `docs/results/weighting_fix/`.

Rows that changed, held out split (every other row of `heldout.md` is unchanged):

| scenario | metric | v1.1.0 | after the fix |
|---|---|---|---|
| jam_soft | latency med / p90 (s) | 5.0 / 6.1 | 4.6 / 5.6 |
| jam_soft | max nav error med (m), Marsad | 11 | 9 |
| jam_soft | class at first alarm / settled | 83% / 83% | 83% / 83% (unchanged) |
| jam_soft | median recovery time (s, JSON only) | 47.5 | 48.1 |
| jam_hard | median recovery time (s, JSON only) | 20.0 | 20.3 |
| benign_obstruction | time not TRUSTED | 84.6% | 84.7% (85% in the table either way) |

Dev split: `jam_soft` latency 5.2 → 4.9 s, navigation error 11 → 10 m, class accuracy 97% → 100%, DENIED in 97% →
100% of runs. Ablation (20 seeds): full engine `jam_soft` latency 5.1 → 4.8 s; no other ablation cell changed in its
table. Detectability sweep: every cell unchanged.

Against the preregistration:

* **P7a hit.** Every scenario in which every sample carries a usable fix is unchanged in `heldout.md`, `dev.md`,
  `detectability.md` and `ablation.md`. Some JSON medians differ from v1.1.0 in the 13th to 15th significant digit.
  A same machine control (`scripts/engine_diff.py`, output in `docs/results/weighting_fix/engine_diff_heldout.txt`)
  ran the v1.2.0 engine and the fixed engine on the held out split on this machine: the nine predicted scenarios are
  bitwise identical, and the v1.2.0 engine run here shows the same last digit differences from the published JSON,
  which was produced on another machine. They are floating point platform effects, not engine changes.
* **P7b hit.** `jam_hard`: detection 100% on both splits, latency unchanged (2.4 s held out, 2.4 s dev).
* **P7c hit.** `jam_soft`: detection 100% on both splits; latency 4.6 s held out and 4.9 s dev, inside the band of
  3.0 s to the v1.1.0 value; settled class accuracy unchanged held out, +3 points dev.
* **P7d hit.** `benign_obstruction`: time not TRUSTED 85% held out and 88% dev, as before; no run reaches DENIED.
* **P7e miss.** `throughput.json` reports 1,263.0 µs per sample against a prediction of 187.7 µs ± 20%. A same
  machine control (`scripts/throughput.py`, output in `docs/results/weighting_fix/throughput_control.txt`) times
  both engines alternately on this laptop: v1.2.0 738.9 to 1,181.8 µs, fixed engine 892.3 to 1,211.5 µs, within the spread
  of repeated runs. The miss reflects the machine, not the change; the prediction should not have assumed the same
  hardware. The published 187.7 µs stays the reference figure for a cloud core, and this control cannot resolve a
  difference between the two engines below about 10%.
* **P8 hit.** All 140 existing tests pass unmodified; the 3 new tests in `tests/test_mixed_rate.py` pass, and the
  interleaved drift test failed on the old code.

With the fix, the soft jamming navigation error (9 m) is now lower than the baseline's (11 m); the baseline's
latency is still lower (4.1 s vs 4.6 s).

### What the numbers do and do not say

* **The baseline catches every abrupt event and none of the gradual ones.** Its innovation gate is designed for
  noise and faults, and a slow carry-off stays under it by construction.
* **Even when the baseline detects a jump it ends up wrong.** After the latch expires it accepts the spoofed
  position again (430 m median error). Marsad keeps the offset latched until the GNSS agrees with the
  dead-reckoned continuation of the last trusted track.
* **Marsad is not better at everything.** In `jam_soft` the baseline's latency is lower (4.1 s vs 5.0 s in v1.1.0,
  4.1 s vs 4.6 s after the v1.3.0 fix); navigation error was equal (11 m) in v1.1.0 and is now 9 m for Marsad. Marsad's rewind-to-onset anchor is deliberately conservative.
* **Class accuracy:** jamming vs spoofing vs environmental is separated well when AGC is available. A `replay`
  is now labelled `replay_meaconing` in 97% of runs once a delay (lag) is confirmed by cross-correlating GNSS
  and reference velocity; at the very first alarm the label is still the coarse one. Without a reference sensor a
  carry-off is reported as `spoofing_unclassified` (the fine label is right in 47% of those runs). Jump vs. drift
  labelling is imperfect in ~10% of power-signature carry-off runs.
* **Obstruction is DEGRADED for most of its duration by design.** The product claim is "does not deny good
  navigation", not "stays silent".

## Ablation (held-out, fresh seeds)

Ablation runs use 20 seeds (6000+), so the full engine figures differ slightly from the main table.

`docs/results/ablation.md`. Removing a detector:

| removed | consequence |
|---|---|
| inertial/reference | stealth carry-off detection drops from 100% to **0%**; carry-off with a power signature from 100% to 45%; multipath reaches DENIED in 5% of runs (0% with all detectors) |
| signal | hard jamming latency 2.4 s → 4.5 s, soft 5.1 s → 7.5 s; carry-off with a power signature 32.5 s → 48.3 s; carry-off without a reference detected in 10% of runs instead of 50%; obstruction time not TRUSTED falls from 88% to 63% (no run reaches DENIED either way) |
| kinematic | jump latency 0.1 s → 1.4 s, replay 0.1 s → 1.6 s (still caught by the others) |
| timing | no measurable change on these scenarios (the simulator rarely exercises clock steps) |

The reference sensor is the single biggest factor for carry-off, which is why the adapters warn loudly when only
an EKF-fused (GNSS-contaminated) velocity is available.

## Detectability floor for carry-off

![detectability](img/detectability.png)

`docs/results/detectability.md` sweeps carry-off rate × reference bias. Without a power signature, drifts of
0.05 m/s are **never** detected, 0.1 m/s in about 50 to 56% of runs (after about 4 to 5 minutes), and 0.15 m/s and faster in
100% of runs (0.15 m/s after about 2.3 minutes). In v1.0.0 the 0.15 m/s cell was 0 to 38%; the improvement comes from the
slow reference-bias estimator and the 240 s window. The sweep is on fresh seeds and the bias values are bounds of
the simulated reference sensor. The floor comes from the reference
bias bound and the sensor noise integrated over the window, not from the code path.

## Case studies

![carry-off](img/case-carry-off.png)
![jamming](img/case-jamming.png)
![jump](img/case-jump.png)

## Performance

v1.1.0 engine: 187.7 µs per sample (3000 samples in 0.56 s, `docs/results/throughput.json`, CPython 3.13, one cloud core, engine only; v1.0.0 was 45.7 µs,
the increase is the replay cross-correlation and the longer drift windows). Memory is bounded: the longest drift window is 240 s, history is pruned at 1.6× that. This is still
well inside the budget for 5 to 50 Hz. The core is
standard-library only. A compiled port is not needed for 5 to 50 Hz companion-computer use; it would be for
microcontrollers.

## Threats to validity

1. **Same author for simulator and detectors.** Held-out splits mitigate over-fitting to parameters but not to
   the model. Real receivers have failure modes the simulator does not have.
2. **Idealised reference sensor.** Bias is bounded and white noise is Gaussian. A real visual-odometry system
   drops out, scale-drifts, and fails in featureless terrain or over water.
3. **Simple GNSS error model.** No ionospheric events, no multi-constellation geometry, no receiver-specific
   C/N0 behaviour, no real AGC scale.
4. **Baseline is a stand-in.** Do not read the table as "Marsad beats PX4".
5. **Held-out seeds are not independent of the design.** The 1.1 changes were developed while looking at v1.0.0
   results; the numbers above are on fresh seeds but the same scenario family.
6. **Spoofer model is measurement-level.** A spoofer that also manipulates C/N0 statistics to match baselines,
   or that manipulates the reference sensor, is outside the model (see below).

## Not handled (by design or by limit)

* Attack at power-up (no clean baseline to learn).
* A coordinated attack that also corrupts the reference sensor (the reference must be independent).
* Slow drift below roughly 0.1 m/s (undetected or only after minutes): the reference sensor's residual bias and noise,
  integrated over the window, bound what can be seen.
* After a long outage with no reference, re-acquisition is unverifiable; the state stays DEGRADED until an
  operator acknowledges (`engine.acknowledge()`).
* Multipath excursions that do not revert within 4 s are indistinguishable from a small jump at onset.
