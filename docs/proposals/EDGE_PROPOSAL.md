# Marsad: a position trust layer for uncrewed systems in contested GNSS conditions

Proposal seed, version 1.3.0, October 2026. Author: Huda Mueen. Marsad is an independent open source project
(Apache 2.0). It has no affiliation, endorsement or partnership with EDGE Group or any other organisation; this
document describes what a pilot could look like if a partner chose to run one.

## 1. Problem

Public reporting in 2026 describes GNSS interference in Gulf waters at a scale that affects ordinary traffic. After
28 February 2026 the maritime analytics firm Windward reported navigation interference affecting more than 1,100
commercial ships within 24 hours in UAE, Qatari, Omani and Iranian waters, with vessel positions displaced onto land,
airports and a nuclear power plant [1]. Separate reporting describes dozens of clusters of misplaced vessels around
the Strait of Hormuz [3]. The European Union Aviation Safety Agency lists the Middle East among the regions most
affected by jamming and spoofing and recommends verifying position by non GNSS means [2].

For an uncrewed vehicle the dangerous case is not jamming, which the receiver reports, but a position that is wrong
while every receiver health flag looks normal. A slow drift ("carry off") is absorbed by the navigation filter as if
it were real motion. Alternative navigation (visual odometry, optical flow, wheel or Doppler odometry) exists; what
is missing is a component that decides, with stated evidence, when GNSS can no longer be believed.

## 2. What Marsad does

Marsad reads the GNSS fix and an independent motion reference, accumulates evidence for five hypotheses
(environmental degradation, jamming, spoofing by jump, spoofing by drift, replay), and outputs a trust score, a state
(TRUSTED, DEGRADED, DENIED), a recommended navigation mode, a dead reckoned fallback position and a plain language
reason. The core is standard library Python. Adapters exist for PX4 ULog, MAVLink and ROS 2. Output is advisory: the
MAVLink reporter cannot send commands, and a test enforces this.

## 3. Evidence

Every figure below is reproducible with the command listed in [VALIDATION.md](../VALIDATION.md) or
[EVALUATION.md](../EVALUATION.md). Labels: SIMULATED = the repository's own generator; REAL LOG = unmodified flight,
no attack; SIH + INJECTED = PX4 software in the loop log using the SIH simulator, with an offset added to the GNSS
fixes, scored against simulator truth.

| finding | label |
|---|---|
| Jump and replay spoofing detected in 100% of 30 held out runs, median latency 0.1 s; gate baseline also detects them but returns to the spoofed position (median error 430 m vs 8 m on jumps) | SIMULATED |
| Stealth carry off detected in 100% of 30 runs, median 58.3 s; gate baseline 0% | SIMULATED |
| Carry off without a reference sensor: 53% detected | SIMULATED |
| Drift of 0.1 m/s detected in 50 to 56% of runs, 0.05 m/s never | SIMULATED |
| Two public PX4 flights (911 s and 334 s of GPS): zero alarms | REAL LOG |
| Jumps of 50, 200 and 1000 m added to two PX4 SIH logs: detected 4/4 on the first attacked fix | SIH + INJECTED |
| Drifts of 1 and 2 m/s in a 32 s window: 4/4 detected, median 15.7 to 27.8 s (v1.2.0: 0/4); 0.5 m/s and slower: 0/4 | SIH + INJECTED |
| Drifts of 0.5 to 2 m/s in a 230 s window: 4/4 detected, median 15.7 to 48.3 s at median offsets of 18.8 to 22.4 m (v1.2.0: 98.1 to 204.6 s, 77.1 to 186.8 m) | SIH + INJECTED |
| Drift of 0.25 m/s in a 230 s window: detected 4/4 (113.6 s) when the GNSS velocity is honest, 0/4 when the spoofer also shifts velocity; 0.1 m/s: 0/4 | SIH + INJECTED |
| Engine cost 892.3 to 1,263.0 µs per sample on a Windows laptop (v1.3.0 engine; the v1.1.0 engine measured 187.7 µs on one cloud core) | SIMULATED |

