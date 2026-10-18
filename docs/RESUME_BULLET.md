# Resume entry

**Marsad, open source GNSS jamming and spoofing trust engine for UAVs and robots (Python, PX4, MAVLink, ROS 2).**

* Built a position trust engine that detected stealth carry off spoofing in 100% of 30 held out runs versus 0% for an autopilot style gate [SIMULATED] and raised zero alarms over 1,245 s of two public PX4 flights [REAL LOG].
* Preregistered tests on PX4 SIH logs: jumps of 50 to 1000 m detected 4/4 on the first attacked fix; drifts of 0.5 m/s and faster detected in 15.7 to 48.3 s at 18.8 to 22.4 m median offset, while 0.25 m/s and slower were not reliably detected [SIH + INJECTED]; not yet tested against real spoofing signals or real receiver behaviour.

## Sources for every number

| number | label | file |
|---|---|---|
| 100% vs 0%, 30 held out runs, stealth carry off | SIMULATED | `docs/results/weighting_fix/heldout.md`, row `spoof_drift_stealth` (identical to `docs/results/heldout.md`) |
| zero alarms, 911 s + 334 s = 1,245 s | REAL LOG | `docs/results/weighting_fix/real_logs.txt` |
| jumps 4/4 at 0.0 s | SIH + INJECTED | `docs/results/weighting_fix/sih_inject.txt`, `docs/results/weighting_fix/sih_inject_long.txt` |
| 15.7 to 48.3 s, 18.8 to 22.4 m, drifts of 0.5 to 2 m/s, 230 s window | SIH + INJECTED | `docs/results/weighting_fix/sih_inject_long.txt` |
| 0.25 m/s velocity consistent 0/4, 0.1 m/s 0/4 ("not reliably detected") | SIH + INJECTED | `docs/results/weighting_fix/sih_inject_long.txt`; cause in `docs/KNOWN_LIMITS.md` |

Notes on wording:

* All numbers are from the v1.3.0 engine (after the evidence weighting fix). No throughput figure is quoted because
  the bullet does not name the hardware.
* "Drifts of 0.5 m/s and faster" refers to the 230 s window of `sitl2.ulg`. In the 32 s window of `sitl1.ulg` only
  1 and 2 m/s were detected (15.7 to 27.8 s), because 0.5 m/s needs longer than 32 s.
* The median offsets across both logs are 18.8 to 22.8 m; the bullet quotes the 230 s window only.
* "Not reliably detected" covers 0.25 m/s with honest GNSS velocity detected 4/4 (113.6 s) but 0/4 when the spoofer
  also shifts the velocity, and 0.1 m/s missed in both modes.
