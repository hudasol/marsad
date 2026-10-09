"""MCP server tests through the SDK's in-memory client. Scenario data is SIMULATED."""
import asyncio
import json
from dataclasses import asdict

import pytest

pytest.importorskip("mcp")
from marsad.api.state import Store  # noqa: E402
from marsad.mcp_server import build_server  # noqa: E402
from marsad.sim import generate  # noqa: E402

try:
    import marsad.tracks  # noqa: F401
    HAVE_TRACKS = True
except Exception:  # pragma: no cover
    HAVE_TRACKS = False
needs_tracks = pytest.mark.skipif(not HAVE_TRACKS, reason="marsad.tracks not importable")

EXPECTED_TOOLS = {"assess_vehicle_window", "get_vehicle_trust", "score_track", "score_tracks",
                  "list_distrusted_tracks", "source_health", "interference_map", "run_simulated_scenario",
                  "explain_state", "list_scenarios"}


def run(coro_fn, store=None):
    """Run coro_fn(call, client) against a fresh in-memory server. call(name, args) -> (is_error, payload)."""
    server = build_server(store or Store())

    async def main():
        try:
            from mcp import Client
        except ImportError:      # mcp 1.x
            from mcp.shared.memory import create_connected_server_and_client_session as mk
            async with mk(server._mcp_server) as session:
                return await coro_fn(_caller(session), session)
        async with Client(server) as client:
            return await coro_fn(_caller(client), client)
    return asyncio.run(main())


def _caller(c):
    async def call(name, args=None):
        r = await c.call_tool(name, args or {})
        err = getattr(r, "is_error", None)
        if err is None:
            err = r.isError
        sc = getattr(r, "structured_content", None) or getattr(r, "structuredContent", None)
        text = r.content[0].text if r.content else ""
        return err, (sc if sc is not None else text)
    return call


def samples_json(kind, seed=1, duration=300.0):
    run_ = generate(kind, seed, "dev", duration=duration, cadence=1.0)
    out = []
    for s in run_.samples:
        d = {"t": s.t}
        if s.gnss is not None:
            d["gnss"] = {k: v for k, v in asdict(s.gnss).items() if v is not None}
        if s.ref is not None:
            d["ref"] = {k: v for k, v in asdict(s.ref).items() if v is not None}
        out.append(d)
    return out


def test_tools_and_resources_listed():
    async def go(call, c):
        tools = await c.list_tools()
        names = {t.name for t in tools.tools}
        res = await c.list_resources()
        return names, {str(r.uri) for r in res.resources}, tools
    names, uris, tools = run(go)
    assert names == EXPECTED_TOOLS
    assert {"marsad://docs/trust-states", "marsad://docs/limits"} <= uris
    for t in tools.tools:
        assert t.description and len(t.description) > 40, f"{t.name} needs a real description"


def test_resources_content():
    async def go(call, c):
        a = await c.read_resource("marsad://docs/trust-states")
        b = await c.read_resource("marsad://docs/limits")
        return a.contents[0].text, b.contents[0].text
    a, b = run(go)
    assert all(w in a for w in ("TRUSTED", "DEGRADED", "DENIED", "Recommended action"))
    assert "SIMULATED" in b and "not affiliated" in b and "cannot" in b.lower()


def test_assess_window_detects_jamming_and_explains():
    smp = samples_json("jam_hard")

    async def go(call, c):
        return await call("assess_vehicle_window", {"samples": smp, "preset": "uav_multirotor"})
    err, out = run(go)
    assert not err
    assert out["final"]["state"] in ("TRUSTED", "DEGRADED", "DENIED")
    assert any(t["to"] == "DENIED" for t in out["transitions"]), "jamming window should reach DENIED"
    assert isinstance(out["evidence"], list) and isinstance(out["explanation"], str) and out["explanation"]
    assert out["simulated"] is False and out["n_samples"] == len(smp)


def test_assess_window_is_stateless():
    store = Store()
    smp = samples_json("nominal", duration=120.0)

    async def go(call, c):
        await call("assess_vehicle_window", {"samples": smp})
        return await call("get_vehicle_trust", {"vehicle_id": "window"})
    err, out = run(go, store)
    assert err and "unknown vehicle" in out
    assert not store.vehicles


def test_assess_window_validation_errors_are_readable():
    async def go(call, c):
        return [await call("assess_vehicle_window", {"samples": [{"t": 1, "gnss": {"lat": 95, "lon": 0}}]}),
                await call("assess_vehicle_window", {"samples": []}),
                await call("assess_vehicle_window", {"samples": [{"t": 1}], "preset": "warp_drive"}),
                await call("assess_vehicle_window", {"samples": [{"t": 2}, {"t": 1}]})]
    r = run(go)
    assert all(e for e, _ in r)
    assert "lat" in r[0][1] and "preset" in r[2][1] and "non-decreasing" in r[3][1]


