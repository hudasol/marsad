# Roadmap

Ordered by what the evidence says is weakest. Each item names the result that motivates it. Methods that change
detection behaviour get a preregistration before they are run, as with the earlier fixes.

## Next

Ordered by what the v1.5.0 evidence says is weakest. Each change to detection behaviour gets a preregistration with
kill criteria first, and is developed on the design subset and the development seeds only.

1. **Real flight false alarms.** 46 of 101 corpus flights reached DENIED. The adaptive timeout and recovery timer trial
   was not adopted (it missed 68 of 101 and raised episodes per hour). Open causes: lost fixes under 3 s on 1 Hz
   receivers (about half of the alarmed flights), a cold start latch in the drift check, and the unverifiable
   reacquisition cap. Next try: separate the receiver cadence from the loss decision without touching the recovery
   timer, and score on fresh flights drawn after the change is fixed.
2. **A reference the spoofer does not control.** In SITL EKF2 a velocity consistent drift is invisible against the
   vehicle's own EKF2. Evaluate on logs with optical flow, visual odometry or wheel odometry, and with the receiver
   velocity excluded from the reference. The corpus holds 7 flights with an independent source; more are needed.
3. **Detection without an independent reference.** `spoof_drift_noref` is detected in 53% of simulated runs, the window
   baseline in 87%. Not attempted in v1.5.0 (no time left after the false alarm work).
4. **Latency on slow drift.** The window test is faster on every drift case; not attempted in v1.5.0.
5. **Hardware or hardware in the loop.** SITL with a patched simulated GPS is the strongest flight controller evidence;
   a bench receiver fed with logged data, or an authorised test range, is the next step.

## Later

- Live validation on a flight controller or a range with an authorised test source, replacing the pymavlink loopback.
- Authentication scopes and rate limits on the API beyond the single shared key.
- A second independent reference type (barometer plus airspeed, wheel odometry) evaluated on its own.
- Real interference data for the map, from a source that permits redistribution.

## Not planned

Anything that generates or transmits RF, and any command path to a vehicle. Marsad stays advisory.
