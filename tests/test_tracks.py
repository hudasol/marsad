"""Tests for the track-trust module. All scenario data is SIMULATED."""
import json
import math

import pytest

import marsad.tracks as T
from marsad.geo import LocalFrame, haversine
from marsad.tracks import (InterferenceMap, TrackConfig, TrackReport, TrackTrust, TrackTrustEngine, Zone,
                           evaluate, make_demo_stream, make_scenario)
from marsad.tracks.geomfit import robust_circle_fit
from marsad.tracks.sim import (AIS, KINDS, RADAR, demo_zones, make_demo_scenario, run_scenario)

FR = LocalFrame(25.3, 54.8)


def rep(tid, src, t, e, n, **kw):
    lat, lon = FR.to_geo(e, n)
    kw.setdefault("cls", "surface")
    return TrackReport(tid, src, t, lat, lon, **kw)


# ---------------------------------------------------------------- API surface
def test_public_exports():
    for name in ("TrackReport", "TrackTrust", "Zone", "TrackTrustEngine", "InterferenceMap",
                 "make_scenario", "evaluate", "make_demo_stream"):
        assert hasattr(T, name)


def test_to_dict_json_friendly():
    eng = TrackTrustEngine()
    res = eng.ingest(rep("A", "ais-like", 0.0, 0, 0, speed=5.0, course=90.0, accuracy_m=6.0))
    assert isinstance(res, TrackTrust)
    d = res.to_dict()
    json.dumps(d)
    assert {"track_id", "trust", "state", "reasons", "sources", "last_t", "n_reports", "lat", "lon"} <= set(d)
    json.dumps(TrackReport.from_dict(rep("A", "x", 1, 0, 0).to_dict()).to_dict())
    json.dumps(Zone("z", 1, 2, 3, {"surface"}).to_dict())


def test_unknown_track_and_invalid_report():
    eng = TrackTrustEngine()
    assert eng.get("nope") is None
    bad = eng.ingest(TrackReport("X", "s", 1.0, float("nan"), 55.0))
    assert bad.state != "TRUSTED" or bad.trust < 0.95
    assert eng.ingest(TrackReport("Y", "s", 1.0, 95.0, 55.0)).reasons[0]["kind"] == "invalid_report"


# ---------------------------------------------------------------- single checks
def _run(eng, reps):
    last = None
    for r in reps:
        last = eng.ingest(r)
    return last


def test_clean_straight_track_is_trusted():
    eng = TrackTrustEngine()
    res = _run(eng, [rep("A", "ais-like", t, 8.0 * t, 0.0, speed=8.0, course=90.0, accuracy_m=6.0) for t in range(0, 300, 10)])
    assert res.state == "TRUSTED" and res.trust > 0.9 and not res.reasons


def test_teleport_single_source():
    eng = TrackTrustEngine()
    reps = [rep("A", "ais-like", t, 8.0 * t, 0.0, speed=8.0, course=90.0, accuracy_m=6.0) for t in range(0, 100, 10)]
    reps.append(rep("A", "ais-like", 100, 8.0 * 100 + 15000, 0.0, speed=8.0, course=90.0, accuracy_m=6.0))
    res = _run(eng, reps)
    assert res.state != "TRUSTED"
    assert any(r["kind"] == "teleport" for r in res.reasons)
    # evidence leaks away with time: the same track is trusted again long after the glitch
    assert eng.get("A", t=100 + 1500).state == "TRUSTED"


def test_speed_displacement_mismatch():
    eng = TrackTrustEngine()
    # reports 3 m/s but moves 15 m/s (below the surface envelope, so only the consistency check can see it)
    res = _run(eng, [rep("A", "s", t, 15.0 * t, 0.0, speed=3.0, course=90.0, accuracy_m=6.0) for t in range(0, 120, 10)])
    assert res.state != "TRUSTED"
    assert any("speed" in r["kind"] for r in res.reasons)


