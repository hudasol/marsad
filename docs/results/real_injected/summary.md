# Attacks injected into real flights (REAL LOG + INJECTED)

## Arm ekf: n flights run 101, scored 52

Excluded: {"Marsad not TRUSTED in the 30 s before the earliest onset": 23, "no reference for this arm": 2, "less than 300 s of fixes": 24}

| case | method | detected | 95% CI | median latency s (95% CI) | median offset m | p vs Marsad |
|---|---|---|---|---|---|---|
| jump_50 | marsad | 52/52 | 0.93 to 1.00 | 0.4 (0.4 to 0.5) | 50 |  |
| jump_50 | gate | 52/52 | 0.93 to 1.00 | 0.4 (0.4 to 0.5) | 50 | 1 |
| jump_50 | ekf2_gate_ref | 52/52 | 0.93 to 1.00 | 0.4 (0.4 to 0.5) | 50 | 1 |
| jump_50 | window | 52/52 | 0.93 to 1.00 | 0.4 (0.4 to 0.5) | 50 | 1 |
| jump_50 | stack | 52/52 | 0.93 to 1.00 | 0.4 (0.4 to 0.5) | 50 | 1 |
| jump_200 | marsad | 52/52 | 0.93 to 1.00 | 0.4 (0.4 to 0.5) | 200 |  |
| jump_200 | gate | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 200 | 1 |
| jump_200 | ekf2_gate_ref | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 200 | 1 |
| jump_200 | window | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 200 | 1 |
| jump_200 | stack | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 200 | 1 |
| jump_1000 | marsad | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 1000 |  |
| jump_1000 | gate | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 1000 | 1 |
| jump_1000 | ekf2_gate_ref | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 1000 | 1 |
| jump_1000 | window | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 1000 | 1 |
| jump_1000 | stack | 52/52 | 0.93 to 1.00 | 0.5 (0.4 to 0.5) | 1000 | 1 |
| drift_0.25_velcons | marsad | 45/52 | 0.74 to 0.94 | 111.8 (110.2 to 112.8) | 27 |  |
| drift_0.25_velcons | gate | 2/52 | 0.00 to 0.13 | 76.1 (72.6 to 79.7) | 18 | 2.61e-12 |
| drift_0.25_velcons | ekf2_gate_ref | 3/52 | 0.01 to 0.16 | 189.5 (144.8 to 1921.0) | 46 | 5.12e-12 |
| drift_0.25_velcons | window | 52/52 | 0.93 to 1.00 | 57.6 (57.2 to 57.9) | 13 | 0.0156 |
| drift_0.25_velcons | stack | 52/52 | 0.93 to 1.00 | 57.5 (57.1 to 57.9) | 13 | 0.0156 |
| drift_0.25_posonly | marsad | 45/52 | 0.74 to 0.94 | 111.0 (109.1 to 112.6) | 26 |  |
| drift_0.25_posonly | gate | 2/52 | 0.00 to 0.13 | 65.4 (62.6 to 68.2) | 15 | 2.61e-12 |
| drift_0.25_posonly | ekf2_gate_ref | 3/52 | 0.01 to 0.16 | 166.6 (127.6 to 1697.2) | 40 | 5.12e-12 |
| drift_0.25_posonly | window | 52/52 | 0.93 to 1.00 | 57.7 (57.3 to 58.0) | 13 | 0.0156 |
| drift_0.25_posonly | stack | 52/52 | 0.93 to 1.00 | 57.7 (57.2 to 58.0) | 13 | 0.0156 |
| drift_0.5_velcons | marsad | 52/52 | 0.93 to 1.00 | 42.3 (41.6 to 42.6) | 19 |  |
| drift_0.5_velcons | gate | 2/52 | 0.00 to 0.13 | 70.5 (68.3 to 72.7) | 33 | 1.78e-15 |
| drift_0.5_velcons | ekf2_gate_ref | 48/52 | 0.81 to 0.98 | 80.1 (71.5 to 95.7) | 38 | 0.125 |
| drift_0.5_velcons | window | 52/52 | 0.93 to 1.00 | 31.6 (31.3 to 31.8) | 13 | 1 |
| drift_0.5_velcons | stack | 52/52 | 0.93 to 1.00 | 31.6 (31.3 to 31.8) | 13 | 1 |
| drift_0.5_posonly | marsad | 52/52 | 0.93 to 1.00 | 41.9 (41.4 to 42.1) | 18 |  |
| drift_0.5_posonly | gate | 2/52 | 0.00 to 0.13 | 59.0 (38.3 to 79.7) | 27 | 1.78e-15 |
| drift_0.5_posonly | ekf2_gate_ref | 49/52 | 0.84 to 0.99 | 82.3 (75.6 to 93.8) | 39 | 0.25 |
| drift_0.5_posonly | window | 52/52 | 0.93 to 1.00 | 31.5 (31.2 to 31.7) | 13 | 1 |
| drift_0.5_posonly | stack | 52/52 | 0.93 to 1.00 | 31.5 (31.2 to 31.6) | 13 | 1 |
| drift_1.0_velcons | marsad | 52/52 | 0.93 to 1.00 | 25.5 (25.3 to 25.7) | 20 |  |
| drift_1.0_velcons | gate | 2/52 | 0.00 to 0.13 | 108.5 (104.7 to 112.4) | 104 | 1.78e-15 |
| drift_1.0_velcons | ekf2_gate_ref | 51/52 | 0.90 to 1.00 | 19.0 (18.8 to 19.2) | 14 | 1 |
| drift_1.0_velcons | window | 52/52 | 0.93 to 1.00 | 18.5 (18.3 to 18.7) | 13 | 1 |
| drift_1.0_velcons | stack | 52/52 | 0.93 to 1.00 | 18.4 (18.3 to 18.6) | 13 | 1 |
| drift_1.0_posonly | marsad | 52/52 | 0.93 to 1.00 | 25.4 (25.1 to 25.6) | 20 |  |
| drift_1.0_posonly | gate | 2/52 | 0.00 to 0.13 | 81.1 (60.6 to 101.5) | 76 | 1.78e-15 |
| drift_1.0_posonly | ekf2_gate_ref | 51/52 | 0.90 to 1.00 | 19.0 (18.8 to 19.1) | 14 | 1 |
| drift_1.0_posonly | window | 52/52 | 0.93 to 1.00 | 18.6 (18.4 to 18.7) | 14 | 1 |
| drift_1.0_posonly | stack | 52/52 | 0.93 to 1.00 | 18.4 (18.2 to 18.6) | 13 | 1 |
| drift_2.0_velcons | marsad | 52/52 | 0.93 to 1.00 | 15.7 (15.5 to 15.9) | 21 |  |
| drift_2.0_velcons | gate | 2/52 | 0.00 to 0.13 | 77.7 (69.4 to 86.1) | 145 | 1.78e-15 |
| drift_2.0_velcons | ekf2_gate_ref | 52/52 | 0.93 to 1.00 | 11.3 (11.2 to 11.4) | 13 | 1 |
| drift_2.0_velcons | window | 52/52 | 0.93 to 1.00 | 12.0 (12.0 to 12.1) | 14 | 1 |
| drift_2.0_velcons | stack | 52/52 | 0.93 to 1.00 | 11.3 (11.2 to 11.4) | 13 | 1 |
| drift_2.0_posonly | marsad | 52/52 | 0.93 to 1.00 | 15.6 (15.5 to 15.7) | 21 |  |
| drift_2.0_posonly | gate | 2/52 | 0.00 to 0.13 | 70.5 (41.7 to 99.3) | 131 | 1.78e-15 |
| drift_2.0_posonly | ekf2_gate_ref | 52/52 | 0.93 to 1.00 | 11.1 (11.1 to 11.2) | 12 | 1 |
| drift_2.0_posonly | window | 52/52 | 0.93 to 1.00 | 12.0 (12.0 to 12.1) | 14 | 1 |
| drift_2.0_posonly | stack | 52/52 | 0.93 to 1.00 | 11.1 (11.1 to 11.2) | 12 | 1 |

