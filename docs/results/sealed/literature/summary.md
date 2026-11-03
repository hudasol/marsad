# literature family, seeds 7000 to 7099

| kind | method | detected or false alarm | 95% interval | median latency s (95% interval) | pre attack false alarms |
|---|---|---|---|---|---|
| benign_multipath | marsad | 6/100 | 0.0223 to 0.126 | n/a | n/a |
| benign_multipath | gate | 66/100 | 0.5585 to 0.7518 | n/a | n/a |
| benign_multipath | ekf2_gate_ref | 32/100 | 0.2302 to 0.4208 | n/a | n/a |
| benign_multipath | window | 65/100 | 0.5482 to 0.7427 | n/a | n/a |
| benign_multipath | stack | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| benign_obstruction | marsad | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| benign_obstruction | gate | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| benign_obstruction | ekf2_gate_ref | 58/100 | 0.4771 to 0.678 | n/a | n/a |
| benign_obstruction | window | 78/100 | 0.6861 to 0.8567 | n/a | n/a |
| benign_obstruction | stack | 100/100 | 0.9638 to 1.0 | n/a | n/a |
| lit_equal_power | marsad | 100/100 | 0.9638 to 1.0 | 73.37 (73.02 to 73.67) | 0 |
| lit_equal_power | gate | 100/100 | 0.9638 to 1.0 | 204.04 (198.02 to 215.28) | 0 |
| lit_equal_power | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 70.77 (70.18 to 71.75) | 0 |
| lit_equal_power | window | 100/100 | 0.9638 to 1.0 | 69.42 (68.74 to 70.53) | 0 |
| lit_equal_power | stack | 100/100 | 0.9638 to 1.0 | 69.42 (68.65 to 70.33) | 0 |
| lit_jam_chirp | marsad | 100/100 | 0.9638 to 1.0 | 9.27 (8.79 to 9.71) | 0 |
| lit_jam_chirp | gate | 100/100 | 0.9638 to 1.0 | 6.41 (5.18 to 6.87) | 0 |
| lit_jam_chirp | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 10.61 (9.83 to 11.28) | 0 |
| lit_jam_chirp | window | 100/100 | 0.9638 to 1.0 | 11.08 (9.62 to 12.56) | 0 |
| lit_jam_chirp | stack | 100/100 | 0.9638 to 1.0 | 8.08 (7.55 to 8.53) | 0 |
| lit_switch | marsad | 100/100 | 0.9638 to 1.0 | 1.48 (1.46 to 1.51) | 0 |
| lit_switch | gate | 99/100 | 0.9455 to 0.9997 | 2.09 (2.06 to 2.12) | 0 |
| lit_switch | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 4.02 (3.78 to 4.39) | 0 |
| lit_switch | window | 94/100 | 0.874 to 0.9777 | 3.92 (3.6 to 4.21) | 0 |
| lit_switch | stack | 100/100 | 0.9638 to 1.0 | 4.02 (3.78 to 4.39) | 0 |
| lit_takeover | marsad | 100/100 | 0.9638 to 1.0 | 11.37 (9.53 to 17.95) | 0 |
| lit_takeover | gate | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| lit_takeover | ekf2_gate_ref | 100/100 | 0.9638 to 1.0 | 78.64 (73.08 to 80.17) | 0 |
| lit_takeover | window | 100/100 | 0.9638 to 1.0 | 75.04 (71.53 to 76.52) | 0 |
| lit_takeover | stack | 100/100 | 0.9638 to 1.0 | 3.92 (3.62 to 4.6) | 0 |
| lit_time_push | marsad | 100/100 | 0.9638 to 1.0 | 17.75 (15.68 to 20.57) | 0 |
| lit_time_push | gate | 0/100 | 0.0 to 0.0362 | n/a | 0 |
| lit_time_push | ekf2_gate_ref | 38/100 | 0.2848 to 0.4825 | 11.84 (9.8 to 16.94) | 0 |
| lit_time_push | window | 100/100 | 0.9638 to 1.0 | 12.71 (11.43 to 15.81) | 0 |
| lit_time_push | stack | 100/100 | 0.9638 to 1.0 | 11.59 (9.7 to 13.08) | 0 |
| nominal | marsad | 0/100 | 0.0 to 0.0362 | n/a | n/a |
| nominal | gate | 0/100 | 0.0 to 0.0362 | n/a | n/a |
| nominal | ekf2_gate_ref | 0/100 | 0.0 to 0.0362 | n/a | n/a |
| nominal | window | 3/100 | 0.0062 to 0.0852 | n/a | n/a |
| nominal | stack | 3/100 | 0.0062 to 0.0852 | n/a | n/a |

Paired exact McNemar tests against Marsad (detection):

* lit_equal_power, gate: only Marsad 0, only gate 0, p 1.0
* lit_equal_power, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_equal_power, window: only Marsad 0, only window 0, p 1.0
* lit_equal_power, stack: only Marsad 0, only stack 0, p 1.0
* lit_jam_chirp, gate: only Marsad 0, only gate 0, p 1.0
* lit_jam_chirp, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_jam_chirp, window: only Marsad 0, only window 0, p 1.0
* lit_jam_chirp, stack: only Marsad 0, only stack 0, p 1.0
* lit_switch, gate: only Marsad 1, only gate 0, p 1.0
* lit_switch, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_switch, window: only Marsad 6, only window 0, p 0.03125
* lit_switch, stack: only Marsad 0, only stack 0, p 1.0
* lit_takeover, gate: only Marsad 100, only gate 0, p 0.0
* lit_takeover, ekf2_gate_ref: only Marsad 0, only ekf2_gate_ref 0, p 1.0
* lit_takeover, window: only Marsad 0, only window 0, p 1.0
* lit_takeover, stack: only Marsad 0, only stack 0, p 1.0
* lit_time_push, gate: only Marsad 100, only gate 0, p 0.0
* lit_time_push, ekf2_gate_ref: only Marsad 62, only ekf2_gate_ref 0, p 0.0
* lit_time_push, window: only Marsad 0, only window 0, p 1.0
* lit_time_push, stack: only Marsad 0, only stack 0, p 1.0