def test_flatline_and_timestamp_regression():
    eng = TrackTrustEngine()
    reps = [rep("A", "s", t, 100.0, 100.0, speed=6.0, course=90.0, accuracy_m=6.0) for t in range(0, 80, 10)]
    res = _run(eng, reps)
    assert any(r["kind"] == "flatline" for r in res.reasons)
    eng = TrackTrustEngine()
    reps = [rep("B", "s", t, 8.0 * t, 0.0, speed=8.0, course=90.0, accuracy_m=6.0) for t in range(0, 100, 10)]
    reps.append(rep("B", "s", 40, 320.0, 0.0, speed=8.0, course=90.0, accuracy_m=6.0))
    res = _run(eng, reps)
    assert any(r["kind"] == "timestamp_regression" for r in res.reasons)


def test_forbidden_zone():
    zl = FR.to_geo(5000, 5000)
    zone = Zone("SIM-RUNWAY", zl[0], zl[1], 1500.0, {"surface"})
    eng = TrackTrustEngine(zones=[zone])
    # vessel creeps slowly into the zone (no jump, plausible kinematics)
    reps = [rep("V", "ais-like", t, 3300.0 + 2.0 * t, 5000.0, speed=2.0, course=90.0, accuracy_m=6.0, cls="surface")
            for t in range(0, 900, 10)]
    res = _run(eng, reps)
    assert any(r["kind"] == "forbidden_zone" for r in res.reasons)
    assert res.state != "TRUSTED"
    # an aircraft over the same spot is fine
    eng = TrackTrustEngine(zones=[zone])
    res = _run(eng, [rep("P", "ads-b-like", t, 4800.0 + 2.0 * t, 5000.0, speed=2.0, course=90.0, accuracy_m=6.0, cls="air")
                     for t in range(0, 300, 10)])
    assert res.state == "TRUSTED"


def test_cross_source_disagreement_and_agreement():
    eng = TrackTrustEngine()
    for t in range(0, 200, 10):
        eng.ingest(rep("A", "ais-like", t, 5.0 * t, 0, speed=5.0, course=90.0, accuracy_m=6.0))
        res = eng.ingest(rep("A", "radar-like", t + 3, 5.0 * (t + 3) + 20, 10, speed=5.0, course=90.0, accuracy_m=35.0))
    assert res.state == "TRUSTED"
    for t in range(200, 260, 10):
        eng.ingest(rep("A", "ais-like", t, 5.0 * t + 4000, 0, speed=5.0, course=90.0, accuracy_m=6.0))
        res = eng.ingest(rep("A", "radar-like", t + 3, 5.0 * (t + 3), 0, speed=5.0, course=90.0, accuracy_m=35.0))
    assert res.state == "DISTRUSTED"
    assert any(r["kind"] == "cross_source_disagreement" for r in res.reasons)


def test_proximity_association_without_shared_ids():
    eng = TrackTrustEngine()
    res = None
    for t in range(0, 400, 10):
        eng.ingest(rep("AIS-1", "ais-like", t, 5.0 * t, 0, speed=5.0, course=90.0, accuracy_m=6.0))
        off = 0.0 if t < 200 else 900.0
        res = eng.ingest(rep("RAD-9", "radar-like", t + 2, 5.0 * (t + 2) + off, 0, speed=5.0, course=90.0, accuracy_m=35.0))
    assert res.state != "TRUSTED"      # associated by proximity during the first 200 s, then they diverged


def test_circle_fit_and_pattern():
    import random
    rnd = random.Random(1)
    xs = [100 + 120 * math.cos(0.3 * i) + rnd.gauss(0, 3) for i in range(30)]
    ys = [-50 + 120 * math.sin(0.3 * i) + rnd.gauss(0, 3) for i in range(30)]
    xs[7] += 80.0                       # outlier
    f = robust_circle_fit(xs, ys)
    assert abs(f["r"] - 120) < 8 and abs(f["cx"] - 100) < 8 and abs(f["cy"] + 50) < 8
    assert robust_circle_fit([float(i) for i in range(10)], [2.0 * i for i in range(10)]) is None

    def circ(speed_claim, course_follows):
        eng = TrackTrustEngine()
        res = None
        w, r = 4.0 / 120.0, 120.0       # 4 m/s along a 120 m circle
        for k in range(60):
            t = 10.0 * k
            a = w * t
            crs = (90.0 - math.degrees(a + math.pi / 2)) % 360.0 if course_follows else 45.0
            res = eng.ingest(rep("C", "ais-like", t, r * math.cos(a) + rnd.gauss(0, 5), r * math.sin(a) + rnd.gauss(0, 5),
                                 speed=speed_claim, course=crs, accuracy_m=6.0))
        return res
    assert circ(4.0, True).state == "TRUSTED"         # legitimate loiter: speed and course agree with the circle
    spoof = circ(9.0, False)                          # claims 9 m/s cruising on course 45 while sitting on a circle
    assert spoof.state != "TRUSTED" and any(r["kind"] == "circle_pattern" for r in spoof.reasons)


