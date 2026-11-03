# literature family, seeds 0 to 29

| kind | method | detected or false alarm | 95% interval | median latency s (95% interval) | pre attack false alarms |
|---|---|---|---|---|---|
| benign_multipath | marsad | 1/30 | 0.0008 to 0.1722 | n/a | n/a |
| benign_multipath | gate | 25/30 | 0.6528 to 0.9436 | n/a | n/a |
| benign_multipath | ekf2_gate_ref | 12/30 | 0.2266 to 0.594 | n/a | n/a |
| benign_multipath | window | 21/30 | 0.506 to 0.8527 | n/a | n/a |
| benign_multipath | stack | 30/30 | 0.8843 to 1.0 | n/a | n/a |
| benign_obstruction | marsad | 30/30 | 0.8843 to 1.0 | n/a | n/a |
| benign_obstruction | gate | 30/30 | 0.8843 to 1.0 | n/a | n/a |
| benign_obstruction | ekf2_gate_ref | 15/30 | 0.313 to 0.687 | n/a | n/a |
| benign_obstruction | window | 25/30 | 0.6528 to 0.9436 | n/a | n/a |
| benign_obstruction | stack | 30/30 | 0.8843 to 1.0 | n/a | n/a |
| lit_equal_power | marsad | 30/30 | 0.8843 to 1.0 | 73.06 (70.46 to 73.8) | 0 |
| lit_equal_power | gate | 30/30 | 0.8843 to 1.0 | 217.38 (193.83 to 225.94) | 0 |
| lit_equal_power | ekf2_gate_ref | 30/30 | 0.8843 to 1.0 | 70.66 (67.26 to 71.39) | 0 |
| lit_equal_power | window | 30/30 | 0.8843 to 1.0 | 70.11 (67.61 to 70.79) | 0 |
| lit_equal_power | stack | 30/30 | 0.8843 to 1.0 | 70.11 (66.64 to 70.71) | 0 |
| lit_jam_chirp | marsad | 30/30 | 0.8843 to 1.0 | 9.15 (7.99 to 10.27) | 0 |
| lit_jam_chirp | gate | 30/30 | 0.8843 to 1.0 | 6.51 (5.18 to 7.24) | 0 |
| lit_jam_chirp | ekf2_gate_ref | 30/30 | 0.8843 to 1.0 | 9.97 (8.03 to 12.24) | 0 |
| lit_jam_chirp | window | 30/30 | 0.8843 to 1.0 | 11.19 (9.39 to 12.0) | 0 |
| lit_jam_chirp | stack | 30/30 | 0.8843 to 1.0 | 8.22 (7.12 to 8.89) | 0 |
| lit_switch | marsad | 30/30 | 0.8843 to 1.0 | 1.5 (1.48 to 1.52) | 0 |
| lit_switch | gate | 30/30 | 0.8843 to 1.0 | 2.1 (2.08 to 2.12) | 0 |
| lit_switch | ekf2_gate_ref | 30/30 | 0.8843 to 1.0 | 4.26 (3.41 to 5.03) | 0 |
| lit_switch | window | 28/30 | 0.7793 to 0.9918 | 4.14 (3.29 to 5.01) | 0 |
| lit_switch | stack | 30/30 | 0.8843 to 1.0 | 4.26 (3.41 to 5.03) | 0 |
| lit_takeover | marsad | 30/30 | 0.8843 to 1.0 | 10.25 (8.52 to 16.79) | 0 |
| lit_takeover | gate | 0/30 | 0.0 to 0.1157 | n/a | 0 |
| lit_takeover | ekf2_gate_ref | 30/30 | 0.8843 to 1.0 | 77.69 (71.48 to 82.39) | 0 |
| lit_takeover | window | 30/30 | 0.8843 to 1.0 | 72.28 (70.74 to 76.67) | 0 |
| lit_takeover | stack | 30/30 | 0.8843 to 1.0 | 3.51 (3.16 to 4.42) | 0 |
| lit_time_push | marsad | 30/30 | 0.8843 to 1.0 | 13.56 (12.22 to 16.6) | 0 |
| lit_time_push | gate | 0/30 | 0.0 to 0.1157 | n/a | 0 |
| lit_time_push | ekf2_gate_ref | 17/30 | 0.3743 to 0.7454 | 10.19 (9.13 to 13.87) | 0 |
| lit_time_push | window | 30/30 | 0.8843 to 1.0 | 10.14 (7.97 to 16.38) | 0 |
| lit_time_push | stack | 30/30 | 0.8843 to 1.0 | 7.7 (6.33 to 9.31) | 0 |
| nominal | marsad | 0/30 | 0.0 to 0.1157 | n/a | n/a |
| nominal | gate | 0/30 | 0.0 to 0.1157 | n/a | n/a |
| nominal | ekf2_gate_ref | 0/30 | 0.0 to 0.1157 | n/a | n/a |
| nominal | window | 1/30 | 0.0008 to 0.1722 | n/a | n/a |
| nominal | stack | 1/30 | 0.0008 to 0.1722 | n/a | n/a |

Paired exact McNemar tests against Marsad (detection):

* lit_equal_power, gate: only Marsad 0, only gate 0, p 1.0
* lit_equal_power, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_equal_power, window: only Marsad 0, only window 0, p 1.0
* lit_equal_power, stack: only Marsad 0, only stack 0, p 1.0
* lit_jam_chirp, gate: only Marsad 0, only gate 0, p 1.0
* lit_jam_chirp, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_jam_chirp, window: only Marsad 0, only window 0, p 1.0
* lit_jam_chirp, stack: only Marsad 0, only stack 0, p 1.0
* lit_switch, gate: only Marsad 0, only gate 0, p 1.0
* lit_switch, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_switch, window: only Marsad 2, only window 0, p 0.5
* lit_switch, stack: only Marsad 0, only stack 0, p 1.0
* lit_takeover, gate: only Marsad 30, only gate 0, p 0.0
* lit_takeover, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_takeover, window: only Marsad 0, only window 0, p 1.0
* lit_takeover, stack: only Marsad 0, only stack 0, p 1.0
* lit_time_push, gate: only Marsad 30, only gate 0, p 0.0
* lit_time_push, ekf2_gate_ref: only Marsad 13, only ekf2_gate_ref 0, p 0.000244
* lit_time_push, window: only Marsad 0, only window 0, p 1.0
* lit_time_push, stack: only Marsad 0, only stack 0, p 1.0
