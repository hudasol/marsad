"""Static explanatory text shared by the REST docs, the MCP resources and the dashboard."""

INDEPENDENCE = ("Marsad is an independent open-source project. It is not affiliated with, endorsed by, "
                "or sponsored by the Technology Innovation Institute (TII), the Advanced Technology "
                "Research Council (ATRC), or any of their entities.")

SIM_NOTICE = ("Everything produced by the simulator is SIMULATED, measurement-level data. It does not "
              "come from hardware and has not been validated against real receivers or real flights.")

ACTION_TEXT = {
    "USE_GNSS": "Use GNSS normally.",
    "USE_GNSS_WITH_CAUTION": "Use GNSS with inflated covariance / reduced weight; prefer an alternative navigation source if one is available.",
    "FALLBACK_REFERENCE": "Do not navigate on GNSS. Navigate on the independent reference (dead reckoning, VIO, optical flow, odometry) from the last trusted position.",
    "HOLD_AND_ALERT": "No usable fallback. Stop trusting GNSS, hold or return per mission policy, and alert the operator.",
}

HYPOTHESIS_TEXT = {
    "nominal": "nothing anomalous",
    "environmental_degradation": "environmental degradation (obstruction / multipath), degraded but not malicious",
    "jamming": "jamming-like signal loss (C/N0 falls, AGC rises, fixes are lost)",
    "spoofing_jump": "position-takeover spoofing (abrupt displacement)",
    "spoofing_drift": "gradual carry-off spoofing (slow drift away from the independent reference)",
    "replay_meaconing": "replay / meaconing (delayed re-broadcast of genuine signals)",
    "spoofing_unclassified": "spoofing-like signal anomaly (kind undetermined, e.g. no independent reference)",
    "none": "an unexplained anomaly",
}

TRUST_STATES_DOC = """# Marsad trust states

Marsad reports one of three states for a vehicle's GNSS position, together with a trust score
(probability the position can be believed, 0..1), a recommended action and human-readable evidence.

## TRUSTED
GNSS agrees with every check (signal quality, kinematics, independent reference, time).
Recommended action: USE_GNSS. Use GNSS normally.

## DEGRADED
Something is off, but the evidence does not (yet) justify abandoning GNSS: for example partial
obstruction, multipath, or early or weak signs of spoofing. Trust is capped below 0.5.
Recommended action: USE_GNSS_WITH_CAUTION (inflate covariance, reduce weight, prefer alternative
navigation where available), or FALLBACK_REFERENCE when a verified reference track exists.

## DENIED
GNSS should not be used: jamming-like loss, a spoofing hypothesis above threshold, or a lost fix.
Trust is capped at 0.14. Recommended action: FALLBACK_REFERENCE (navigate on dead reckoning / VIO /
odometry from the last trusted position) or HOLD_AND_ALERT when no reference is available.
The state does not return to TRUSTED until GNSS is verified against the dead-reckoned continuation
and dwell times have elapsed; if the reference has drifted too far for that to be possible, Marsad
says so (re-acquisition unverifiable) and stays below TRUSTED. An operator can acknowledge.

Marsad is advisory. It never commands a vehicle.
"""

LIMITS_DOC = """# What Marsad cannot do

- It is not a GNSS receiver or RF analyser. It consumes receiver-reported and vehicle-reported
  measurements (position, velocity, C/N0, AGC, clock) and cannot see the RF environment.
- It is not a replacement for authenticated GNSS (OSNMA, M-code) or controlled-reception antennas.
- It needs an independent motion reference (VIO, optical flow, odometry, INS) to catch slow carry-off
  spoofing that stays under per-sample gates. Without one, such an attack may go undetected.
  A reference that itself drifts sets a detectability floor.
- Its evaluation so far is on SIMULATED, measurement-level scenarios written by the same author as the
  detectors. It has not been validated on hardware or on real flight logs. Treat scores as advisory.
- It does not attribute interference to any actor and cannot say who is responsible.
- Track trust scores the physical plausibility and cross-source agreement of reported positions; a
  plausible but false track cannot be detected by plausibility alone.
- The interference map is built only from events fed to this process and decays over time. An empty
  cell means "no events reported", not "no interference".
- The service keeps state in memory only and is not a production-hardened system (no persistence,
  simple optional API key, no security audit).
- Marsad is an independent project, not affiliated with or endorsed by TII, ATRC or any ATRC entity.
"""

SCENARIO_INFO = {
    "nominal": "Honest GNSS, no event. Should stay TRUSTED.",
    "benign_obstruction": "Honest degradation: partial sky obstruction (fewer satellites, lower C/N0). Hard negative, should not be called an attack.",
    "benign_multipath": "Honest degradation: multipath spikes. Hard negative.",
    "jam_hard": "Jamming-like: C/N0 collapses, AGC rises, fixes are lost, then recover.",
    "jam_soft": "Partial jamming-like degradation: noisy positions and intermittent fixes.",
    "spoof_jump": "Spoofed position abruptly displaced and held.",
    "spoof_jump_transient": "Spoofed displacement that later ends.",
    "spoof_drift": "Gradual carry-off: position slowly drifts away; velocity may look consistent.",
    "spoof_drift_stealth": "Carry-off at the same signal power as honest GNSS, velocity consistent. Hardest case.",
    "replay": "Delayed re-broadcast (meaconing) of genuine signals.",
    "spoof_drift_noref": "Carry-off with NO independent reference available. Expected to be hard or undetectable.",
    "spoof_drift_ref_outage": "Carry-off during an outage of the independent reference.",
}
