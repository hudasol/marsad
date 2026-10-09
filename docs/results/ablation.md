### Ablation: detection rate / median latency (s) per scenario, held-out (SIMULATED)

| scenario | full | -signal | -kinematic | -inertial | -timing |
|---|---|---|---|---|---|
| `nominal` | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs |
| `benign_obstruction` | FA 88% time, deny 0% runs | FA 63% time, deny 0% runs | FA 85% time, deny 0% runs | FA 86% time, deny 0% runs | FA 88% time, deny 0% runs |
| `benign_multipath` | FA 2% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 2% time, deny 5% runs | FA 2% time, deny 0% runs |
| `jam_hard` | 100% / 2.4 | 100% / 4.5 | 100% / 2.4 | 100% / 2.4 | 100% / 2.4 |
| `jam_soft` | 100% / 5.1 | 100% / 7.5 | 100% / 5.3 | 100% / 5.1 | 100% / 5.1 |
| `spoof_jump` | 100% / 0.1 | 100% / 0.1 | 100% / 1.4 | 100% / 0.1 | 100% / 0.1 |
| `spoof_drift` | 100% / 32.5 | 100% / 48.3 | 100% / 32.5 | 45% / 35.8 | 100% / 32.5 |
| `spoof_drift_stealth` | 100% / 54.1 | 100% / 54.1 | 100% / 54.1 | 0% / – | 100% / 54.1 |
| `replay` | 100% / 0.1 | 100% / 0.1 | 100% / 1.6 | 100% / 0.1 | 100% / 0.1 |
| `spoof_drift_noref` | 50% / 34.1 | 10% / 78.9 | 40% / 34.1 | 50% / 34.1 | 50% / 34.1 |
