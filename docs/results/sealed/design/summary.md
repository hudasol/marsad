# design family, seeds 7000 to 7099

| kind | method | detected or false alarm | 95% interval | median latency s (95% interval) | pre attack false alarms |
|---|---|---|---|---|---|
| benign_multipath | marsad | 5/100 | 0.0164 to 0.1128 | n/a | n/a |
| benign_multipath | gate | 72/100 | 0.6213 to 0.8052 | n/a | n/a |
| benign_multipath | ekf2_gate_ref | 36/100 | 0.2664 to 0.4621 | n/a | n/a |
| benign_multipath | window | 77/100 | 0.6751 to 0.8483 | n/a | n/a |
| benign_multipath | stack | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| benign_obstruction | marsad | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| benign_obstruction | gate | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| benign_obstruction | ekf2_gate_ref | 53/100 | 0.4276 to 0.6306 | n/a | n/a |
| benign_obstruction | window | 84/100 | 0.7532 to 0.9057 | n/a | n/a |
| benign_obstruction | stack | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| jam_hard | marsad | 100/100 | 0.9638 to 1.0 | 2.46 (2.31 to 2.7) | 0 |
| jam_hard | gate | 100/100 | 0.9638 to 1.0 | 2.94 (2.79 to 5.02) | 0 |
| jam_hard | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 7.94 (7.82 to 8.02) | 0 |
| jam_hard | window | 100/100 | 0.9638 to 1.0 | 7.94 (7.82 to 8.02) | 3 |
| jam_hard | stack | 100/100 | 0.9638 to 1.0 | 0.75 (0.72 to 0.77) | 3 |
| jam_soft | marsad | 100/100 | 0.9638 to 1.0 | 4.71 (4.52 to 4.85) | 0 |
| jam_soft | gate | 100/100 | 0.9638 to 1.0 | 4.47 (4.16 to 4.75) | 0 |
| jam_soft | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 5.82 (5.28 to 6.35) | 0 |
| jam_soft | window | 100/100 | 0.9638 to 1.0 | 6.27 (5.41 to 6.94) | 1 |
| jam_soft | stack | 100/100 | 0.9638 to 1.0 | 1.66 (1.6 to 1.83) | 1 |
| nominal | marsad | 0/100 | 0.0 to 0.0362 | n/a | n/a |
| nominal | gate | 0/100 | 0.0 to 0.0362 | n/a | n/a |
| nominal | ekf2_gate_ref | 0/100 | 0.0 to 0.0362 | n/a | n/a |
| nominal | window | 10/100 | 0.049 to 0.1762 | n/a | n/a |
| nominal | stack | 10/100 | 0.049 to 0.1762 | n/a | n/a |
| replay | marsad | 100/100 | 0.9638 to 1.0 | 0.1 (0.08 to 0.14) | 0 |
| replay | gate | 100/100 | 0.9638 to 1.0 | 0.1 (0.08 to 0.14) | 0 |
| replay | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 0.1 (0.08 to 0.14) | 0 |
| replay | window | 100/100 | 0.9638 to 1.0 | 0.1 (0.08 to 0.14) | 4 |
| replay | stack | 100/100 | 0.9638 to 1.0 | 0.1 (0.08 to 0.14) | 4 |
| spoof_drift | marsad | 100/100 | 0.9638 to 1.0 | 28.13 (25.83 to 31.9) | 0 |
| spoof_drift | gate | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| spoof_drift | ekf2_gate_ref | 54/100 | 0.4374 to 0.6402 | 26.67 (24.26 to 29.25) | 0 |
| spoof_drift | window | 100/100 | 0.9638 to 1.0 | 23.96 (21.34 to 29.49) | 6 |
| spoof_drift | stack | 100/100 | 0.9638 to 1.0 | 23.96 (20.79 to 29.49) | 6 |
| spoof_drift_noref | marsad | 57/100 | 0.4671 to 0.6686 | 36.61 (34.02 to 38.76) | 0 |
| spoof_drift_noref | gate | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| spoof_drift_noref | ekf2_gate_ref | 24/100 | 0.1602 to 0.3357 | 28.45 (25.81 to 34.75) | 0 |
| spoof_drift_noref | window | 83/100 | 0.7418 to 0.8977 | 46.55 (26.83 to 53.74) | 30 |
| spoof_drift_noref | stack | 83/100 | 0.7418 to 0.8977 | 46.55 (26.83 to 53.74) | 30 |
| spoof_drift_ref_outage | marsad | 100/100 | 0.9638 to 1.0 | 55.86 (40.75 to 66.41) | 0 |
| spoof_drift_ref_outage | gate | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| spoof_drift_ref_outage | ekf2_gate_ref | 51/100 | 0.408 to 0.6114 | 48.85 (39.42 to 54.89) | 0 |
| spoof_drift_ref_outage | window | 100/100 | 0.9638 to 1.0 | 52.39 (45.4 to 58.09) | 5 |
| spoof_drift_ref_outage | stack | 100/100 | 0.9638 to 1.0 | 52.39 (45.4 to 58.09) | 5 |
| spoof_drift_stealth | marsad | 100/100 | 0.9638 to 1.0 | 53.28 (51.25 to 55.58) | 0 |
| spoof_drift_stealth | gate | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| spoof_drift_stealth | ekf2_gate_ref | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| spoof_drift_stealth | window | 100/100 | 0.9638 to 1.0 | 40.13 (38.12 to 43.05) | 3 |
| spoof_drift_stealth | stack | 100/100 | 0.9638 to 1.0 | 40.13 (38.12 to 43.05) | 3 |
| spoof_jump | marsad | 100/100 | 0.9638 to 1.0 | 0.08 (0.07 to 0.11) | 0 |
| spoof_jump | gate | 100/100 | 0.9638 to 1.0 | 0.08 (0.07 to 0.11) | 0 |
| spoof_jump | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 0.08 (0.07 to 0.11) | 0 |
| spoof_jump | window | 100/100 | 0.9638 to 1.0 | 0.08 (0.07 to 0.11) | 5 |
| spoof_jump | stack | 100/100 | 0.9638 to 1.0 | 0.08 (0.07 to 0.11) | 5 |
| spoof_jump_transient | marsad | 100/100 | 0.9638 to 1.0 | 0.1 (0.09 to 0.11) | 0 |
| spoof_jump_transient | gate | 100/100 | 0.9638 to 1.0 | 0.1 (0.09 to 0.11) | 0 |
| spoof_jump_transient | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 0.1 (0.09 to 0.11) | 0 |
| spoof_jump_transient | window | 100/100 | 0.9638 to 1.0 | 0.1 (0.09 to 0.11) | 3 |
| spoof_jump_transient | stack | 100/100 | 0.9638 to 1.0 | 0.1 (0.09 to 0.11) | 3 |

