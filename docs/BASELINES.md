# Baselines

Marsad is compared against five reference detectors so that every result can be read against something a
flight stack already does, rather than against nothing. This page states what each baseline is, what it
reproduces and what it does not, how its parameters were fixed, and what the comparison shows. Numbers
come from `scripts/run_baselines.py` and `scripts/sih_baselines.py`; the raw output is in
`docs/results/baselines/`.

All SIMULATED results use the held out split, seeds 5000 to 5029. SIH + INJECTED results use the PX4
software in the loop logs `sitl1.ulg` and `sitl2.ulg` with attacks added to the GNSS record afterwards.
Nothing here is a REAL LOG result.

## What each baseline is

| key | name | what it does |
|---|---|---|
| `gate` | simplified gate | The original single threshold innovation test that shipped with Marsad 1.0. Kept so earlier tables stay comparable. |
| `ekf2_gate` | EKF2 style gate | Position and velocity innovation gating with the documented PX4 EKF2 defaults, a reset timeout and a no aiding timeout. Propagates with the receiver velocity. |
| `ekf2_gate_ref` | EKF2 style gate with reference | The same gate, propagated with the independent velocity reference. This is the strongest fair version of an innovation gate. |
| `window` | window consistency | Compares GNSS displacement over a sliding 60 s window with the integral of the independent reference velocity. Flags when the difference exceeds a noise scaled threshold. |
| `signal` | signal monitor | Watches AGC and C/N0 steps against a running mean. Detects jamming style changes in the radio front end. |
| `stack` | stack of the three | Alarms when any of `ekf2_gate_ref`, `window` or `signal` alarms. This is the nearest thing to what a careful integrator would assemble from parts. |

Defaults are in `src/marsad/bench/baselines.py`:

- `ekf2_gate`: position noise 1.9 m, velocity noise 0.3 m/s, gates of 5 sigma, minimum 6 satellites,
  reset timeout 7 s, no aiding timeout 5 s.
- `window`: 60 s window, position noise 1.3 m, z threshold 4.3, bias bound 0.08 m/s.
- `signal`: AGC step 0.077, C/N0 step 3.5 dB, 120 s running mean, 10 s hold.

## What they do not reproduce

These are reimplementations that work on measurement level samples. They are not PX4 code in the loop.

- `ekf2_gate` follows the structure and defaults of the EKF2 GNSS checks, but it is not the EKF2 filter.
  It has no IMU bias states, no magnetometer, no barometer and no fusion of other sources. A real
  EKF2 replay with injected GNSS is listed in `docs/ROADMAP.md`.
- `window` is not a published product. It is the simplest consistency test that uses the same reference
  Marsad uses, and it is included because it is a strong competitor on drift.
- `signal` sees only the fields the log or simulator provides. A receiver with richer spectrum data would
  do better.

## How parameters were fixed

Free parameters were checked on the NOMINAL scenario of the dev split only, with `scripts/calibrate_baselines.py`.
No attack scenario and no held out seed was used. Result on 30 nominal dev seeds, time not TRUSTED:

| baseline | mean | worst run |
|---|---|---|
| `gate`, `ekf2_gate`, `ekf2_gate_ref`, `signal` | 0.00% | 0.00% |
| `window` | 0.09% | 2.63% |

The AGC step 99.9th percentile on nominal is 0.043 against a threshold of 0.077, and the C/N0 step is
1.93 dB against 3.5 dB. The window baseline keeps a small false alarm rate at its default; it was not
tuned further because tuning it on nominal data alone would only trade away detection.

## Held out SIMULATED results

Share of runs detected, then median latency in seconds from onset.

| scenario | Marsad | simplified gate | EKF2 style gate | EKF2 style + reference | window | signal | stack |
|---|---|---|---|---|---|---|---|
| `jam_hard` | 100% / 2.4 | 100% / 5.0 | 100% / 8.0 | 100% / 8.0 | 100% / 8.0 | 100% / 0.7 | 100% / 0.7 |
| `jam_soft` | 100% / 4.6 | 100% / 4.1 | 100% / 6.0 | 100% / 6.2 | 100% / 5.8 | 100% / 1.6 | 100% / 1.6 |
| `spoof_jump` | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 87% / 5.5 | 100% / 0.1 |
| `replay` | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 27% / 0.5 | 100% / 0.1 |
| `spoof_drift` | 100% / 27.1 | 0% | 30% / 28.9 | 53% / 24.2 | 100% / 22.6 | 0% | 100% / 22.6 |
| `spoof_drift_stealth` | 100% / 58.0 | 0% | 0% | 0% | 100% / 43.0 | 0% | 100% / 43.0 |
| `spoof_drift_noref` | 53% / 33.1 | 0% | 27% / 22.8 | 27% / 22.8 | 87% / 31.1 | 0% | 87% / 31.1 |
| `spoof_drift_ref_outage` | 100% / 41.1 | 0% | 20% / 27.2 | 43% / 53.5 | 100% / 53.7 | 0% | 100% / 53.7 |

