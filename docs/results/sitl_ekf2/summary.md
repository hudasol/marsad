# PX4 EKF2 in the loop (SITL EKF2)

n is 4 runs per case (four headings). Detection counts are runs in which the method left TRUSTED after the onset.
Arm ekf: reference is EKF2 fused velocity. Arm truth: reference is simulator truth velocity.

| case | Marsad ekf arm | 95% CI | median latency s | Marsad truth arm | gate | window | stack | EKF2 rejection of 1 s or longer | EKF2 position error at 60 s, m |
|---|---|---|---|---|---|---|---|---|---|
| clean | 0/4 | 0.00 to 0.60 | n/a | 0/4 | 0/4 | 0/4 | 0/4 | 3/4 | n/a |
| drift:0.25 position only | 0/4 | 0.00 to 0.60 | n/a | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 13 to 13 |
| drift:0.25 velocity consistent | 0/4 | 0.00 to 0.60 | n/a | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 14 to 14 |
| drift:0.5 position only | 4/4 | 0.40 to 1.00 | 62.0 | 4/4 | 0/4 | 4/4 | 4/4 | 0/4 | 26 to 26 |
| drift:0.5 velocity consistent | 0/4 | 0.00 to 0.60 | n/a | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 27 to 27 |
| drift:1.0 position only | 4/4 | 0.40 to 1.00 | 34.6 | 4/4 | 0/4 | 4/4 | 4/4 | 0/4 | 53 to 53 |
| drift:1.0 velocity consistent | 0/4 | 0.00 to 0.60 | n/a | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 55 to 55 |
| drift:2.0 position only | 4/4 | 0.40 to 1.00 | 19.4 | 4/4 | 0/4 | 4/4 | 4/4 | 0/4 | 105 to 106 |
| drift:2.0 velocity consistent | 0/4 | 0.00 to 0.60 | n/a | 4/4 | 0/4 | 0/4 | 0/4 | 0/4 | 110 to 110 |
| jump:1000 | 4/4 | 0.40 to 1.00 | 0.0 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 1000 to 1000 |
| jump:200 | 4/4 | 0.40 to 1.00 | 0.1 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 200 to 200 |
| jump:50 | 4/4 | 0.40 to 1.00 | 0.1 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 50 to 50 |

Runs with a Marsad or baseline alarm before the onset: 0
