### dev split, 30 seeds per scenario (SIMULATED)



**Attack and interference scenarios** (SIMULATED)

| scenario | n | detected (Marsad) | detected (gate baseline) | latency med / p90 (s), Marsad | latency med (s), baseline | max nav error med (m): Marsad / baseline / raw GNSS | class acc. at first alarm / settled (fine) | no-fallback time |
|---|---|---|---|---|---|---|---|---|
| `jam_hard` | 30 | 100% | 100% | 2.4 / 3.0 | 2.9 | 7 / 7 / 4 | 100% (coarse) / 100% | 0% |
| `jam_soft` | 30 | 100% | 100% | 5.2 / 5.9 | 4.4 | 11 / 9 / 20 | 97% (coarse) / 97% | 0% |
| `spoof_jump` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 7 / 278 / 278 | 100% (coarse) / 100% | 0% |
| `spoof_jump_transient` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 7 / 222 / 219 | 100% (coarse) / 100% | 0% |
| `spoof_drift` | 30 | 100% | 0% | 30.4 / 33.7 | – | 14 / 284 / 283 | 100% (coarse) / 97% | 0% |
| `spoof_drift_stealth` | 30 | 100% | 0% | 44.3 / 53.8 | – | 20 / 204 / 203 | 100% (coarse) / 100% | 0% |
| `replay` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 8 / 757 / 757 | 100% (coarse) / 100% | 0% |
| `spoof_drift_noref` | 30 | 100% | 0% | 25.7 / 35.2 | – | 12 / 264 / 265 | 100% (coarse) / 0% | 93% |
| `spoof_drift_ref_outage` | 30 | 100% | 0% | 24.7 / 30.1 | – | 11 / 254 / 253 | 100% (coarse) / 77% | 94% |

**Benign conditions** (false-alarm behaviour, SIMULATED)

| scenario | n | time not-TRUSTED, Marsad | runs reaching DENIED, Marsad | time DENIED, baseline | runs reaching DENIED, baseline |
|---|---|---|---|---|---|
| `nominal` | 30 | 0% | 0% | 0% | 0% |
| `benign_obstruction` | 30 | 88% | 0% | 88% | 100% |
| `benign_multipath` | 30 | 1% | 0% | 40% | 83% |
