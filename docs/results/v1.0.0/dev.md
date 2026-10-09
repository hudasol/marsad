### dev split, 30 seeds per scenario (SIMULATED)



**Attack and interference scenarios** (SIMULATED)

| scenario | n | detected (Marsad) | detected (gate baseline) | latency med / p90 (s), Marsad | latency med (s), baseline | max nav error med (m): Marsad / baseline / raw GNSS | class acc. (coarse) | no-fallback time |
|---|---|---|---|---|---|---|---|---|
| `jam_hard` | 30 | 100% | 100% | 2.5 / 4.4 | 2.9 | 7 / 7 / 4 | 100% | 0% |
| `jam_soft` | 30 | 100% | 100% | 5.7 / 6.8 | 4.4 | 12 / 9 / 20 | 100% | 0% |
| `spoof_jump` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 14 / 278 / 278 | 100% | 0% |
| `spoof_jump_transient` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 7 / 222 / 219 | 100% | 0% |
| `spoof_drift` | 30 | 100% | 0% | 30.9 / 35.2 | – | 16 / 284 / 283 | 100% | 0% |
| `spoof_drift_stealth` | 30 | 100% | 0% | 46.7 / 58.2 | – | 20 / 204 / 203 | 100% | 0% |
| `replay` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 14 / 757 / 757 | 100% | 0% |
| `spoof_drift_noref` | 30 | 100% | 0% | 25.7 / 35.2 | – | 12 / 264 / 265 | 100% | 93% |
| `spoof_drift_ref_outage` | 30 | 100% | 0% | 24.8 / 30.1 | – | 11 / 254 / 253 | 100% | 94% |

**Benign conditions** (false-alarm behaviour, SIMULATED)

| scenario | n | time not-TRUSTED, Marsad | runs reaching DENIED, Marsad | time DENIED, baseline | runs reaching DENIED, baseline |
|---|---|---|---|---|---|
| `nominal` | 30 | 0% | 0% | 0% | 0% |
| `benign_obstruction` | 30 | 77% | 0% | 88% | 100% |
| `benign_multipath` | 30 | 0% | 0% | 40% | 83% |