def test_run_scenario_then_follow_up_tools():
    async def go(call, c):
        e1, summary = await call("run_simulated_scenario", {"kind": "jam_hard", "seed": 1})
        vid = summary["vehicle_id"]
        e2, trust = await call("get_vehicle_trust", {"vehicle_id": vid})
        e3, expl = await call("explain_state", {"vehicle_id": vid})
        return (e1, summary), (e2, trust), (e3, expl)
    (e1, s), (e2, t), (e3, x) = run(go)
    assert not (e1 or e2 or e3)
    assert s["simulated"] is True and "SIMULATED" in s["notice"] and "SIMULATED" in s["explanation"]
    assert s["scenario"]["is_attack"] and s["detection"]["detected"]
    assert s["detection"]["latency_to_denied_s"] is not None
    assert s["ground_truth_errors_m"]["max_marsad_nav_error_during_event"] is not None
    assert t["simulated"] is True and t["evidence"] is not None and t["explanation"]
    assert x["state_meaning"] and x["action_detail"] and x["transitions"] and "limits" in x


def test_run_scenario_errors_and_nominal():
    async def go(call, c):
        bad = await call("run_simulated_scenario", {"kind": "does_not_exist"})
        badsplit = await call("run_simulated_scenario", {"kind": "nominal", "split": "x"})
        nom = await call("run_simulated_scenario", {"kind": "nominal", "seed": 2})
        return bad, badsplit, nom
    bad, badsplit, (e, nom) = run(go)
    assert bad[0] and "unknown scenario" in bad[1] and badsplit[0]
    assert not e and nom["final"]["state"] == "TRUSTED"
    assert nom["seconds_not_trusted_in_non_attack_scenario"] == 0


def test_list_scenarios():
    async def go(call, c):
        return await call("list_scenarios")
    err, out = run(go)
    kinds = {s["kind"] for s in out["scenarios"]}
    assert not err and {"spoof_drift", "jam_hard", "benign_obstruction"} <= kinds
    assert out["simulated"] is True and out["explanation"]


def test_unknown_vehicle_tools_error():
    async def go(call, c):
        return [await call("get_vehicle_trust", {"vehicle_id": "x"}), await call("explain_state", {"vehicle_id": "x"})]
    assert all(e for e, _ in run(go))


@needs_tracks
def test_track_tools():
    reports = [
        {"track_id": "A", "source": "s1", "t": 0.0, "lat": 24.5, "lon": 54.4, "speed": 5.0, "course": 90.0, "cls": "vessel"},
        {"track_id": "A", "source": "s1", "t": 60.0, "lat": 24.5, "lon": 54.4027, "speed": 5.0, "course": 90.0, "cls": "vessel"},
        {"track_id": "B", "source": "s1", "t": 0.0, "lat": 24.6, "lon": 54.4, "speed": 5.0, "course": 90.0, "cls": "vessel"},
        {"track_id": "B", "source": "s1", "t": 10.0, "lat": 25.6, "lon": 55.4, "speed": 5.0, "course": 90.0, "cls": "vessel"},
    ]

    async def go(call, c):
        one = await call("score_track", {"report": reports[0]})
        many = await call("score_tracks", {"reports": reports[1:]})
        bad = await call("list_distrusted_tracks", {"min_trust": 0.5})
        none = await call("list_distrusted_tracks", {"min_trust": 0.0})
        src = await call("source_health")
        bbox = await call("interference_map", {"bbox": [0, 0, 1, 1]})
        bbox_bad = await call("interference_map", {"bbox": [1, 2, 3]})
        bad_in = await call("score_track", {"report": {"track_id": "x", "source": "s", "t": 0, "lat": 99, "lon": 0}})
        return one, many, bad, none, src, bbox, bbox_bad, bad_in
    one, many, bad, none, src, bbox, bbox_bad, bad_in = run(go)
    assert not one[0] and one[1]["explanation"] and "trust" in one[1] and "evidence" in one[1]
    assert not many[0] and many[1]["tracks"][0]["track_id"] == "B" and many[1]["n_not_trusted"] >= 1
    assert many[1]["tracks"][0]["evidence"], "a distrusted track must come with evidence"
    assert [t["track_id"] for t in bad[1]["tracks"]][:1] == ["B"] and "explanation" in bad[1]
    assert none[1]["count"] == 0
    assert "sources" in src[1] and src[1]["explanation"]
    assert bbox[1]["n_cells"] == 0 and bbox[1]["evidence"] and "explanation" in bbox[1]
    assert bbox_bad[0] and bad_in[0] and "lat" in bad_in[1]


def test_tools_share_state_with_api_store():
    """MCP and REST can run in one process on the same store."""
    from fastapi.testclient import TestClient
    from marsad.api import create_app
    store = Store()
    with TestClient(create_app(store=store)) as c:
        async def go(call, cl):
            return await call("run_simulated_scenario", {"kind": "nominal", "seed": 3})
        err, out = run(go, store)
        assert not err
        v = c.get("/v1/vehicles").json()["vehicles"]
        assert v and v[0]["simulated"] is True


def test_no_tool_writes_outside_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def go(call, c):
        await call("run_simulated_scenario", {"kind": "spoof_drift"})
        await call("list_scenarios")
        return True
    assert run(go)
    assert list(tmp_path.iterdir()) == []


def test_server_name_and_independence_in_instructions():
    s = build_server(Store())
    assert s.name == "marsad"
    ins = getattr(s, "instructions", None) or ""
    assert "not affiliated" in ins and "advisory" in ins.lower()
