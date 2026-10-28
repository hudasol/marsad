# Roadmap

Ordered by what the evidence says is weakest. Each item names the result that motivates it. Methods that change
detection behaviour get a preregistration before they are run, as with the earlier fixes.

## Next

1. **Fallback consistency channel without an independent reference.**
   Motivation: `spoof_drift_noref` is detected in 53% of runs, the window baseline in 87% (`docs/BASELINES.md`).
   The channel would compare displacement with the receiver's own velocity integral when no reference exists. The
   hard part is keeping the nominal false alarm rate at zero, because a receiver velocity that a spoofer shifts
   consistently carries no information. Needs its own preregistration.
2. **Replay through the real EKF2.**
   Motivation: the EKF2 style baselines are reimplementations. Feed recorded sensor data through PX4 with injected
   GNSS, in software in the loop, and compare the vehicle's own accept and reject decisions with Marsad.
3. **Score the baselines and the v1.4.0 engine on the real logs.**
   Motivation: REAL LOG results exist only for the v1.3.0 engine and cover the false alarm side. Run
   `marsad replay` and `scripts/replay_baselines.py` on `flight1.ulg` and `flight2.ulg` and record the result in
   `docs/VALIDATION.md`.
4. **Latency on slow drift.**
   Motivation: a plain window test is faster (57.1 s against 113.6 s at 0.25 m/s on SIH). Look at whether the
   bias allowance can be made adaptive per vehicle without reintroducing absorption.

## Later

- Live validation on a flight controller or a range with an authorised test source, replacing the pymavlink loopback.
- Authentication scopes and rate limits on the API beyond the single shared key.
- A second independent reference type (barometer plus airspeed, wheel odometry) evaluated on its own.
- Real interference data for the map, from a source that permits redistribution.

## Not planned

Anything that generates or transmits RF, and any command path to a vehicle. Marsad stays advisory.
