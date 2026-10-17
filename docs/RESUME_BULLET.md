# Resume entry

**Marsad, open source GNSS jamming and spoofing trust engine for UAVs and robots (Python, PX4, MAVLink, ROS 2).**

* Built a position trust engine that detected stealth carry off spoofing in 100% of 30 held out runs versus 0% for an autopilot style gate [SIMULATED], and raised zero alarms over 1,245 s of two public PX4 flights [REAL LOG].
* Preregistered a test on real PX4 SIH logs: jumps of 50 to 1000 m caught 4/4 on the first attacked fix, but drifts of 0.5 to 2 m/s caught only after median latencies of 98.1 to 204.6 s and slower drifts missed [SIH + INJECTED]; traced the gap to an evidence weighting defect at mixed sensor rates.

## Sources for every number

| number | file |
|---|---|
| 100% vs 0%, 30 runs, stealth carry off | `docs/results/heldout.md`, row `spoof_drift_stealth` |
| zero alarms, 911 s + 334 s = 1,245 s | `docs/results/real_logs.txt` |
| jumps 4/4 at 0.0 s | `docs/results/sih_inject.txt`, `docs/results/sih_inject_long.txt` |
| 98.1 to 204.6 s, drifts of 0.1 and 0.25 m/s at 0/4 | `docs/results/sih_inject_long.txt` |
| mixed sensor rates (0.008 s vs 0.124 s median gaps) | `docs/results/sih_diagnose.txt`, `docs/results/sih_diagnose_long.txt` |

Note on wording: the SIH + INJECTED drift results are weak (long latencies, large offsets at alarm), so the second
line states them as a limitation found and diagnosed, not as a detection success.
