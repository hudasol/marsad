# Track trust (`marsad.tracks`)

Scores the positional trustworthiness of tracks fused from several sources (cooperative AIS/ADS-B-like reports, radar, EO, own-vehicle reports), with human-readable reasons, so a decision platform does not inherit poisoned positions. Standard library only, deterministic, streaming, bounded memory. Does not attribute interference to any actor.

All numbers below are from **SIMULATED** scenarios (`marsad.tracks.sim`). No real feed data was used.

## API

```python
from marsad.tracks import (TrackReport, TrackTrust, Zone, TrackTrustEngine, TrackConfig,
                           InterferenceMap, make_scenario, evaluate, make_demo_stream)

eng = TrackTrustEngine(config=None, zones=[Zone("airport", lat, lon, 2500.0, {"surface"})])
tt = eng.ingest(TrackReport("T1", "ais-like", t, lat, lon, speed=7.0, course=90.0,
                            cls="surface", accuracy_m=6.0, ident="MMSI123"))
tt.to_dict()   # track_id, trust 0..1, state TRUSTED|SUSPECT|DISTRUSTED, reasons[{kind,message,weight,t}],
               # sources, last_t, n_reports, lat, lon
eng.snapshot(t=None); eng.get("T1"); eng.source_health()
# source_health -> {source: {trust, n_tracks, common_mode_offset_m, flagged[, bearing_deg, attribution]}}
```

`InterferenceMap(cell_km=5.0, half_life_s=1800.0)`: `report_vehicle(lat, lon, t, state, hypothesis, confidence)`, `report_track_anomaly(lat, lon, t, kind, weight)`, `confidence(lat, lon, t)`, `cells(t)`, `to_geojson(t)`. Cells are pointy-top hexagons (axial coordinates, `cell_km` = centre spacing) over an equirectangular projection around a fixed reference (25 N, 55 E by default), so ids are stable. Confidence is `1 - exp(-S)` with `S` the half-life-decayed sum of weights (DENIED/DISTRUSTED = 1.0, DEGRADED/SUSPECT = 0.5, TRUSTED = 0, times the report confidence; environmental degradation counts half).

Simulator: `make_scenario(seed, n_tracks=20, duration=900, faults=None)` returns a `Scenario` (`.reports` in arrival order, `.zones`, `.labels`, `.meta`). Fault kinds: `ais_common_offset, teleport, replay, flatline, circle_spoof, forbidden_zone`. `make_demo_stream(seed)` returns a time-ordered `list[TrackReport]`; the matching zones come from `marsad.tracks.sim.demo_zones()` and labels from `make_demo_scenario(seed)`. `sim.stress()` runs the sensitivity cases below.

## Checks

Each check emits weighted evidence; per track the evidence is accumulated as leaky log-odds of "this position is bad" (tau 150 s of data time, same idea as `marsad.fusion`). `trust = 1 - sigmoid(-3 + L + source_penalty)`. States use hysteresis (TRUSTED at >= 0.7, DISTRUSTED below 0.3).

| Check | Reason kind | What it looks at |
|---|---|---|
| Kinematics | `teleport`, `acceleration` | implied speed / acceleration vs class envelope, noise-aware |
| Self-consistency | `speed_displacement_mismatch`, `course_displacement_mismatch` | displacement vs reported speed (consecutive and 20 s baseline) and course |
| Cross-source | `cross_source_disagreement` | same `track_id` / `ident`, or unique proximity match (single-source tracks after 60 s, gate 1.5 km); z-score of disagreement vs combined claimed accuracy and extrapolation error |
| Replay / freeze | `timestamp_regression`, `stale_timestamp`, `flatline`, `position_replay` | non-monotonic or stale stamps; identical position while reporting speed; two consecutive exact repeats of earlier coordinates |
| Zones | `forbidden_zone` | class inside a zone that forbids it; down-weighted if a second source agrees |
| Circle signature | `circle_pattern` | robust (MAD-trimmed Kasa) circle fit over a sliding window: radius 25-600 m, tight fit, >= 150 deg arc, then circle speed vs reported speed and course vs tangent |
| Source common-mode | `source_common_mode` | see below |

**Source common-mode.** For each source pair the engine keeps the latest per-track offset vector (bounded table). If at least 4 tracks (and >= 20 % of the fresh paired tracks) share a displacement above 500 m that is coherent around its median (dispersion <= max(20 % of the offset, 3 sigma)), the pair is flagged. Attribution: the cooperative side if the other is an independent type (names containing radar/eo/optical/sar/..., or `TrackConfig.source_classes`); otherwise a third source that agrees with one side; otherwise both are lowered with `attribution: "shared"`. A blamed source gets a log-odds penalty of 4.5 on every track it carries (x0.4 for tracks currently verified by another source, scaled down when only a small share of paired tracks show the offset). Individual tracks are therefore not blamed one by one; the reason on each track names the source, the offset and bearing.

## Results (SIMULATED)

