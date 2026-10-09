# MCP server

`marsad.mcp_server` exposes Marsad to AI agents and decision platforms over the
[Model Context Protocol](https://modelcontextprotocol.io). It is advisory and read-mostly: tools score and
explain, and nothing they do reaches outside this process's in-memory store. Every result carries
`evidence` (machine-readable reasons) and `explanation` (plain language).

> Marsad is an independent open-source project, not affiliated with or endorsed by TII, ATRC or any
> ATRC entity. Results labelled `simulated: true` come from the measurement-level simulator, not hardware.

## Run

```bash
pip install -e ".[mcp]"
python -m marsad.mcp_server                       # stdio (default)
python -m marsad.mcp_server --http --port 8765    # streamable HTTP at http://127.0.0.1:8765/mcp
```

Tested with the official Python SDK, 2.x (`MCPServer`); 1.x (`FastMCP`) is supported by import fallback.

## Client configuration

Claude Desktop (`claude_desktop_config.json`); use the full path to the Python that has Marsad installed:

```json
{
  "mcpServers": {
    "marsad": {
      "command": "/path/to/marsad/.venv/bin/python",
      "args": ["-m", "marsad.mcp_server"]
    }
  }
}
```

On Windows: `"command": "C:\\path\\to\\marsad\\.venv\\Scripts\\python.exe"`.

Generic stdio client (any MCP host):

```json
{ "name": "marsad", "transport": "stdio", "command": "python", "args": ["-m", "marsad.mcp_server"] }
```

Generic HTTP client:

```json
{ "name": "marsad", "transport": "streamable-http", "url": "http://127.0.0.1:8765/mcp" }
```

The HTTP transport has no authentication of its own: bind it to localhost or put it behind a gateway.

## Tools

| Tool | What it does | Writes to store |
|---|---|---|
| `assess_vehicle_window(samples, preset)` | Runs a fresh engine over a window of samples. Returns final state, trust, action, posterior, every transition, ranked evidence, explanation. Stateless. | no |
| `get_vehicle_trust(vehicle_id)` | Latest report for a vehicle in the store (fed by REST or a simulated scenario). | no |
| `explain_state(vehicle_id)` | Why the vehicle is in its state: meaning, action detail, transition history with evidence, top hypotheses. | no |
| `score_track(report)` | Scores one track report and updates that track (stateful per `track_id`). | yes (track) |
| `score_tracks(reports)` | Same for a batch; returns the latest score per track, most distrusted first. | yes (tracks) |
| `list_distrusted_tracks(min_trust=0.5)` | Stored tracks with trust below the threshold, with reasons. | no |
| `source_health()` | Per-source health and flagged sources. No attribution of intent. | no |
| `interference_map(bbox=None)` | Time-decayed hex cells of reported events, optional `[min_lon, min_lat, max_lon, max_lat]`. | no |
| `list_scenarios()` | The SIMULATED scenario kinds. | no |
| `run_simulated_scenario(kind, seed=1, split="dev")` | Runs one SIMULATED scenario; returns a timeline summary and stores it as vehicle `sim-<kind>-<seed>-<split>`. | yes (vehicle) |

`samples` use the same shape as the REST API (see [API.md](API.md)): `{"t", "gnss": {...}, "ref": {"ve","vn"}}`.
Send at least ~30 s of data so baselines form, and include the independent `ref` velocity if you have one.
Bad input returns a tool error with a readable message (for example `invalid input: lat: Input should be
less than or equal to 90`), and a rejected call changes nothing.

## Resources

| URI | Content |
|---|---|
| `marsad://docs/trust-states` | what TRUSTED, DEGRADED and DENIED mean and the recommended action for each |
| `marsad://docs/limits` | what Marsad cannot do; read before relying on a verdict |

## Example exchange

An agent checks a simulated jamming scenario (SIMULATED data).

```
agent -> list_scenarios()
tool  <- {"simulated": true, "scenarios": [{"kind": "jam_hard", "is_attack": true, ...}, ...]}

agent -> run_simulated_scenario({"kind": "jam_hard", "seed": 1})
tool  <- {"simulated": true, "vehicle_id": "sim-jam_hard-1-dev",
          "scenario": {"kind": "jam_hard", "label": "jamming", "event_start": 198.7, "event_end": 259.3},
          "detection": {"detected": true, "latency_to_non_trusted_s": 2.1, "latency_to_denied_s": 2.3},
          "ground_truth_errors_m": {"max_raw_gnss_error_before_alarm": 2.9,
                                    "max_marsad_nav_error_during_event": 3.8},
          "transitions": [
            {"t": 200.8, "from": "TRUSTED", "to": "DEGRADED", "dominant": "jamming",
             "summary": "DEGRADED: most likely jamming-like signal loss. AGC +0.22 above baseline. Action: FALLBACK_REFERENCE."},
            {"t": 201.0, "from": "DEGRADED", "to": "DENIED", "dominant": "jamming", "...": "..."}],
          "explanation": "SIMULATED scenario. State TRUSTED, trust 0.97. ..."}

agent -> explain_state({"vehicle_id": "sim-jam_hard-1-dev"})
tool  <- {"state": "TRUSTED", "state_meaning": "GNSS agrees with all checks.",
          "transitions": [... the DEGRADED and DENIED episodes with their evidence ...],
          "limits": "Advisory only; see marsad://docs/limits."}
```

Scenario numbers are properties of the simulator and of this seed; they are not field results.

## Tests

`tests/test_mcp.py` drives the server through the SDK's in-memory client: tool listing, resources,
stateless assessment, scenario follow-up, validation errors, track tools, shared store with the REST app,
and a check that no tool writes to disk.
