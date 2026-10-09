# REST and SSE API

Marsad ships a small FastAPI service (`marsad.api`). It is in-memory, advisory, and meant for local or
trusted-network use. It also serves the [dashboard](DASHBOARD.md) at `/`.

> **Independence notice.** Marsad is an independent open-source project. It is not affiliated with,
> endorsed by, or sponsored by the Technology Innovation Institute (TII), the Advanced Technology
> Research Council (ATRC), or any of their entities. The same notice is returned by `GET /v1/version`.
>
> **Simulation.** Everything produced by `/v1/demo/*` is SIMULATED, measurement-level data and is flagged
> `simulated: true`. Nothing here has been validated on hardware or real flight logs.

## Run

```bash
pip install -e ".[api]"
python -m marsad.api                       # http://127.0.0.1:8000  (dashboard at /, OpenAPI at /docs)
python -m marsad.api --host 0.0.0.0 --port 8080
```

Embed it:

```python
from marsad.api import create_app
app = create_app()                         # or create_app(api_key="...", cors_origins=["http://localhost:3000"])
```

| Setting | How | Default |
|---|---|---|
| API key | env `MARSAD_API_KEY` (or `create_app(api_key=...)`) | unset: open (fine for localhost only) |
| CORS | env `MARSAD_CORS_ORIGINS` (comma separated) or `create_app(cors_origins=[...])` | off |
| Batch cap | env `MARSAD_MAX_BATCH` | 2000 samples or reports per request |
| Body cap | env `MARSAD_MAX_BODY_BYTES` | 8 MiB |
| History per vehicle | env `MARSAD_HISTORY` | 6000 points |
| Capacity | env `MARSAD_MAX_VEHICLES`, `MARSAD_MAX_TRACKS` | 200, 5000 (HTTP 429 beyond) |

With a key set, send `X-API-Key: <key>` or `Authorization: Bearer <key>` on every `/v1` call except
`/v1/health` and `/v1/version`. `EventSource` cannot set headers, so `/v1/stream` also accepts
`?api_key=`; the dashboard reads the key from the URL fragment (`/#key=...`). The key is compared in
constant time. This is a simple shared secret, not a security audit: put a real gateway in front of
anything exposed beyond a trusted network.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /v1/health` | liveness, counts |
| `GET /v1/version` | version, API version, independence and simulation notices, capabilities |
| `POST /v1/vehicles/{vid}/samples` | feed a time-ordered batch; returns latest TrustReport and state transitions |
| `GET /v1/vehicles` | list vehicles with latest state |
| `GET /v1/vehicles/{vid}/trust` | latest report, plain-language explanation, recent transitions |
| `GET /v1/vehicles/{vid}/history?n=600` | last `n` compact points (state, trust, posterior, raw/nav position) and all transitions |
| `POST /v1/vehicles/{vid}/acknowledge` | operator override (`engine.acknowledge()`); body optional `{operator, note}` |
| `DELETE /v1/vehicles/{vid}` | forget a vehicle |
| `POST /v1/tracks/reports` | feed a batch of track reports |
| `GET /v1/tracks?state=&max_trust=&limit=` | tracks, most distrusted first |
| `GET /v1/tracks/{id}` | one track with its reasons |
| `GET /v1/sources` | per-source health (flags a source that looks compromised or faulty; no attribution of intent) |
| `GET /v1/map/interference?bbox=minlon,minlat,maxlon,maxlat` | GeoJSON hex cells, time-decayed |
| `GET /v1/stream` | Server-Sent Events (below) |
| `POST /v1/demo/start` | start a SIMULATED scenario: `{kind, seed, split: dev\|heldout, speed: 0.5..100}` |
| `POST /v1/demo/stop`, `GET /v1/demo/status` | stop / inspect the demo |
| `GET /v1/demo/scenarios` | available simulated scenarios with descriptions |

Vehicle ids match `[A-Za-z0-9_.-]{1,64}`. Failures return `{"detail": ...}` with 401, 404, 409, 413, 422,
429 or 501 (the track modules could not be imported; vehicle endpoints keep working).

### Samples

Field names match `marsad.types.GnssFix` and `RefMotion`. `gnss.t` and `ref.t` default to the sample `t`.

```json
{"preset": "uav_multirotor",
 "samples": [
  {"t": 100.0,
   "gnss": {"lat": 24.4539, "lon": 54.3773, "alt": 50, "ve": 8.1, "vn": 2.0,
            "cn0_mean": 42.1, "cn0_std": 3.0, "n_sats": 12, "agc": 0.31, "hdop": 0.9,
            "fix_type": 3, "t_gnss": 97.2},
   "ref": {"ve": 8.0, "vn": 2.1, "sigma": 0.15, "source": "vio"}}]}