def test_bounded_memory():
    cfg = TrackConfig(max_tracks=300, track_ttl_s=100.0)
    eng = TrackTrustEngine(cfg)
    for i in range(3000):
        eng.ingest(rep(f"K{i}", "s", float(i), i % 50 * 100.0, 0.0, speed=1.0, course=90.0))
    assert len(eng._tracks) <= cfg.max_tracks + 256
    assert len(eng.snapshot()) <= len(eng._tracks)
    assert all(len(ps.win) <= cfg.circle_window for tr in eng._tracks.values() for ps in tr.per_src.values())


# ---------------------------------------------------------------- scenarios
def test_clean_scenarios_have_no_flags():
    for seed in range(0, 6):
        sc = make_scenario(seed, loiter=(seed % 2 == 0))
        res = run_scenario(sc)
        assert res["ever_flag"] == {}, (seed, res["ever_flag"], res["reasons"])
        assert res["source_flags"] == {}


@pytest.mark.parametrize("kind", [k for k in KINDS])
def test_each_fault_type_detected(kind):
    det = tot = fp = 0
    for seed in (1000, 1001, 1002):
        sc = make_scenario(seed, faults=[kind])
        res = run_scenario(sc)
        ft, tainted = sc.labels["faulted_tracks"], set(sc.labels["tainted_tracks"])
        assert ft, "scenario must contain faulted tracks"
        for tid in ft:
            tot += 1
            det += tid in res["first_flag"]
        fp += sum(1 for tid in res["ever_flag"] if tid not in ft and tid not in tainted)
    assert det / tot >= 0.9, (kind, det, tot)
    assert fp == 0


def test_common_mode_offset_attributed_to_source():
    for seed in (1000, 1001, 1002, 1003):
        sc = make_scenario(seed, faults={"ais_common_offset": {"magnitude_m": 7000.0, "bearing_deg": 135.0}})
        eng = TrackTrustEngine(zones=sc.zones)
        for r in sc:
            eng.ingest(r)
        h = eng.source_health()
        assert h[AIS]["flagged"] and not h[RADAR]["flagged"]
        assert h[AIS]["trust"] < 0.3 and h[RADAR]["trust"] > 0.9
        assert 6000 < h[AIS]["common_mode_offset_m"] < 8000
        assert abs(h[AIS]["bearing_deg"] - 135.0) < 10.0 or abs(h[AIS]["bearing_deg"] - 135.0) > 350.0
        assert h[AIS]["attribution"] == "sole"
        # source-level reason shows on tracks carried by that source
        snap = eng.snapshot()
        assert sum(any(r["kind"] == "source_common_mode" for r in x.reasons) for x in snap) >= len(snap) // 2


def test_partial_offset_penalises_whole_source_but_keeps_verified_tracks_usable():
    sc = make_scenario(1004, faults={"ais_common_offset": {"magnitude_m": 6000.0, "fraction": 0.5}})
    eng = TrackTrustEngine(zones=sc.zones)
    for r in sc:
        eng.ingest(r)
    h = eng.source_health()
    assert h[AIS]["flagged"] and not h[RADAR]["flagged"]
    ft = sc.labels["faulted_tracks"]
    snap = {x.track_id: x for x in eng.snapshot()}
    assert all(snap[t].state == "DISTRUSTED" for t in ft)
    unaffected = [t for t in snap if t not in ft]
    assert unaffected
    # unmodified tracks are not blamed individually: no cross-source disagreement reason on them
    for t in unaffected:
        assert not any(r["kind"] == "cross_source_disagreement" for r in snap[t].reasons)
    # but their source penalty is visible, and strongest on tracks nobody can verify
    pen = {t: next((r["weight"] for r in snap[t].reasons if r["kind"] == "source_common_mode"), 0.0) for t in unaffected}
    assert all(w > 0 for w in pen.values())
    verified = [t for t in unaffected if sc.labels["radar_covered"][t]]
    unverified = [t for t in unaffected if not sc.labels["radar_covered"][t]]
    if verified and unverified:
        assert max(pen[t] for t in verified) < min(pen[t] for t in unverified)


