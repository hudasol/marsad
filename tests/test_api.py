"""REST/SSE service tests (FastAPI TestClient). All simulated data is labelled as such."""
import json
import threading
import time
from dataclasses import asdict

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from marsad.api import create_app  # noqa: E402
from marsad.api.models import MAX_BATCH  # noqa: E402
from marsad.api.state import Store  # noqa: E402
from marsad.sim import generate  # noqa: E402

try:
    import marsad.tracks  # noqa: F401
    HAVE_TRACKS = True
except Exception:  # pragma: no cover
    HAVE_TRACKS = False
needs_tracks = pytest.mark.skipif(not HAVE_TRACKS, reason="marsad.tracks not importable")


def to_json(sample):
    d = {"t": sample.t}
    if sample.gnss is not None:
        d["gnss"] = {k: v for k, v in asdict(sample.gnss).items() if v is not None}
    if sample.ref is not None:
        d["ref"] = {k: v for k, v in asdict(sample.ref).items() if v is not None}
    return d


def sim_samples(kind="jam_hard", seed=1, duration=300.0, cadence=1.0):
    run = generate(kind, seed, "dev", duration=duration, cadence=cadence)
    return run, [to_json(s) for s in run.samples]


@pytest.fixture()
def client():
    with TestClient(create_app(store=Store())) as c:
        yield c


