"""Marsad MCP server: position-trust tools for AI agents and decision platforms.

Advisory and read-mostly. Tools score and explain; they never command a vehicle and never touch
anything outside this process's in-memory store (shared with the REST service when run in-process).

Run:  python -m marsad.mcp_server            (stdio)
      python -m marsad.mcp_server --http     (streamable HTTP, default 127.0.0.1:8765/mcp)
"""
from __future__ import annotations

import argparse
import functools
from typing import Any, Optional

from pydantic import ValidationError

from .api import texts
from .api.models import MAX_BATCH, PRESETS, SampleIn, TrackReportIn
from .api.state import Store, StoreError, get_store, explain_report

try:                                    # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:                     # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

try:
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:                     # mcp 1.x
    from mcp.server.fastmcp.exceptions import ToolError

try:
    from mcp_types import ToolAnnotations as _TA
except ImportError:                     # pragma: no cover
    try:
        from mcp.types import ToolAnnotations as _TA
    except ImportError:
        _TA = None

INSTRUCTIONS = (
    "Marsad answers one question: can this position be believed? Vehicle tools assess GNSS trust from a "
    "window of timestamped samples (GNSS fix + optional independent velocity reference). Track tools score "
    "reported tracks for physical plausibility and cross-source agreement. Every result carries `evidence` "
    "(machine-readable reasons) and `explanation` (plain language). Marsad is advisory: it recommends, never "
    "commands. Results labelled simulated=true come from the measurement-level simulator, not hardware. "
    "Read marsad://docs/limits before relying on a verdict. " + texts.INDEPENDENCE
)