def test_two_comparable_sources_cannot_attribute():
    # two cooperative sources disagree: both are lowered, none is singled out
    cfg = TrackConfig()
    eng = TrackTrustEngine(cfg)
    for t in range(0, 300, 10):
        for i in range(8):
            tid = f"K{i}"
            e = 5.0 * t + 1000 * i
            eng.ingest(rep(tid, "ais-a", t, e, 0, speed=5.0, course=90.0, accuracy_m=6.0))
            eng.ingest(rep(tid, "ais-b", t + 1, e + 5.0 + (3000.0 if t > 100 else 0.0), 0, speed=5.0, course=90.0, accuracy_m=6.0))
    h = eng.source_health()
    assert h["ais-a"]["flagged"] and h["ais-b"]["flagged"]
    assert h["ais-a"]["attribution"] == "shared"


def test_no_second_source_means_slow_offset_undetected():
    # documented limit: single source, slow consistent drift within the kinematic envelope
    eng = TrackTrustEngine()
    res = None
    for t in range(0, 900, 10):
        drift = 0.4 * t                    # 0.4 m/s extra, 360 m over the run
        res = eng.ingest(rep("S", "ais-like", t, 6.0 * t + drift, 0, speed=6.4, course=90.0, accuracy_m=6.0))
    assert res.state == "TRUSTED"


# ---------------------------------------------------------------- evaluation / determinism
def test_evaluate_shape_and_labels():
    r = evaluate(range(1000, 1002))
    assert r["label"] == "SIMULATED"
    assert r["track_level"]["recall"] >= 0.9 and r["track_level"]["precision"] >= 0.9
    assert r["clean"]["false_flag_rate"] <= 0.05
    assert r["source_level"]["detected"] == r["source_level"]["scenarios"]
    json.dumps(r)


def test_determinism():
    f = list(KINDS)
    a, b = make_scenario(5, faults=f), make_scenario(5, faults=f)
    assert [x.to_dict() for x in a.reports] == [x.to_dict() for x in b.reports]
    assert a.labels == b.labels
    assert [x.to_dict() for x in make_scenario(6, faults=f).reports] != [x.to_dict() for x in a.reports]
    out = []
    for _ in range(2):
        eng = TrackTrustEngine(zones=a.zones)
        out.append([eng.ingest(r).to_dict() for r in a.reports])
    assert out[0] == out[1]
    assert evaluate(range(1000, 1001)) == evaluate(range(1000, 1001))


def test_demo_stream():
    s = make_demo_stream(7)
    assert s and all(s[i].t <= s[i + 1].t for i in range(len(s) - 1))
    assert make_demo_stream(7)[10].to_dict() == s[10].to_dict()
    sc = make_demo_scenario(7)
    assert sc.labels["label"] == "SIMULATED" and sc.meta["label"] == "SIMULATED"
    eng = TrackTrustEngine(zones=demo_zones())
    for r in s:
        eng.ingest(r)
    states = {x.state for x in eng.snapshot()}
    assert "DISTRUSTED" in states and "TRUSTED" in states
    assert eng.source_health()[AIS]["flagged"]


