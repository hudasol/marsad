# Technical report section 4 as of v1.4.0 (superseded)

> Superseded by section 4 of [TECHNICAL_REPORT.md](../TECHNICAL_REPORT.md). Kept as the record.

## 4. Failure regimes (reported, not hidden)

* **No independent reference (SIMULATED):** carry-off without a power signature is undetectable; 53% detection (power-signature
  cases only) and no fallback position (`HOLD_AND_ALERT`).
* **Slow carry-off near the reference bias bound:** 0.05 m/s is never detected and 0.1 m/s in 50 to 56% of runs (SIMULATED).
* **Attack at power-up:** no clean baseline.
* **Coordinated attack on the reference sensor.**
* **Replay labelling is late:** at the first alarm a replay carries the coarse spoofing label; `replay_meaconing` is assigned once a delay is confirmed (97% of runs settled, SIMULATED).
* **Where the baseline wins (SIMULATED):** in soft jamming its latency is lower (4.1 s vs 4.6 s), although its navigation error is
  higher (11 m vs 9 m) since v1.3.0.
* **Slow drift on real PX4 SIH logs (SIH + INJECTED):** v1.2.0 diluted drift evidence when the reference (about 125 Hz)
  arrived faster than GNSS (about 8 Hz) and caught drifts of 0.5 to 2 m/s only after median latencies of 98.1 to
  204.6 s. The preregistered fix in v1.3.0 brings this to 15.7 to 48.3 s at median offsets of 18.8 to 22.4 m in a 230 s
  window. Still missed: a velocity consistent drift of 0.25 m/s, because the reference bias estimator absorbs 34.8%
  of it before the drift evidence starts, and any drift of 0.1 m/s (KNOWN_LIMITS.md).