```

* `preset` (`uav_multirotor`, `uav_fixedwing`, `ground_robot`, `vessel`) applies when the vehicle is
  created; a different preset for an existing vehicle returns 409 (delete it first).
* Times must be non-decreasing, across batches too (422 otherwise). A rejected batch changes nothing.
* NaN/Inf, `lat` outside [-90, 90], `lon` outside [-180, 180], unknown fields and oversized batches are rejected (422).
* The independent `ref` velocity matters: without it Marsad cannot catch slow carry-off spoofing.

```bash
curl -s -X POST localhost:8000/v1/vehicles/uav1/samples -H 'content-type: application/json' -d @window.json
curl -s localhost:8000/v1/vehicles/uav1/trust
curl -s 'localhost:8000/v1/vehicles/uav1/history?n=100'
curl -s -X POST localhost:8000/v1/vehicles/uav1/acknowledge -H 'content-type: application/json' \
     -d '{"operator":"alice","note":"visual fix confirmed"}'
```

Response of `POST .../samples`:

```json
{"vehicle_id": "uav1", "simulated": false, "n_samples": 500,
 "report": {"t": 299.0, "state": "DENIED", "trust": 0.14, "action": "FALLBACK_REFERENCE",
            "dominant": "jamming", "probs": {"nominal": 0.01, "jamming": 0.93, "...": 0},
            "evidence": [{"detector": "signal", "kind": "agc_rise", "message": "AGC +0.24 above baseline", "weight": 2.1}],
            "nav": {"e": 120.4, "n": -33.0, "lat": 24.4536, "lon": 54.3784},
            "summary": "DENIED: most likely jamming-like signal loss. ...", "explanation": "..."},
 "transitions": [{"t": 201.0, "from": "DEGRADED", "to": "DENIED", "trust": 0.14, "evidence": ["..."]}]}
```

`nav` is the position Marsad recommends navigating on (GNSS when trusted, the dead-reckoned
continuation of the last trusted track when it is not).

### Tracks

```bash
curl -s -X POST localhost:8000/v1/tracks/reports -H 'content-type: application/json' -d '{
 "reports": [{"track_id":"T1","source":"ais-like","t":0,"lat":24.5,"lon":54.4,"speed":5,"course":90,"cls":"vessel"}]}'
curl -s 'localhost:8000/v1/tracks?max_trust=0.5'
curl -s localhost:8000/v1/sources
curl -s localhost:8000/v1/map/interference
```

Report fields: `track_id`, `source`, `t`, `lat`, `lon`, optional `speed` (m/s), `course` (deg 0..360),
`cls` (`vessel|aircraft|ground|unknown`), `accuracy_m`, `ident`. Track state is `TRUSTED`, `SUSPECT` or
`DISTRUSTED`, each with `reasons[{kind, message, weight}]`. Vehicles that leave `TRUSTED` and anomalous
tracks feed the interference map, throttled; the map reflects only events reported to this process.
Time `t` is whatever clock you use; keep one epoch per process, because map decay is relative to the
latest `t` seen.

### Server-Sent Events: `GET /v1/stream`

The stream starts with `retry: 2000`, then `hello` and `scene`, then live events. A keep-alive comment is
sent every 15 s. `?max_events=N` closes after N events (used by tests).

| Event | Payload |
|---|---|
| `hello` | version info, notices, vehicle list, demo status |
| `scene` | `{tracks, sources, map (GeoJSON), simulated, available}`, at most once per second |
| `vehicle` | `{vehicle_id, simulated, origin, points[], report, n_samples}`; `points` are compact per-sample records (decimated to 300 per event) |
| `transition` | one state change with evidence |
| `acknowledge` | operator override |
| `vehicle_deleted` | `{vehicle_id}` |
| `demo` | demo status (kind, seed, split, speed, sim_t, duration, event window) |

```bash
curl -N localhost:8000/v1/stream
```

### Demo mode (SIMULATED)

```bash
curl -s localhost:8000/v1/demo/scenarios
curl -s -X POST localhost:8000/v1/demo/start -H 'content-type: application/json' \
     -d '{"kind":"spoof_drift","seed":1,"split":"dev","speed":20}'
curl -s -X POST localhost:8000/v1/demo/stop
```

The demo replays a measurement-level scenario (from `marsad.sim`) at `speed` simulated seconds per second
into the vehicle `demo`, together with a simulated track scene from `make_demo_stream`. Starting a demo
**resets the track engine, the interference map and the `demo` vehicle**. History points of the `demo`
vehicle carry a `truth` position (simulated ground truth, in the same local frame as `raw` and `nav`).
Ground truth is never included for any other vehicle, and the `demo` id rejects externally posted
samples (409). The simulator has no RF, waveform or SDR code; it cannot interfere with a real receiver.

## Using the store from MCP in the same process

`marsad.api.state.get_store()` returns the process-wide store used by `create_app()`'s default; the MCP
server (`marsad.mcp_server.build_server()`) uses the same one, so a program that runs both in one process
shares vehicles, tracks and the map. Separate `python -m` processes do not share state.