The SIH results exposed a defect that simulation hid: when the reference arrives faster than GNSS (about 125 Hz
against 8 Hz in the two PX4 SIH logs), drift evidence was weighted by the wrong time step and accrued at roughly 6% of
its intended rate. It was fixed in v1.3.0 after predictions were committed (PREREGISTRATION_WEIGHTING.md): 27 of 28
predicted SIH rows were hit (SIH + INJECTED), and the two real flights still raise no alarm (REAL LOG). The one miss, a velocity consistent drift
of 0.25 m/s, is explained in KNOWN_LIMITS.md. All rows above use the v1.3.0 engine; the SIMULATED rows are unchanged from v1.1.0 by the fix.

## 4. What it does not claim

It has not run on a flight controller, on a companion computer, or on any real interference data. No real spoofing
signal has been received. The reference used in the SIH tests is simulator truth, which is better than any real
sensor. The simulated results come from a generator written by the same author as the detectors. Marsad does not
generate RF, attribute interference to any actor, or command a vehicle.

## 5. Pilot in three stages

1. **Offline log replay (4 to 6 weeks).** Run Marsad on partner flight logs, including logs with known interference
   and logs from clean flights. Measure false alarm time on clean flights and detection latency against independent
   ground truth (RTK or survey). Exit criterion: zero unexplained DENIED events on clean logs, preregistered
   detection targets met or missed in public.
2. **Advisory companion computer (2 to 3 months).** Marsad on a Raspberry Pi or Jetson class computer reading
   MAVLink from a real flight controller, logging its verdicts alongside the autopilot. No influence on control.
3. **Closed loop in an authorised range.** Only with a licensed operator and range permission: the trust state
   selects the navigation source under a written mission policy, against controlled interference.

## 6. Independent reference sensors needed

Carry off detection depends on a motion reference that GNSS cannot move: visual inertial odometry or optical flow
with a range sensor on aircraft, wheel odometry on ground robots, Doppler velocity logs on boats. Without one,
simulated carry off detection falls to 53%. The pilot must log this sensor with its own quality flag.

## 7. Robotics extension

Presets exist for ground robots and vessels with their own speed, acceleration and reference noise bounds. Ground
robots and uncrewed surface vessels are attractive first targets because wheel odometry and Doppler logs are cheaper
and more stable references than vision over water or desert.

## 8. Risks

* The reference bias estimator can absorb part of a slow, velocity consistent drift (KNOWN_LIMITS.md); stage 1 must
  measure how much on partner logs with a real reference sensor before stage 2.
* Real reference sensors drift, drop out and fail over water and featureless terrain; the bias bound may need to
  widen, which raises the slowest detectable drift.
* Partner logs may lack the topics Marsad needs (raw GNSS, an independent velocity, receiver jamming indicators).
* A spoofer that also corrupts the reference sensor is outside the threat model.

## 9. Asks

* Flight logs with known interference and with clean flights, from the same platform.
* Access to a test platform (a multirotor or ground robot with an independent reference sensor).
* A sponsor or host for stage 3 in an authorised environment.

## Sources (all opened while preparing this document)

1. OCCRP, "More Than 1,100 Ships Hit by Widespread GPS Disruption After Iran Strikes", 5 March 2026.
   https://www.occrp.org/en/news/more-than-1100-ships-hit-by-widespread-gps-disruption-after-iran-strikes
2. EASA, "Global Navigation Satellite System (GNSS) Outages and Alterations" (Safety Information Bulletin 2022-02R4).
   https://www.easa.europa.eu/en/domains/air-operations/global-navigation-satellite-system-outages-and-alterations
3. ZAWYA (TradeArabia, based on BBC reporting), "Iran's GPS jamming turns shipping lanes into minefields, says expert",
   2026. https://www.zawya.com/en/business/transport-and-logistics/irans-gps-jamming-turns-shipping-lanes-into-minefields-says-expert-jlg92c4z