Largest navigation error after onset, median over runs, in metres. This is the position each detector
would hand to the vehicle; Marsad hands over its recommended position.

| scenario | Marsad | EKF2 style + reference | window | signal | stack |
|---|---|---|---|---|---|
| `spoof_jump` | 8 | 430 | 430 | 430 | 430 |
| `spoof_drift` | 18 | 404 | 33 | 411 | 371 |
| `spoof_drift_stealth` | 19 | 140 | 28 | 144 | 28 |
| `replay` | 10 | 711 | 164 | 712 | 710 |
| `spoof_drift_noref` | 99 | 243 | 86 | 243 | 243 |
| `spoof_drift_ref_outage` | 31 | 118 | 65 | 118 | 103 |

Alarms in benign conditions, share of runs with any alarm and mean share of time not TRUSTED.

| scenario | Marsad | EKF2 style + reference | window | signal | stack |
|---|---|---|---|---|---|
| `nominal` | 0% / 0% | 0% / 0% | 23% / 0% | 0% / 0% | 23% / 0% |
| `benign_obstruction` | 100% / 85% | 60% / 23% | 73% / 23% | 100% / 95% | 100% / 95% |
| `benign_multipath` | 3% / 2% | 33% / 0% | 60% / 1% | 100% / 98% | 100% / 98% |

## SIH + INJECTED results

Attacks are added to the recorded GNSS of a clean PX4 SIH flight. The reference is the simulator truth
velocity, which has zero bias. Four attack headings per row.

`sitl2.ulg`, 290 s, attack from 60 s:

| attack | Marsad | EKF2 style + reference | window | signal |
|---|---|---|---|---|
| drift 0.1 m/s | 0/4 | 0/4 | 0/4 | 0/4 |
| drift 0.25 m/s | 4/4 at 113.6 s | 0/4 | 4/4 at 57.1 s | 0/4 |
| drift 0.5 m/s | 4/4 at 42.5 s | 0/4 | 4/4 at 31.1 s | 0/4 |
| drift 1.0 m/s | 4/4 at 25.5 s | 0/4 | 4/4 at 18.1 s | 0/4 |
| jump 50 to 1000 m | 4/4 at 0.0 s | 4/4 at 0.0 s | 4/4 at 0.0 s | 0/4 |

Clean replay of the unmodified log: no baseline and not Marsad leaves TRUSTED.

## What the comparison shows

1. **Innovation gates miss slow drift.** A gate propagated with the receiver velocity cannot see a drift
   that is velocity consistent. Giving it the independent reference helps (53% against 30% on
   `spoof_drift`), and still leaves most runs undetected.
2. **A plain window test is faster at drift detection than Marsad.** It reaches `spoof_drift` in 22.6 s
   against 27.1 s and 0.25 m/s SIH drift in 57.1 s against 113.6 s. Marsad is deliberately slower
   because it carries a bias estimate for the reference and refuses to trust a window until the bound
   is established.
3. **The window test false alarms and cannot classify.** It alarms in 23% of nominal runs and 60% of
   multipath runs where Marsad alarms in 0% and 3%. It reports one state, so it cannot tell drift from
   jump from replay, and it gives no recovery position. That is why its navigation error on `replay` is
   164 m against 10 m.
4. **Marsad is the only entry that keeps the navigation error small across every attack class.** On
   `spoof_jump` it hands over 8 m where every baseline hands over 430 m, because it holds the last
   trusted position instead of following the jump.
5. **Without a reference Marsad is weaker than the window test.** `spoof_drift_noref` is 53% against
   87%. This is the largest open gap and the first item in `docs/ROADMAP.md`.
6. **Nothing detects 0.1 m/s.** That rate is below the reference bias bound, and no method here separates
   it from reference error. See `docs/KNOWN_LIMITS.md`.
7. **Signal monitoring is complementary, not competing.** It is fastest on jamming and blind to
   spoofing. It also alarms on obstruction and multipath in every run, so it cannot be used alone to
   deny.

## Caveats on reading these numbers

- The SIH reference is simulator truth with zero bias. This flatters every method that uses it, and the
  window test most of all, because Marsad pays for a bias allowance that the SIH reference does not need.
- The SIMULATED generator is the same one Marsad was developed against, although on a held out split.
- Four headings per SIH row is a small sample. The rows show direction, not a rate.
- No baseline here has been scored on a REAL LOG. In ordinary flight logs the reference velocity is the
  EKF fused velocity, which follows GNSS, so a real replay measures false alarms only. It is run with
  `python scripts/replay_baselines.py flight1.ulg flight2.ulg`.

## Reproduce

```bash
python scripts/calibrate_baselines.py --seeds 30
python scripts/run_baselines.py --workers 4 --marsad docs/results/prior_bound/heldout.json
python scripts/sih_baselines.py sitl2.ulg --end 290 --t-attack 60 \
    --marsad docs/results/prior_bound/sih_inject_long.json --out docs/results/baselines/sih_inject_long.json
python scripts/replay_baselines.py path/to/real_flight.ulg
```