def post_all(c, vid, samples, preset=None, step=500):
    out = None
    for i in range(0, len(samples), step):
        body = {"samples": samples[i:i + step]}
        if preset:
            body["preset"] = preset
        r = c.post(f"/v1/vehicles/{vid}/samples", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
    return out


# ------------------------------------------------------------------ meta
def test_version_has_independence_notice(client):
    v = client.get("/v1/version").json()
    assert v["api"] == "v1" and v["advisory_only"] is True
    assert "not affiliated" in v["independence_notice"] and "TII" in v["independence_notice"]
    assert "SIMULATED" in v["simulation_notice"]


def test_health_and_dashboard(client):
    assert client.get("/v1/health").json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200 and "مرصد" in page.text
    assert "SIMULATED" in page.text
    assert client.get("/app.js").status_code == 200 and client.get("/style.css").status_code == 200


def test_dashboard_is_offline_only():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "marsad" / "dashboard"
    for f in ("index.html", "app.js", "style.css"):
        txt = (root / f).read_text(encoding="utf-8")
        assert "http://" not in txt.replace("http://www.w3.org", "") and "https://" not in txt, f
        assert "@import" not in txt and "cdn" not in txt.lower()


# ------------------------------------------------------------------ vehicles
def test_samples_to_trust_and_transitions(client):
    run, samples = sim_samples("jam_hard")
    out = post_all(client, "uav1", samples, "uav_multirotor")
    assert out["report"]["state"] in ("TRUSTED", "DEGRADED", "DENIED")
    r = client.get("/v1/vehicles/uav1/trust").json()
    assert r["simulated"] is False and "explanation" in r and r["report"]["action"]
    h = client.get("/v1/vehicles/uav1/history?n=50").json()
    assert 0 < len(h["points"]) <= 50 and "truth" not in h["points"][0]
    states = {t["to"] for t in h["transitions"]}
    assert "DENIED" in states, "a jamming scenario must reach DENIED"
    v = client.get("/v1/vehicles").json()["vehicles"]
    assert v[0]["vehicle_id"] == "uav1" and v[0]["n_samples"] == len(samples)


def test_validation_errors(client):
    ok = {"t": 1.0, "gnss": {"lat": 24.0, "lon": 54.0}}
    assert client.post("/v1/vehicles/a/samples", json={"samples": [{"t": 1, "gnss": {"lat": 91, "lon": 0}}]}).status_code == 422
    assert client.post("/v1/vehicles/a/samples", json={"samples": [{"t": 1, "gnss": {"lat": 0, "lon": 181}}]}).status_code == 422
    r = client.post("/v1/vehicles/a/samples", content='{"samples":[{"t":1,"gnss":{"lat":NaN,"lon":0}}]}',
                    headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert client.post("/v1/vehicles/a/samples", json={"samples": []}).status_code == 422
    assert client.post("/v1/vehicles/a/samples", json={"samples": [{"t": i} for i in range(MAX_BATCH + 1)]}).status_code == 422
    assert client.post("/v1/vehicles/a/samples", json={"samples": [{"t": 1, "gnss": {"lat": 0, "lon": 0, "bogus": 1}}]}).status_code == 422
    assert client.post("/v1/vehicles/bad id!/samples", json={"samples": [ok]}).status_code == 422
    assert client.post("/v1/vehicles/a/samples", json={"samples": [ok], "preset": "nope"}).status_code == 422
    assert client.post("/v1/vehicles/a/samples", json={"samples": [ok, {"t": 0.5}]}).status_code == 422
    assert client.get("/v1/vehicles").json()["vehicles"] == []   # failed batches leave no vehicle behind


def test_preset_conflict_and_out_of_order(client):
    s = [{"t": 1.0, "gnss": {"lat": 24.0, "lon": 54.0}}]
    assert client.post("/v1/vehicles/a/samples", json={"samples": s, "preset": "ground_robot"}).status_code == 200
    assert client.post("/v1/vehicles/a/samples", json={"samples": s, "preset": "vessel"}).status_code == 409
    assert client.post("/v1/vehicles/a/samples", json={"samples": [{"t": 0.5}]}).status_code == 422


def test_acknowledge_and_delete(client):
    _, samples = sim_samples("spoof_jump", duration=300.0)
    post_all(client, "v", samples)
    assert client.get("/v1/vehicles/v/trust").json()["report"]["state"] != "TRUSTED"
    a = client.post("/v1/vehicles/v/acknowledge", json={"operator": "tester", "note": "checked"})
    assert a.status_code == 200 and a.json()["kind"] == "operator_acknowledge"
    assert client.post("/v1/vehicles/nope/acknowledge").status_code == 404
    assert client.delete("/v1/vehicles/v").status_code == 200
    assert client.get("/v1/vehicles/v/trust").status_code == 404
    assert client.delete("/v1/vehicles/v").status_code == 404


def test_unknown_vehicle_404(client):
    assert client.get("/v1/vehicles/zzz/history").status_code == 404


# ------------------------------------------------------------------ tracks and map
@needs_tracks
def test_tracks_flow(client):
    reports = [
        {"track_id": "A", "source": "s1", "t": 0.0, "lat": 24.5, "lon": 54.4, "speed": 5.0, "course": 90.0, "cls": "vessel"},
        {"track_id": "A", "source": "s1", "t": 60.0, "lat": 24.5, "lon": 54.4 + 0.0027, "speed": 5.0, "course": 90.0, "cls": "vessel"},
        {"track_id": "B", "source": "s1", "t": 0.0, "lat": 24.6, "lon": 54.4, "speed": 5.0, "course": 90.0, "cls": "vessel"},
        {"track_id": "B", "source": "s1", "t": 10.0, "lat": 25.6, "lon": 55.4, "speed": 5.0, "course": 90.0, "cls": "vessel"},  # teleport
    ]
    r = client.post("/v1/tracks/reports", json={"reports": reports})
    assert r.status_code == 200 and r.json()["n"] == 4
    rows = client.get("/v1/tracks").json()["tracks"]
    assert [t["track_id"] for t in rows][0] == "B" and rows[0]["trust"] < rows[-1]["trust"]
    assert rows[0]["reasons"], "distrust must carry reasons"
    one = client.get("/v1/tracks/B").json()
    assert one["state"] in ("SUSPECT", "DISTRUSTED")
    assert client.get("/v1/tracks/ZZ").status_code == 404
    assert isinstance(client.get("/v1/sources").json()["sources"], dict)
    assert client.get("/v1/tracks?state=distrusted").status_code == 200
    assert client.get("/v1/tracks?state=bogus").status_code == 422
    assert client.post("/v1/tracks/reports", json={"reports": [dict(reports[0], lat=95)]}).status_code == 422
    assert client.post("/v1/tracks/reports", json={"reports": [dict(reports[0], cls="spaceship")]}).status_code == 422


@needs_tracks
def test_map_is_geojson_and_fed_by_vehicle_reports(client):
    gj = client.get("/v1/map/interference").json()
    assert gj["type"] == "FeatureCollection"
    _, samples = sim_samples("jam_hard", duration=300.0)
    post_all(client, "v", samples)
    gj = client.get("/v1/map/interference").json()
    assert len(gj["features"]) >= 1, "a non-TRUSTED vehicle must leave interference cells"
    assert client.get("/v1/map/interference?bbox=0,0,1,1").json()["features"] == []
    assert client.get("/v1/map/interference?bbox=bad").status_code == 422


def test_tracks_unavailable_degrades_to_501(monkeypatch):
    import marsad.api.state as st
    monkeypatch.setattr(st, "tracks_mod", lambda: (_ for _ in ()).throw(st.Unavailable("Track trust")))
    with TestClient(create_app(store=Store())) as c:
        assert c.get("/v1/tracks").status_code == 501
        assert c.get("/v1/sources").status_code == 501
        assert c.post("/v1/tracks/reports", json={"reports": [
            {"track_id": "A", "source": "s", "t": 0, "lat": 1, "lon": 1}]}).status_code == 501
        assert c.get("/v1/health").status_code == 200   # vehicle side keeps working


# ------------------------------------------------------------------ SSE
def _read_events(client, n, path="/v1/stream"):
    events = []
    with client.stream("GET", f"{path}{'&' if '?' in path else '?'}max_events={n}") as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        ev = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((ev, json.loads(line.split(":", 1)[1])))
    return events


def test_sse_first_events(client):
    ev = _read_events(client, 2)
    assert [e[0] for e in ev] == ["hello", "scene"]
    assert "not affiliated" in ev[0][1]["independence_notice"]


def test_sse_streams_vehicle_events_and_transitions(client):
    # Starlette's TestClient buffers the response until the stream ends, hence max_events.
    out = []
    t = threading.Thread(target=lambda: out.extend(_read_events(client, 5)), daemon=True)
    t.start()
    assert _wait(lambda: client.app.state.store.subs, 5), "subscriber never attached"
    _, samples = sim_samples("jam_hard", duration=300.0)
    post_all(client, "v", samples, step=700)
    t.join(10)
    assert not t.is_alive()
    kinds = [e[0] for e in out]
    assert "vehicle" in kinds
    veh = next(d for k, d in out if k == "vehicle")
    assert veh["vehicle_id"] == "v" and veh["points"] and "state" in veh["report"]


# ------------------------------------------------------------------ demo (SIMULATED)
def _wait(pred, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


def test_demo_scenarios_list(client):
    d = client.get("/v1/demo/scenarios").json()
    kinds = {s["kind"] for s in d["scenarios"]}
    assert d["simulated"] is True and {"spoof_drift", "jam_hard", "nominal", "replay"} <= kinds
    assert {"dev", "heldout"} == set(d["splits"])


def test_demo_start_stop_flags_simulated_and_truth(client):
    r = client.post("/v1/demo/start", json={"kind": "jam_hard", "seed": 1, "speed": 100})
    assert r.status_code == 200 and r.json()["simulated"] is True and r.json()["running"] is True
    assert _wait(lambda: client.get("/v1/demo/status").json()["sim_t"] > 5 or client.get("/v1/vehicles").json()["vehicles"])
    assert _wait(lambda: any(v["vehicle_id"] == "demo" and v["n_samples"] > 50 for v in client.get("/v1/vehicles").json()["vehicles"]))
    h = client.get("/v1/vehicles/demo/history?n=20").json()
    assert h["simulated"] is True
    assert any(p.get("truth") for p in h["points"]), "ground truth is included for the simulated demo vehicle"
    assert client.get("/v1/vehicles").json()["vehicles"][0]["simulated"] is True
    s = client.post("/v1/demo/stop").json()
    assert s["running"] is False
    n1 = client.get("/v1/vehicles").json()["vehicles"][0]["n_samples"]
    time.sleep(0.4)
    assert client.get("/v1/vehicles").json()["vehicles"][0]["n_samples"] == n1, "no samples after stop"


def test_demo_vehicle_rejects_real_data_and_bad_input(client):
    assert client.post("/v1/demo/start", json={"kind": "nope"}).status_code == 422
    assert client.post("/v1/demo/start", json={"kind": "nominal", "speed": 1000}).status_code == 422
    assert client.post("/v1/demo/start", json={"kind": "nominal", "split": "x"}).status_code == 422
    client.post("/v1/demo/start", json={"kind": "nominal", "speed": 100})
    assert _wait(lambda: client.get("/v1/vehicles").json()["vehicles"])
    r = client.post("/v1/vehicles/demo/samples", json={"samples": [{"t": 9999.0}]})
    assert r.status_code == 409
    client.post("/v1/demo/stop")


def test_nonsimulated_vehicle_never_carries_truth(client):
    _, samples = sim_samples("nominal", duration=120.0)
    post_all(client, "real", samples)
    h = client.get("/v1/vehicles/real/history").json()
    assert h["simulated"] is False and all("truth" not in p for p in h["points"])
    ev = client.get("/v1/vehicles/real/trust").json()
    assert "truth" not in json.dumps(ev)


# ------------------------------------------------------------------ security knobs
def test_api_key():
    with TestClient(create_app(api_key="s3cret", store=Store())) as c:
        assert c.get("/v1/health").status_code == 200 and c.get("/v1/version").status_code == 200
        assert c.get("/v1/vehicles").status_code == 401
        assert c.get("/v1/vehicles", headers={"X-API-Key": "wrong"}).status_code == 401
        assert c.get("/v1/vehicles", headers={"X-API-Key": "s3cret"}).status_code == 200
        assert c.get("/v1/vehicles", headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert c.get("/v1/stream?max_events=1").status_code == 401
        with c.stream("GET", "/v1/stream?max_events=1&api_key=s3cret") as r:
            assert r.status_code == 200
            list(r.iter_lines())
        assert c.get("/").status_code == 200   # the static dashboard shell stays open


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("MARSAD_API_KEY", "envkey")
    with TestClient(create_app(store=Store())) as c:
        assert c.get("/v1/vehicles").status_code == 401
        assert c.get("/v1/vehicles", headers={"X-API-Key": "envkey"}).status_code == 200


def test_cors_off_by_default_and_opt_in():
    with TestClient(create_app(store=Store())) as c:
        r = c.get("/v1/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in r.headers
    with TestClient(create_app(store=Store(), cors_origins=["http://ok.example"])) as c:
        r = c.get("/v1/health", headers={"Origin": "http://ok.example"})
        assert r.headers.get("access-control-allow-origin") == "http://ok.example"
        r = c.get("/v1/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in r.headers


def test_body_size_cap(monkeypatch):
    import marsad.api.app as appmod
    monkeypatch.setattr(appmod, "MAX_BODY", 200)
    with TestClient(create_app(store=Store())) as c:
        big = {"samples": [{"t": float(i)} for i in range(100)]}
        assert c.post("/v1/vehicles/a/samples", json=big).status_code == 413