Paired exact McNemar tests against Marsad (detection):

* jam_hard, gate: only Marsad 0, only gate 0, p 1.0
* jam_hard, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* jam_hard, window: only Marsad 0, only window 0, p 1.0
* jam_hard, stack: only Marsad 0, only stack 0, p 1.0
* jam_soft, gate: only Marsad 0, only gate 0, p 1.0
* jam_soft, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* jam_soft, window: only Marsad 0, only window 0, p 1.0
* jam_soft, stack: only Marsad 0, only stack 0, p 1.0
* replay, gate: only Marsad 0, only gate 0, p 1.0
* replay, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* replay, window: only Marsad 0, only window 0, p 1.0
* replay, stack: only Marsad 0, only stack 0, p 1.0
* spoof_drift, gate: only Marsad 100, only gate 0, p 0.0
* spoof_drift, ekf2_gate_ref: only Marsad 46, only ekf2_gate_ref 0, p 0.0
* spoof_drift, window: only Marsad 0, only window 0, p 1.0
* spoof_drift, stack: only Marsad 0, only stack 0, p 1.0
* spoof_drift_noref, gate: only Marsad 57, only gate 0, p 0.0
* spoof_drift_noref, ekf2_gate_ref: only Marsad 39, only ekf2_gate_ref 6, p 1e-06
* spoof_drift_noref, window: only Marsad 9, only window 35, p 0.000106
* spoof_drift_noref, stack: only Marsad 9, only stack 35, p 0.000106
* spoof_drift_ref_outage, gate: only Marsad 100, only gate 0, p 0.0
* spoof_drift_ref_outage, ekf2_gate_ref: only Marsad 49, only ekf2_gate_ref 0, p 0.0
* spoof_drift_ref_outage, window: only Marsad 0, only window 0, p 1.0
* spoof_drift_ref_outage, stack: only Marsad 0, only stack 0, p 1.0
* spoof_drift_stealth, gate: only Marsad 100, only gate 0, p 0.0
* spoof_drift_stealth, ekf2_gate_ref: only Marsad 100, only ekf2_gate_ref 0, p 0.0
* spoof_drift_stealth, window: only Marsad 0, only window 0, p 1.0
* spoof_drift_stealth, stack: only Marsad 0, only stack 0, p 1.0
* spoof_jump, gate: only Marsad 0, only gate 0, p 1.0
* spoof_jump, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* spoof_jump, window: only Marsad 0, only window 0, p 1.0
* spoof_jump, stack: only Marsad 0, only stack 0, p 1.0
* spoof_jump_transient, gate: only Marsad 0, only gate 0, p 1.0
* spoof_jump_transient, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* spoof_jump_transient, window: only Marsad 0, only window 0, p 1.0
* spoof_jump_transient, stack: only Marsad 0, only stack 0, p 1.0