def build_server(store: Optional[Store] = None) -> Any:
    """Create the MCP server bound to ``store`` (default: the process-wide shared store)."""
    st = store or get_store()
    mcp = _Server("marsad", instructions=INSTRUCTIONS)

    def ann(read_only: bool):
        return _TA(readOnlyHint=read_only, destructiveHint=False, idempotentHint=False,
                   openWorldHint=False) if _TA else None

    def tool(read_only: bool = True, **kw):
        a = ann(read_only)
        return mcp.tool(annotations=a, **kw) if a is not None else mcp.tool(**kw)

    def wrap(fn):
        """Turn store/validation errors into plain-text tool errors an agent can act on."""
        @functools.wraps(fn)
        def inner(*a, **k):
            try:
                return fn(*a, **k)
            except StoreError as e:
                raise ToolError(e.message)
            except ValidationError as e:
                msgs = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:6])
                raise ToolError(f"invalid input: {msgs}")
        return inner

    # ------------------------------------------------------------------ vehicle tools
    @tool(True)
    @wrap
    def assess_vehicle_window(samples: list[dict[str, Any]], preset: str = "uav_multirotor") -> dict[str, Any]:
        """Assess GNSS trust over a window of samples. Stateless: nothing is stored.

        Each sample is {"t": seconds, "gnss": {"lat","lon", optional "alt","ve","vn" (m/s),"cn0_mean",
        "cn0_std","n_sats","agc"(0..1),"hdop","fix_type","t_gnss"}, "ref": {"ve","vn" (m/s)} }. `ref` is an
        independent non-GNSS velocity (VIO, optical flow, odometry); without it slow carry-off spoofing may
        go undetected. Samples must be time-ordered; send >= 30 s of data at 1-5 Hz so baselines can form.
        Preset is one of: uav_fixedwing, uav_multirotor, ground_robot, vessel.
        Returns the final state (TRUSTED / DEGRADED / DENIED), trust 0..1, recommended action, every state
        transition in the window, ranked evidence and a plain-language explanation."""
        if len(samples) > MAX_BATCH:
            raise ToolError(f"at most {MAX_BATCH} samples per call (got {len(samples)})")
        parsed = [SampleIn.model_validate(s).to_nav() for s in samples]
        if not parsed:
            raise ToolError("samples must not be empty")
        tmp = Store()
        out = tmp.ingest_samples("window", parsed, preset, publish=False)
        rep = out["report"]
        return {"simulated": False, "n_samples": out["n_samples"], "final": {
                    "state": rep["state"], "trust": rep["trust"], "action": rep["action"],
                    "dominant_hypothesis": rep["dominant"], "warmup": rep["warmup"]},
                "posterior": rep["probs"], "transitions": out["transitions"],
                "recommended_position": rep["nav"], "gnss_offset_from_dead_reckoning_m": rep["gnss_offset_m"],
                "evidence": [e["message"] for e in rep["evidence"]],
                "explanation": explain_report(rep) + (" Window is short; baselines were still warming up."
                                                       if rep["warmup"] else "")}

    @tool(True)
    @wrap
    def get_vehicle_trust(vehicle_id: str) -> dict[str, Any]:
        """Latest trust report for a vehicle held in this server's store (fed by the REST API or a
        simulated scenario). Returns state, trust, recommended action, evidence and explanation."""
        d = st.vehicle_trust(vehicle_id)
        rep = d["report"]
        return {"vehicle_id": vehicle_id, "simulated": d["simulated"], "state": rep["state"],
                "trust": rep["trust"], "action": rep["action"], "t": rep["t"],
                "dominant_hypothesis": rep["dominant"], "posterior": rep["probs"],
                "recommended_position": rep["nav"], "recent_transitions": d["recent_transitions"],
                "evidence": [e["message"] for e in rep["evidence"]], "explanation": d["explanation"]}

    @tool(True)
    @wrap
    def explain_state(vehicle_id: str) -> dict[str, Any]:
        """Explain why a vehicle is in its current trust state and what to do: the transition history,
        the evidence behind each change, what the state means and the recommended action."""
        d = st.vehicle_trust(vehicle_id)
        rep = d["report"]
        h = st.history(vehicle_id, 1)
        meaning = {"TRUSTED": "GNSS agrees with all checks.",
                   "DEGRADED": "Something is off but not conclusive; use GNSS with caution.",
                   "DENIED": "GNSS should not be used; navigate on the independent reference or hold."}[rep["state"]]
        return {"vehicle_id": vehicle_id, "simulated": d["simulated"], "state": rep["state"],
                "state_meaning": meaning, "action": rep["action"],
                "action_detail": texts.ACTION_TEXT.get(rep["action"], ""),
                "transitions": [{k: t[k] for k in ("t", "from", "to", "trust", "dominant", "evidence")}
                                for t in h["transitions"][-10:]],
                "ranking": sorted(rep["probs"].items(), key=lambda kv: -kv[1])[:3],
                "evidence": [e["message"] for e in rep["evidence"]], "explanation": d["explanation"],
                "limits": "Advisory only; see marsad://docs/limits."}

    # ------------------------------------------------------------------ track tools
    def _track_view(d: dict, simulated: bool = False) -> dict:
        msgs = [r["message"] for r in sorted(d.get("reasons", []), key=lambda r: -r.get("weight", 0))]
        if d["state"] == "TRUSTED":
            ex = f"Track {d['track_id']} looks plausible (trust {d['trust']:.2f})."
        else:
            ex = (f"Track {d['track_id']} is {d['state']} (trust {d['trust']:.2f}): "
                  + ("; ".join(msgs[:3]) if msgs else "no specific reason recorded") + ".")
        return {**d, "evidence": msgs, "explanation": ex + (" (SIMULATED.)" if simulated else "")}

    @tool(False)
    @wrap
    def score_track(report: dict[str, Any]) -> dict[str, Any]:
        """Score one track report and update the stored track. Stateful per track_id: the score uses that
        track's history, so send reports in time order. Report: {"track_id","source","t","lat","lon",
        optional "speed" (m/s),"course" (deg),"cls" (vessel|aircraft|ground|unknown),"accuracy_m","ident"}.
        Returns trust 0..1, state (TRUSTED / SUSPECT / DISTRUSTED), reasons, evidence and explanation."""
        v = TrackReportIn.model_validate(report)
        out = st.ingest_tracks([v.model_dump()], origin="mcp", publish=False)
        return _track_view(out["tracks"][0])

    @tool(False)
    @wrap
    def score_tracks(reports: list[dict[str, Any]]) -> dict[str, Any]:
        """Score a batch of track reports (same fields as score_track), time-ordered. Returns the latest
        score per touched track, most distrusted first, with a summary."""
        if not reports or len(reports) > MAX_BATCH:
            raise ToolError(f"send between 1 and {MAX_BATCH} reports")
        vs = [TrackReportIn.model_validate(r).model_dump() for r in reports]
        out = st.ingest_tracks(vs, origin="mcp", publish=False)
        rows = sorted((_track_view(t) for t in out["tracks"]), key=lambda r: r["trust"])
        bad = [r for r in rows if r["state"] != "TRUSTED"]
        return {"n_reports": len(vs), "n_tracks": len(rows), "n_not_trusted": len(bad), "tracks": rows,
                "evidence": [m for r in bad[:5] for m in r["evidence"][:1]],
                "explanation": f"{len(bad)} of {len(rows)} tracks are not TRUSTED."
                               + (f" Most distrusted: {bad[0]['track_id']} ({bad[0]['trust']:.2f})." if bad else "")}

    @tool(True)
    @wrap
    def list_distrusted_tracks(min_trust: float = 0.5) -> dict[str, Any]:
        """List stored tracks whose trust is BELOW `min_trust` (default 0.5), most distrusted first, each
        with its reasons. Use after score_track(s) or when a REST/demo feed is populating the store."""
        if not 0.0 <= min_trust <= 1.0:
            raise ToolError("min_trust must be between 0 and 1")
        rows = [_track_view(r, st.track_origin == "demo") for r in st.list_tracks(max_trust=min_trust)
                if r["trust"] < min_trust]
        return {"threshold": min_trust, "count": len(rows), "tracks": rows,
                "simulated": st.track_origin == "demo",
                "evidence": [m for r in rows[:5] for m in r["evidence"][:1]],
                "explanation": f"{len(rows)} track(s) have trust below {min_trust}."
                               + (" Data in the store is from a SIMULATED demo." if st.track_origin == "demo" else "")}

    @tool(True)
    @wrap
    def source_health() -> dict[str, Any]:
        """Health of each track source (feed): a source whose tracks are repeatedly implausible or that
        disagrees with others may be compromised or faulty. Does not attribute intent."""
        h = st.source_health()
        flagged = [k for k, v in h.items() if isinstance(v, dict) and (
            v.get("compromised") or v.get("flagged") or str(v.get("state", "")).upper() in ("SUSPECT", "DISTRUSTED", "COMPROMISED"))]
        return {"sources": h, "flagged": flagged, "simulated": st.track_origin == "demo",
                "evidence": [f"source {k} flagged" for k in flagged],
                "explanation": (f"{len(flagged)} of {len(h)} sources flagged: {', '.join(flagged)}." if flagged
                                else f"{len(h)} source(s) known; none flagged.")}

    @tool(True)
    @wrap
    def interference_map(bbox: Optional[list[float]] = None) -> dict[str, Any]:
        """Time-decayed hex-cell map of interference events reported to this server (from vehicles that
        left TRUSTED and anomalous tracks). Optional bbox = [min_lon, min_lat, max_lon, max_lat].
        An empty map means no events were reported, NOT that there is no interference."""
        bb = None
        if bbox is not None:
            if len(bbox) != 4 or bbox[0] > bbox[2] or bbox[1] > bbox[3]:
                raise ToolError("bbox must be [min_lon, min_lat, max_lon, max_lat]")
            bb = tuple(bbox)
        gj = st.interference(bb)
        cells = []
        for f in gj.get("features", []):
            try:
                ring = f["geometry"]["coordinates"][0]
                lon = sum(p[0] for p in ring) / len(ring)
                lat = sum(p[1] for p in ring) / len(ring)
            except Exception:
                lat = lon = None
            cells.append({"center_lat": lat, "center_lon": lon, **(f.get("properties") or {})})
        return {"n_cells": len(cells), "cells": cells[:200], "simulated": gj.get("simulated", False),
                "evidence": [f"{len(cells)} active cell(s)"],
                "explanation": ("No interference events reported to this server (or all have decayed)." if not cells
                                else f"{len(cells)} cell(s) with recent reported events; see confidence per cell.")
                               + " Advisory routing hint only; built from reported events, not from RF measurements."}

    # ------------------------------------------------------------------ scenarios
    @tool(True)
    @wrap
    def list_scenarios() -> dict[str, Any]:
        """List the SIMULATED scenarios available to run_simulated_scenario, with a description of each."""
        s = st.scenarios()
        return {**s, "evidence": [], "explanation": "All scenarios are SIMULATED, measurement-level. "
                "Split 'dev' is for tuning; 'heldout' has disjoint, harsher parameter ranges."}

    @tool(False)
    @wrap
    def run_simulated_scenario(kind: str, seed: int = 1, split: str = "dev") -> dict[str, Any]:
        """Run one SIMULATED measurement-level scenario (not hardware, not real data) through the trust
        engine and return a timeline summary: state transitions, detection latency and how far raw GNSS
        and Marsad's advised position were from the simulated ground truth. The run is stored as vehicle
        `sim-<kind>-<seed>-<split>` so get_vehicle_trust / explain_state can follow up. Use list_scenarios
        for valid kinds; split is 'dev' or 'heldout'."""
        if not 0 <= seed <= 2**31 - 1:
            raise ToolError("seed must be between 0 and 2147483647")
        return st.run_scenario_sync(kind, seed, split)

    # ------------------------------------------------------------------ resources
    @mcp.resource("marsad://docs/trust-states", name="trust-states", mime_type="text/markdown",
                  description="What TRUSTED / DEGRADED / DENIED mean and the recommended action for each.")
    def _trust_states() -> str:
        return texts.TRUST_STATES_DOC

    @mcp.resource("marsad://docs/limits", name="limits", mime_type="text/markdown",
                  description="What Marsad cannot do. Read before relying on a verdict.")
    def _limits() -> str:
        return texts.LIMITS_DOC

    return mcp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m marsad.mcp_server", description="Marsad MCP server")
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    server = build_server()
    if not a.http:
        server.run("stdio")
        return 0
    try:
        server.run("streamable-http", host=a.host, port=a.port)
    except TypeError:                   # mcp 1.x configures host/port via settings
        server.settings.host, server.settings.port = a.host, a.port
        server.run("streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
