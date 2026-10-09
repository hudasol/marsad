### heldout split, 30 seeds per scenario (SIMULATED)



**Attack and interference scenarios** (SIMULATED)

| scenario | n | detected (Marsad) | detected (gate baseline) | latency med / p90 (s), Marsad | latency med (s), baseline | max nav error med (m): Marsad / baseline / raw GNSS | class acc. at first alarm / settled (fine) | no-fallback time |
|---|---|---|---|---|---|---|---|---|
| `jam_hard` | 30 | 100% | 100% | 2.4 / 4.5 | 5.0 | 6 / 7 / 4 | 93% (coarse) / 100% | 0% |
| `jam_soft` | 30 | 100% | 100% | 5.0 / 6.1 | 4.1 | 11 / 11 / 22 | 83% (coarse) / 83% | 0% |
| `spoof_jump` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 8 / 430 / 430 | 100% (coarse) / 100% | 0% |
| `spoof_jump_transient` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 6 / 269 / 266 | 100% (coarse) / 100% | 0% |
| `spoof_drift` | 30 | 100% | 0% | 27.2 / 89.5 | – | 18 / 411 / 413 | 100% (coarse) / 90% | 0% |
| `spoof_drift_stealth` | 30 | 100% | 0% | 58.3 / 88.9 | – | 20 / 144 / 145 | 100% (coarse) / 100% | 0% |
| `replay` | 30 | 100% | 100% | 0.1 / 0.2 | 0.1 | 10 / 712 / 709 | 100% (coarse) / 97% | 0% |
| `spoof_drift_noref` | 30 | 53% | 0% | 33.1 / 58.7 | – | 99 / 243 / 245 | 100% (coarse) / 47% | 45% |
| `spoof_drift_ref_outage` | 30 | 100% | 0% | 41.1 / 138.3 | – | 37 / 121 / 121 | 100% (coarse) / 87% | 40% |

**Benign conditions** (false-alarm behaviour, SIMULATED)

| scenario | n | time not-TRUSTED, Marsad | runs reaching DENIED, Marsad | time DENIED, baseline | runs reaching DENIED, baseline |
|---|---|---|---|---|---|
| `nominal` | 30 | 0% | 0% | 0% | 0% |
| `benign_obstruction` | 30 | 85% | 0% | 87% | 100% |
| `benign_multipath` | 30 | 2% | 3% | 35% | 77% |