## Arm indep: n flights run 6, scored 2

Excluded: {"Marsad not TRUSTED in the 30 s before the earliest onset": 2, "less than 300 s of fixes": 2}

| case | method | detected | 95% CI | median latency s (95% CI) | median offset m | p vs Marsad |
|---|---|---|---|---|---|---|
| jump_50 | marsad | 2/2 | 0.16 to 1.00 | 0.4 (0.3 to 0.6) | 50 |  |
| jump_50 | gate | 2/2 | 0.16 to 1.00 | 0.4 (0.3 to 0.6) | 50 | 1 |
| jump_50 | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 0.4 (0.3 to 0.6) | 50 | 1 |
| jump_50 | window | 2/2 | 0.16 to 1.00 | 0.4 (0.3 to 0.6) | 50 | 1 |
| jump_50 | stack | 2/2 | 0.16 to 1.00 | 0.4 (0.3 to 0.6) | 50 | 1 |
| jump_200 | marsad | 2/2 | 0.16 to 1.00 | 0.4 (0.4 to 0.4) | 200 |  |
| jump_200 | gate | 2/2 | 0.16 to 1.00 | 0.4 (0.4 to 0.4) | 200 | 1 |
| jump_200 | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 0.4 (0.4 to 0.4) | 200 | 1 |
| jump_200 | window | 2/2 | 0.16 to 1.00 | 0.4 (0.4 to 0.4) | 200 | 1 |
| jump_200 | stack | 2/2 | 0.16 to 1.00 | 0.4 (0.4 to 0.4) | 200 | 1 |
| jump_1000 | marsad | 2/2 | 0.16 to 1.00 | 0.6 (0.5 to 0.8) | 1000 |  |
| jump_1000 | gate | 2/2 | 0.16 to 1.00 | 0.6 (0.5 to 0.8) | 1000 | 1 |
| jump_1000 | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 0.6 (0.5 to 0.8) | 1000 | 1 |
| jump_1000 | window | 2/2 | 0.16 to 1.00 | 0.6 (0.5 to 0.8) | 1000 | 1 |
| jump_1000 | stack | 2/2 | 0.16 to 1.00 | 0.6 (0.5 to 0.8) | 1000 | 1 |
| drift_0.25_velcons | marsad | 2/2 | 0.16 to 1.00 | 94.5 (81.3 to 107.6) | 22 |  |
| drift_0.25_velcons | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_0.25_velcons | ekf2_gate_ref | 1/2 | 0.01 to 0.99 | 144.8 | 35 | 1 |
| drift_0.25_velcons | window | 2/2 | 0.16 to 1.00 | 55.1 (53.6 to 56.5) | 13 | 1 |
| drift_0.25_velcons | stack | 2/2 | 0.16 to 1.00 | 55.1 (53.6 to 56.5) | 13 | 1 |
| drift_0.25_posonly | marsad | 2/2 | 0.16 to 1.00 | 87.6 (82.1 to 93.1) | 21 |  |
| drift_0.25_posonly | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_0.25_posonly | ekf2_gate_ref | 1/2 | 0.01 to 0.99 | 127.6 | 31 | 1 |
| drift_0.25_posonly | window | 2/2 | 0.16 to 1.00 | 51.8 (46.8 to 56.7) | 12 | 1 |
| drift_0.25_posonly | stack | 2/2 | 0.16 to 1.00 | 50.4 (44.0 to 56.7) | 11 | 1 |
| drift_0.5_velcons | marsad | 2/2 | 0.16 to 1.00 | 39.5 (35.6 to 43.4) | 17 |  |
| drift_0.5_velcons | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_0.5_velcons | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 75.4 (47.3 to 103.5) | 35 | 1 |
| drift_0.5_velcons | window | 2/2 | 0.16 to 1.00 | 31.1 (30.5 to 31.6) | 13 | 1 |
| drift_0.5_velcons | stack | 2/2 | 0.16 to 1.00 | 31.1 (30.5 to 31.6) | 13 | 1 |
| drift_0.5_posonly | marsad | 2/2 | 0.16 to 1.00 | 39.2 (36.4 to 41.9) | 17 |  |
| drift_0.5_posonly | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_0.5_posonly | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 87.2 (36.7 to 137.8) | 41 | 1 |
| drift_0.5_posonly | window | 2/2 | 0.16 to 1.00 | 30.4 (29.8 to 31.0) | 13 | 1 |
| drift_0.5_posonly | stack | 2/2 | 0.16 to 1.00 | 29.7 (28.4 to 31.0) | 12 | 1 |
| drift_1.0_velcons | marsad | 2/2 | 0.16 to 1.00 | 23.8 (22.3 to 25.3) | 19 |  |
| drift_1.0_velcons | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_1.0_velcons | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 18.7 (18.3 to 19.1) | 14 | 1 |
| drift_1.0_velcons | window | 2/2 | 0.16 to 1.00 | 18.4 (18.0 to 18.8) | 13 | 1 |
| drift_1.0_velcons | stack | 2/2 | 0.16 to 1.00 | 18.3 (18.0 to 18.6) | 13 | 1 |
| drift_1.0_posonly | marsad | 2/2 | 0.16 to 1.00 | 22.8 (22.3 to 23.3) | 18 |  |
| drift_1.0_posonly | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_1.0_posonly | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 18.5 (18.1 to 18.8) | 13 | 1 |
| drift_1.0_posonly | window | 2/2 | 0.16 to 1.00 | 17.7 (16.8 to 18.5) | 13 | 1 |
| drift_1.0_posonly | stack | 2/2 | 0.16 to 1.00 | 17.7 (16.8 to 18.5) | 13 | 1 |
| drift_2.0_velcons | marsad | 2/2 | 0.16 to 1.00 | 14.9 (14.6 to 15.1) | 20 |  |
| drift_2.0_velcons | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_2.0_velcons | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 11.0 (10.9 to 11.1) | 12 | 1 |
| drift_2.0_velcons | window | 2/2 | 0.16 to 1.00 | 11.4 (10.6 to 12.1) | 13 | 1 |
| drift_2.0_velcons | stack | 2/2 | 0.16 to 1.00 | 10.9 (10.6 to 11.1) | 12 | 1 |
| drift_2.0_posonly | marsad | 2/2 | 0.16 to 1.00 | 14.9 (14.9 to 14.9) | 20 |  |
| drift_2.0_posonly | gate | 0/2 | 0.00 to 0.84 | n/a | n/a | 0.5 |
| drift_2.0_posonly | ekf2_gate_ref | 2/2 | 0.16 to 1.00 | 11.0 (10.9 to 11.1) | 12 | 1 |
| drift_2.0_posonly | window | 2/2 | 0.16 to 1.00 | 12.1 (11.9 to 12.3) | 14 | 1 |
| drift_2.0_posonly | stack | 2/2 | 0.16 to 1.00 | 11.0 (10.9 to 11.1) | 12 | 1 |
