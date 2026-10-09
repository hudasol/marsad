### Ablation: detection rate / median latency (s) per scenario, held-out (SIMULATED)

| scenario | full | -signal | -kinematic | -inertial | -timing |
|---|---|---|---|---|---|
| `nominal` | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs |
| `benign_obstruction` | FA 75% time, deny 0% runs | FA 1% time, deny 5% runs | FA 75% time, deny 0% runs | FA 69% time, deny 0% runs | FA 75% time, deny 0% runs |
| `benign_multipath` | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs | FA 0% time, deny 0% runs |
| `jam_hard` | 100% / 2.4 | 100% / 4.5 | 100% / 2.4 | 100% / 2.4 | 100% / 2.4 |
| `jam_soft` | 100% / 5.4 | 100% / 10.2 | 100% / 5.4 | 100% / 5.4 | 100% / 5.4 |
| `spoof_jump` | 100% / 0.1 | 100% / 0.1 | 100% / 1.5 | 100% / 0.1 | 100% / 0.1 |
| `spoof_drift` | 100% / 38.9 | 100% / 103.0 | 100% / 38.9 | 45% / 36.0 | 100% / 38.9 |
| `spoof_drift_stealth` | 100% / 56.1 | 100% / 56.1 | 100% / 56.1 | 0% / – | 100% / 56.1 |
| `replay` | 100% / 0.1 | 100% / 0.1 | 100% / 1.6 | 100% / 0.1 | 100% / 0.1 |
