# Evaluation

**Everything on this page is SIMULATED.** The scenarios come from `marsad.sim`, a measurement-level
model of what a GNSS receiver and a reference sensor would report. No flight data, no RF, no hardware.
Read the results as "the method works against this threat model", not "Marsad is validated in the field".

Reproduce: `python scripts/run_eval.py` (about 4 minutes on 4 cores). Raw results: `docs/results/*.json`.

## Method

* **Scenarios (12).** `nominal`; benign: `benign_obstruction`, `benign_multipath`; jamming: `jam_hard`, `jam_soft`;
  spoofing: `spoof_jump`, `spoof_jump_transient`, `spoof_drift` (carry-off with a power signature),
  `spoof_drift_stealth` (no power signature, velocity-consistent), `replay` (meaconing); and two failure-regime
  cases, `spoof_drift_noref` (no reference sensor) and `spoof_drift_ref_outage` (reference lost for 30–60 s).
  600 s, 5 Hz, a manoeuvring UAV at 8–16 m/s, correlated GNSS error (1.2 m, 30 s correlation), a reference
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

## Results, held-out split (30 seeds per scenario)

| scenario | detected: Marsad | detected: gate baseline | latency med / p90 (s): Marsad | max nav error med (m): Marsad / baseline / raw GNSS | coarse class acc. |
|---|---|---|---|---|---|
| jam_hard | 100% | 100% | 2.4 / 4.5 | 8 / 7 / 4 | 80% |
| jam_soft | 100% | 100% | 5.7 / 8.5 | 13 / 10 / 22 | 83% |
| spoof_jump | 100% | 100% | 0.1 / 0.2 | **17 / 403 / 406** | 100% |
| spoof_jump_transient | 100% | 100% | 0.1 / 0.2 | **7 / 80 / 81** | 100% |
| spoof_drift | 97% | **0%** | 30 / 119 | **22 / 103 / 103** | 100% |
| spoof_drift_stealth | 100% | **0%** | 53 / 100 | **21 / 158 / 157** | 100% |
| replay | 100% | 100% | 0.1 / 0.2 | **17 / 1072 / 1070** | 100% |
| spoof_drift_noref *(failure regime)* | **53%** | 0% | 32 / 47 | 99 / 428 / 427 (43% of time no fallback) | 100% |
| spoof_drift_ref_outage *(failure regime)* | 100% | 0% | 54 / 150 | 33 / 122 / 122 (50% no fallback) | 100% |

| benign scenario | time not-TRUSTED: Marsad | runs reaching DENIED: Marsad | runs reaching DENIED: baseline |
|---|---|---|---|
| nominal | 0% | 0% | 0% |
| benign_obstruction | 82% (DEGRADED, never DENIED) | **0%** | 100% |
| benign_multipath | 0% | **0%** | 73% |

Dev split numbers are in `docs/results/dev.md`; they differ mainly in slower-drift latency (dev median 31 s vs 30 s,
p90 35 s vs 119 s).

### What the numbers do and do not say

* **The baseline catches every abrupt event and none of the gradual ones.** Its innovation gate is designed for
  noise and faults, and a slow carry-off stays under it by construction.
* **Even when the baseline detects a jump it ends up wrong.** After the latch expires it accepts the spoofed
  position again (403 m median error). Marsad keeps the offset latched until the GNSS agrees with the
  dead-reckoned continuation of the last trusted track.
* **Marsad is not better at everything.** In `jam_soft` the baseline's navigation error is smaller (10 m vs 13 m)
  and its latency is lower (4.5 s vs 5.7 s). Marsad's rewind-to-onset anchor is deliberately conservative.
* **Class accuracy:** jamming vs spoofing vs environmental is separated well when AGC is available. A `replay`
  is always labelled `spoofing_jump` (never `replay_meaconing`), because after the takeover instant a
  replay and a jump look the same to these detectors. The coarse "spoofing" label is correct; the fine label is not.
* **Obstruction is DEGRADED for most of its duration by design.** The product claim is "does not deny good
  navigation", not "stays silent".

## Ablation (held-out, 20 seeds)

`docs/results/ablation.md`. Removing a detector:

| removed | consequence |
|---|---|
| inertial/reference | stealth carry-off detection drops from 100% to **0%**; carry-off with a power signature from 100% to 45% |
| signal | jamming latency about doubles; carry-off latency 39 s → 103 s; obstruction can reach DENIED (5% of runs) |
| kinematic | jump/replay latency 0.1 s → 1.5 s (still caught by the others) |
| timing | no measurable change on these scenarios (the simulator rarely exercises clock steps) |

The reference sensor is the single biggest factor for carry-off, which is why the adapters warn loudly when only
an EKF-fused (GNSS-contaminated) velocity is available.

## Detectability floor for carry-off

![detectability](img/detectability.png)

`docs/results/detectability.md` sweeps carry-off rate × reference bias. Without a power signature, drifts of
0.1 m/s are **not detected at all** (even with a perfect reference), 0.15 m/s only in 0–38% of runs, and 0.2 m/s in
81–100% of runs but only after more than two minutes; 0.3 m/s and faster is detected in every run. The floor comes from the reference
bias bound and the sensor noise integrated over the window, not from the code path.

## Case studies

![carry-off](img/case-carry-off.png)
![jamming](img/case-jamming.png)
![jump](img/case-jump.png)

## Performance

45.7 µs per sample (3000 samples in 0.137 s, CPython 3.13, one cloud core, includes simulation-free engine
only). Memory is bounded: the longest drift window is 120 s, history is pruned at 1.6× that. The core is
standard-library only. A compiled port is not needed for 5–50 Hz companion-computer use; it would be for
microcontrollers.

## Threats to validity

1. **Same author for simulator and detectors.** Held-out splits mitigate over-fitting to parameters but not to
   the model. Real receivers have failure modes the simulator does not have.
2. **Idealised reference sensor.** Bias is bounded and white noise is Gaussian. A real visual-odometry system
   drops out, scale-drifts, and fails in featureless terrain or over water.
3. **Simple GNSS error model.** No ionospheric events, no multi-constellation geometry, no receiver-specific
   C/N0 behaviour, no real AGC scale.
4. **Baseline is a stand-in.** Do not read the table as "Marsad beats PX4".
5. **Spoofer model is measurement-level.** A spoofer that also manipulates C/N0 statistics to match baselines,
   or that manipulates the reference sensor, is outside the model (see below).

## Not handled (by design or by limit)

* Attack at power-up (no clean baseline to learn).
* A coordinated attack that also corrupts the reference sensor (the reference must be independent).
* Slow drift below the reference bias bound.
* After a long outage with no reference, re-acquisition is unverifiable; the state stays DEGRADED until an
  operator acknowledges (`engine.acknowledge()`).
* Multipath excursions that do not revert within 4 s are indistinguishable from a small jump at onset.
