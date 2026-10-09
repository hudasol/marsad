### heldout split, 30 seeds per scenario (SIMULATED)



**Attack and interference scenarios** (SIMULATED)

| scenario | n | detected (Marsad) | detected (gate baseline) | latency med / p90 (s), Marsad | latency med (s), baseline | max nav error med (m): Marsad / baseline / raw GNSS | class acc. (coarse) | no-fallback time |
|---|---|---|---|---|---|---|---|---|
| `jam_hard` | 30 | 100% | 100% | 2.4 / 4.5 | 5.0 | 8 / 7 / 4 | 80% | 0% |
| `jam_soft` | 30 | 100% | 100% | 5.7 / 8.5 | 4.5 | 13 / 10 / 22 | 83% | 0% |
| `spoof_jump` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 17 / 403 / 406 | 100% | 0% |
| `spoof_jump_transient` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 7 / 80 / 81 | 100% | 0% |
| `spoof_drift` | 30 | 97% | 0% | 30.4 / 119.3 | – | 22 / 103 / 103 | 100% | 0% |
| `spoof_drift_stealth` | 30 | 100% | 0% | 53.0 / 100.1 | – | 21 / 158 / 157 | 100% | 0% |
| `replay` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 17 / 1072 / 1070 | 100% | 0% |
| `spoof_drift_noref` | 30 | 53% | 0% | 31.8 / 46.8 | – | 99 / 428 / 427 | 100% | 43% |
| `spoof_drift_ref_outage` | 30 | 100% | 0% | 53.9 / 149.8 | – | 33 / 122 / 122 | 100% | 50% |

**Benign conditions** (false-alarm behaviour, SIMULATED)

| scenario | n | time not-TRUSTED, Marsad | runs reaching DENIED, Marsad | time DENIED, baseline | runs reaching DENIED, baseline |
|---|---|---|---|---|---|
| `nominal` | 30 | 0% | 0% | 0% | 0% |
| `benign_obstruction` | 30 | 82% | 0% | 83% | 100% |
| `benign_multipath` | 30 | 0% | 0% | 40% | 73% |