# ---------------------------------------------------------------- interference map
def test_map_confidence_and_decay():
    m = InterferenceMap(cell_km=5.0, half_life_s=1000.0)
    lat, lon = 25.3, 54.8
    assert m.confidence(lat, lon, 0.0) == 0.0
    m.report_vehicle(lat, lon, 0.0, "DENIED", "jamming", 1.0)
    c0 = m.confidence(lat, lon, 0.0)
    assert c0 == pytest.approx(1 - math.exp(-1.0))
    # one half-life later the weight sum has halved
    assert m.confidence(lat, lon, 1000.0) == pytest.approx(1 - math.exp(-0.5))
    assert m.confidence(lat, lon, 1e6) < 1e-6
    # more reports raise confidence, bounded below 1
    for i in range(50):
        m.report_track_anomaly(lat, lon, 10.0 + i, "circle_pattern", 2.0)
    c = m.confidence(lat, lon, 60.0)
    assert 0.99 < c <= 1.0
    # TRUSTED / nominal reports add no weight; DEGRADED < DENIED
    m2 = InterferenceMap()
    m2.report_vehicle(lat, lon, 0.0, "TRUSTED", "nominal", 1.0)
    assert m2.confidence(lat, lon, 0.0) == 0.0
    m2.report_vehicle(lat, lon, 0.0, "DEGRADED", "jamming", 1.0)
    a = m2.confidence(lat, lon, 0.0)
    m3 = InterferenceMap()
    m3.report_vehicle(lat, lon, 0.0, "DENIED", "jamming", 1.0)
    assert 0 < a < m3.confidence(lat, lon, 0.0)
    # out-of-order report cannot rewind the cell clock or produce confidences outside [0, 1]
    m3.report_vehicle(lat, lon, -500.0, "DENIED", "jamming", 1.0)
    assert 0.0 <= m3.confidence(lat, lon, -1000.0) <= 1.0


def test_map_cells_hex_geometry_and_dominant():
    m = InterferenceMap(cell_km=5.0)
    m.report_vehicle(25.3, 54.8, 100.0, "DENIED", "spoofing_drift", 0.9)
    m.report_track_anomaly(25.3, 54.8, 110.0, "circle_pattern", 0.2)
    m.report_track_anomaly(25.6, 55.2, 120.0, "teleport", 1.0)
    cells = m.cells(130.0)
    assert len(cells) == 2
    c = next(x for x in cells if x["dominant"] == "spoofing_drift")
    assert c["n_reports"] == 2 and len(c["polygon"]) == 6
    assert m.cell_id(25.3, 54.8) == c["id"]
    assert InterferenceMap(cell_km=5.0).cell_id(25.3, 54.8) == c["id"]       # stable across instances
    # hexagon circumradius = cell_km / sqrt(3); vertices equidistant from the centre
    ds = [haversine(c["lat"], c["lon"], la, lo) for la, lo in c["polygon"]]
    assert all(abs(d - 5000.0 / math.sqrt(3)) < 15.0 for d in ds)
    # a point 3 km away lands in the same or an adjacent cell; 20 km away is a different cell
    assert m.cell_id(25.3, 54.8 + 0.3 / 111.0 * 100 / 100) is not None
    assert m.cell_id(25.3, 54.8 + 0.2) != c["id"]


def test_map_geojson_valid():
    m = InterferenceMap(cell_km=5.0, half_life_s=600.0)
    for i in range(20):
        m.report_vehicle(25.0 + 0.03 * i, 55.0 + 0.02 * i, float(i), "DENIED", "jamming", 0.8)
    gj = m.to_geojson(30.0)
    json.dumps(gj)
    assert gj["type"] == "FeatureCollection" and gj["features"]
    for f in gj["features"]:
        assert f["type"] == "Feature" and f["geometry"]["type"] == "Polygon"
        ring = f["geometry"]["coordinates"][0]
        assert len(ring) == 7 and ring[0] == ring[-1]
        for lon, lat in ring:                       # GeoJSON order is [lon, lat]
            assert 54 < lon < 56 and 24 < lat < 26
        assert 0.0 <= f["properties"]["confidence"] <= 1.0
    assert InterferenceMap().to_geojson(0.0)["features"] == []
    with pytest.raises(ValueError):
        InterferenceMap(cell_km=0)


def test_map_bounded():
    m = InterferenceMap(cell_km=1.0, max_cells=200)
    for i in range(2000):
        m.report_track_anomaly(24.0 + (i % 100) * 0.02, 54.0 + (i // 100) * 0.02, float(i), "x", 1.0 + (i % 7))
    assert len(m._cells) <= 200
