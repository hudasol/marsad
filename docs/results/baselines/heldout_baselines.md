### Detection against baselines, held out split, 30 seeds per scenario (SIMULATED)

Cell: share of runs detected / median latency in seconds. Detection is the first non TRUSTED sample at or after the onset.

| scenario | Marsad | simplified gate | EKF2 style gate | EKF2 style gate + reference | window consistency | signal monitor | stack of the three |
|---|---|---|---|---|---|---|---|
| `jam_hard` | 100% / 2.4 | 100% / 5.0 | 100% / 8.0 | 100% / 8.0 | 100% / 8.0 | 100% / 0.7 | 100% / 0.7 |
| `jam_soft` | 100% / 4.6 | 100% / 4.1 | 100% / 6.0 | 100% / 6.2 | 100% / 5.8 | 100% / 1.6 | 100% / 1.6 |
| `spoof_jump` | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 87% / 5.5 | 100% / 0.1 |
| `spoof_jump_transient` | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 67% / 4.4 | 100% / 0.1 |
| `spoof_drift` | 100% / 27.2 | 0% / - | 30% / 28.9 | 53% / 24.2 | 100% / 22.6 | 0% / - | 100% / 22.6 |
| `spoof_drift_stealth` | 100% / 58.3 | 0% / - | 0% / - | 0% / - | 100% / 43.0 | 0% / - | 100% / 43.0 |
| `replay` | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 100% / 0.1 | 27% / 0.5 | 100% / 0.1 |
| `spoof_drift_noref` | 53% / 33.1 | 0% / - | 27% / 22.8 | 27% / 22.8 | 87% / 31.1 | 0% / - | 87% / 31.1 |
| `spoof_drift_ref_outage` | 100% / 41.1 | 0% / - | 20% / 27.2 | 43% / 53.5 | 100% / 53.7 | 0% / - | 100% / 53.7 |

### Largest navigation error after onset, median over runs (m)

Position each detector would hand to the vehicle (Marsad: its recommended position; empty while it advises holding).

| scenario | Marsad | simplified gate | EKF2 style gate | EKF2 style gate + reference | window consistency | signal monitor | stack of the three |
|---|---|---|---|---|---|---|---|
| `jam_hard` | 6 | 7 | 619 | 6 | 8 | 8 | 7 |
| `jam_soft` | 9 | 11 | 62 | 5 | 17 | 7 | 14 |
| `spoof_jump` | 8 | 430 | 430 | 430 | 430 | 430 | 430 |
| `spoof_jump_transient` | 6 | 269 | 282 | 268 | 267 | 269 | 267 |
| `spoof_drift` | 18 | 411 | 409 | 404 | 33 | 411 | 371 |
| `spoof_drift_stealth` | 20 | 144 | 143 | 140 | 28 | 144 | 28 |
| `replay` | 10 | 712 | 712 | 711 | 164 | 712 | 710 |
| `spoof_drift_noref` | 99 | 243 | 243 | 243 | 86 | 243 | 243 |
| `spoof_drift_ref_outage` | 37 | 121 | 119 | 118 | 65 | 121 | 103 |

### Alarm behaviour in benign conditions: share of runs with any alarm / mean share of time not TRUSTED

| scenario | Marsad | simplified gate | EKF2 style gate | EKF2 style gate + reference | window consistency | signal monitor | stack of the three |
|---|---|---|---|---|---|---|---|
| `nominal` | 0% / 0% | 0% / 0% | 0% / 0% | 0% / 0% | 23% / 0% | 0% / 0% | 23% / 0% |
| `benign_obstruction` | 100% / 85% | 100% / 87% | 77% / 24% | 60% / 23% | 73% / 23% | 100% / 95% | 100% / 95% |
| `benign_multipath` | 3% / 2% | 77% / 35% | 40% / 1% | 33% / 0% | 60% / 1% | 100% / 98% | 100% / 98% |