Setup: 20 tracks, 900 s, sources `ais-like` (sigma 6 m, 5-10 s) and `radar-like` (sigma 35 m, 6 s, 70 % coverage), 3 faulted tracks per track-fault scenario, common offset 3-15 km applied to all `ais-like` tracks. Per seed: one clean scenario (a legitimate tight loiter track on even seeds) plus one scenario per fault kind (7 total). "Flagged" = SUSPECT or DISTRUSTED. TP = faulted track flagged at/after onset. FP = non-faulted track flagged at any time (unmodified tracks carried by an offset source are excluded as tainted).

Tuned on seeds 0-19, then evaluated on held-out seeds 1000-1019 (run twice, before and after the last robustness edit; identical, and no threshold was changed in response to held-out results):

| | Dev 0-19 | Held-out 1000-1019 |
|---|---|---|
| Track precision / recall | 1.000 / 1.000 (710 TP, 0 FP, 0 FN) | 1.000 / 1.000 (710 TP, 0 FP, 0 FN) |
| Clean-scenario false-flag rate (tracks ever flagged) | 0 / 410 | 0 / 410 |
| Clean tracks flagged inside fault scenarios | 0 / 1750 | 0 / 1750 |
| False source flags in clean scenarios | 0 / 20 | 0 / 20 |
| Compromised source flagged and blamed alone | 20 / 20 (median 6.4 s after onset) | 20 / 20 (median 6.0 s) |

Held-out median detection latency after onset: offset 3.9 s, teleport 3.3 s, forbidden zone 5.3 s, replay 7.9 s, flatline 13.6 s, circle 33.1 s.

**Read these with care.** The simulator and the detectors share an author and the held-out seeds use the same fault parameter ranges, so 100 % here shows the implementation is consistent with its own model, not real-world performance. The dev set was not perfect at first: before debugging it showed 76 false-flag track instances, traced to (a) proximity association matching a track to the wrong radar track before its true partner appeared, (b) chance exact coordinate repeats on a loiter track, (c) radar noise on slow tracks resembling a circle, (d) three tracks pushed onto the same airfield looking like a source offset. Fixes: 60 s minimum single-source age before proximity association, two consecutive repeats required, circle radius >= 5 sigma and tighter fit, >= 4 coherent tracks for a source flag, median-centred coherence test.

### Sensitivity and limits (held-out seeds 1000-1019, 20 scenarios each, SIMULATED)

| Case | Track recall | Source flagged (blamed alone) |
|---|---|---|
| Offset 300 m, all `ais-like` | 0.93 | 0 / 20 (below the 500 m source threshold; tracks caught individually via radar) |
| Offset 800 m / 1500 m | 1.00 / 1.00 | 20 / 20 |
| 6 km offset ramped over 800 s | 1.00 | 20 / 20 |
| 6 km offset on 30 % / 15 % of tracks | 1.00 / 1.00 | 12 / 20 and 0 / 20 (tracks flagged individually, source not) |
| 6 km offset, radar covers 20 % of tracks | 1.00 | 13 / 20 |
| 6 km offset, radar sigma 150 m | 1.00 | 20 / 20 |
| Mixed: all 6 faults (2 tracks each) + 50 % offset | 1.00 (303/303) | 20 / 20 |
| 6 km step offset, **no radar** | 1.00 | 0 / 20; caught only because the step is a teleport at onset |
| 6 km offset **ramped over 800 s, no radar** | **0.69** | 0 / 20 |
| 1.5 km offset **ramped over 800 s, no radar** | **0.03** | 0 / 20 |
| Teleport / replay / circle / zone, no radar | 1.00 each | n/a |
| Clean, radar sigma 150 m; clean, no radar | 0 false flags / 400 each | n/a |

## Known limits

- A single-source track with a plausible, slow, consistent offset and no second source or zone is undetectable (see the no-radar ramp rows). The engine cannot know a position is wrong if it never contradicts physics, another source, or a zone.
- A step offset applied to a single source with no independent source is caught only by the teleport at onset; afterwards the evidence leaks away (tau 150 s) and the track returns to TRUSTED. There is no long-term memory of a jump.
- Source-level flags need >= 4 paired tracks and an independent or third source. With two comparable sources the disagreement is reported as shared, not attributed.
- Source offset below ~500 m is not flagged at source level.
- Circle detection needs the circle radius >= 5x the claimed accuracy and an arc >= 150 deg, so latency is tens of seconds to minutes, and noisy sources (radar sigma 35 m) cannot expose small circles. A legitimate circler whose speed and course disagree with its circle would be flagged.
- Proximity association can merge two distinct nearby vessels (unique-nearest and 2x margin rule, 1.5 km gate); association cannot bridge a displacement larger than the gate, so large offsets need shared `track_id` or `ident`.
- Radar-class `unknown` tracks get the permissive envelope (350 m/s) so teleport checks are weak for them; speed/cross-source checks still apply. Zones apply only to declared classes.
- A track seen by one source and never contradicted starts at trust ~0.95; "TRUSTED" means "no contradiction found", not "verified".
- Accuracy claims are taken at face value (floor 3 m). A source that over-claims accuracy raises false flags; one that under-claims hides disagreement.
- Single-threaded Python; roughly 65 us per report in the simulator setting (about 4,200 reports in 0.27 s on the build machine).
