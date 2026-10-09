"""In-memory, thread-safe state store shared by the REST service and the MCP server.

Nothing here touches the filesystem or network. Vehicles each own a ``TrustEngine``; tracks and the
interference map come from ``marsad.tracks`` (imported lazily so the vehicle side works without it).
"""
from __future__ import annotations

import asyncio
import collections
import json
import math
import os
import threading
import time
from typing import Any, Optional

from .. import TrustEngine, preset as make_preset, __version__
from ..types import NavSample
from . import texts
from .models import PRESETS

API_VERSION = "v1"
HISTORY = int(os.environ.get("MARSAD_HISTORY", "6000"))
MAX_VEHICLES = int(os.environ.get("MARSAD_MAX_VEHICLES", "200"))
MAX_TRACKS = int(os.environ.get("MARSAD_MAX_TRACKS", "5000"))
DEFAULT_PRESET = "uav_multirotor"
DEMO_VEHICLE = "demo"


class StoreError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class Unavailable(StoreError):
    def __init__(self, what: str):
        super().__init__(501, f"{what} is not available in this installation (module import failed)")


def _sanitize(o: Any) -> Any:
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    return o


def dumps(o: Any) -> str:
    try:
        return json.dumps(o, allow_nan=False, default=str, separators=(",", ":"))
    except ValueError:
        return json.dumps(_sanitize(o), default=str, separators=(",", ":"))


def tracks_mod():
    try:
        import marsad.tracks as m
        for n in ("TrackReport", "TrackTrustEngine", "InterferenceMap"):
            if not hasattr(m, n):
                raise ImportError(n)
        return m
    except Exception:
        raise Unavailable("Track trust (marsad.tracks)")


def sim_mod():
    try:
        from .. import sim
        return sim
    except Exception:
        raise Unavailable("The scenario simulator (needs numpy)")


def explain_report(d: dict, simulated: bool = False) -> str:
    """Plain-language explanation of a TrustReport dict for operators and agents."""
    state = d["state"]
    dom = d.get("dominant", "none")
    parts = [f"State {state}, trust {d['trust']:.2f}."]
    if state == "TRUSTED":
        parts.append("GNSS agrees with all checks.")
        if d.get("warmup"):
            parts.append("Baselines are still warming up, so confidence is limited.")
    else:
        parts.append(f"Most likely cause: {texts.HYPOTHESIS_TEXT.get(dom, dom)}.")
        top = [e["message"] for e in d.get("evidence", [])[:3]]
        if top:
            parts.append("Evidence: " + "; ".join(top) + ".")
        if d.get("gnss_offset_m") is not None:
            parts.append(f"GNSS is {d['gnss_offset_m']:.0f} m from the dead-reckoned continuation.")
    parts.append("Recommended action " + d["action"] + ": " + texts.ACTION_TEXT.get(d["action"], ""))
    if simulated:
        parts.append("(SIMULATED data.)")
    return " ".join(parts)


class Subscriber:
    def __init__(self, loop: asyncio.AbstractEventLoop, maxsize: int = 4000):
        self.loop, self.q, self.dropped = loop, asyncio.Queue(maxsize), 0

    def _put(self, item) -> None:
        if self.q.full():
            try:
                self.q.get_nowait()
                self.dropped += 1
            except asyncio.QueueEmpty:
                pass
        self.q.put_nowait(item)


class VehicleRec:
    def __init__(self, vid: str, preset_name: str, simulated: bool):
        self.vid, self.preset, self.simulated = vid, preset_name, simulated
        self.engine = TrustEngine(make_preset(preset_name))
        self.history: collections.deque = collections.deque(maxlen=HISTORY)
        self.transitions: collections.deque = collections.deque(maxlen=300)
        self.last: Optional[dict] = None
        self.last_state: Optional[str] = None
        self.n = 0
        self.last_imap_t = -1e18
        self.meta: dict = {}

    def origin(self):
        f = self.engine.frame
        return {"lat": f.lat0, "lon": f.lon0} if f is not None else None

    def summary(self) -> dict:
        r = self.last or {}
        return {"vehicle_id": self.vid, "preset": self.preset, "simulated": self.simulated,
                "state": r.get("state"), "trust": r.get("trust"), "action": r.get("action"),
                "t": r.get("t"), "n_samples": self.n, "origin": self.origin()}


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.vehicles: dict[str, VehicleRec] = {}
        self.subs: list[Subscriber] = []
        self._ev_id = 0
        self.clock = 0.0
        self._track_engine = None
        self._imap = None
        self._track_ids: set = set()
        self._track_imap_t: dict = {}
        self.track_origin: Optional[str] = None
        self._last_scene = 0.0
        self.demo: dict = {"running": False, "simulated": True}

    # ------------------------------------------------------------- pub/sub
    def subscribe(self, loop) -> Subscriber:
        s = Subscriber(loop)
        with self.lock:
            self.subs.append(s)
        return s

    def unsubscribe(self, s: Subscriber) -> None:
        with self.lock:
            if s in self.subs:
                self.subs.remove(s)

    def publish(self, kind: str, data: dict) -> None:
        with self.lock:
            if not self.subs:
                return
            self._ev_id += 1
            item = (self._ev_id, kind, dumps(data))
            subs = list(self.subs)
        for s in subs:
            try:
                s.loop.call_soon_threadsafe(s._put, item)
            except RuntimeError:
                pass   # loop closed

    # ------------------------------------------------------------- vehicles
    def _new_vehicle(self, vid, preset_name, simulated) -> VehicleRec:
        if len(self.vehicles) >= MAX_VEHICLES:
            raise StoreError(429, f"vehicle capacity reached ({MAX_VEHICLES})")
        rec = VehicleRec(vid, preset_name, simulated)
        self.vehicles[vid] = rec
        return rec

    def _process(self, rec: VehicleRec, s: NavSample, truth) -> tuple[Any, dict, Optional[dict]]:
        rep = rec.engine.update(s)
        fr = rec.engine.frame
        g = s.gnss
        raw = nav = tr = None
        if g is not None and g.fix_type >= 3 and fr is not None:
            e, n = fr.to_local(g.lat, g.lon)
            raw = [round(e, 2), round(n, 2)]
        if rep.nav_e is not None:
            nav = [round(rep.nav_e, 2), round(rep.nav_n, 2)]
        if truth is not None and fr is not None:
            e, n = fr.to_local(*truth)
            tr = [round(e, 2), round(n, 2)]
        pt = {"t": round(s.t, 3), "state": rep.state.value, "trust": round(rep.trust, 4),
              "action": rep.action.value, "dominant": rep.dominant,
              "probs": {k: round(v, 3) for k, v in rep.probs.items()},
              "raw": raw, "nav": nav, "offset": None if rep.gnss_offset_m is None else round(rep.gnss_offset_m, 1)}
        if rec.simulated:
            pt["truth"] = tr
        rec.history.append(pt)
        rec.n += 1
        trans = None
        if rec.last_state is not None and rep.state.value != rec.last_state:
            trans = {"vehicle_id": rec.vid, "t": round(s.t, 3), "from": rec.last_state, "to": rep.state.value,
                     "trust": round(rep.trust, 3), "action": rep.action.value, "dominant": rep.dominant,
                     "summary": rep.summary, "evidence": [e.message for e in rep.evidence[:3]],
                     "simulated": rec.simulated}
            rec.transitions.append(trans)
        rec.last_state = rep.state.value
        self.clock = max(self.clock, s.t)
        # feed the interference map from non-trusted states (throttled)
        if rep.state.value != "TRUSTED" and s.t - rec.last_imap_t >= 2.0:
            lat, lon = rep.nav_lat, rep.nav_lon
            if lat is None and g is not None:
                lat, lon = g.lat, g.lon
            if lat is not None:
                rec.last_imap_t = s.t
                try:
                    self._get_imap().report_vehicle(lat, lon, s.t, rep.state.value, rep.dominant,
                                                    max(0.0, min(1.0, 1.0 - rep.trust)))
                except StoreError:
                    pass
        return rep, pt, trans

    def ingest_samples(self, vid: str, samples: list, preset_name: Optional[str] = None, *,
                       simulated: bool = False, truth: Optional[list] = None, publish: bool = True) -> dict:
        if preset_name is not None and preset_name not in PRESETS:
            raise StoreError(422, f"unknown preset {preset_name!r}; choose from {list(PRESETS)}")
        prev = -math.inf
        for s in samples:       # validate order before any state is created or changed
            if s.t < prev:
                raise StoreError(422, f"sample times must be non-decreasing (got t={s.t} after t={prev})")
            prev = s.t
        with self.lock:
            rec = self.vehicles.get(vid)
            if rec is None:
                rec = self._new_vehicle(vid, preset_name or DEFAULT_PRESET, simulated)
            else:
                if rec.simulated != simulated:
                    raise StoreError(409, f"vehicle {vid!r} is reserved for simulated data" if rec.simulated
                                     else f"vehicle {vid!r} holds real data and cannot take simulated samples")
                if preset_name is not None and preset_name != rec.preset:
                    raise StoreError(409, f"vehicle {vid!r} already exists with preset {rec.preset!r}; "
                                          f"delete it to change the preset")
            tl = rec.engine.t_last
            if tl is not None and samples and samples[0].t < tl:
                raise StoreError(422, f"sample times must be non-decreasing (got t={samples[0].t} after t={tl})")
            pts, trans, rep = [], [], None
            for i, s in enumerate(samples):
                rep, pt, tr = self._process(rec, s, truth[i] if truth else None)
                pts.append(pt)
                if tr:
                    trans.append(tr)
            rec.last = rep.to_dict()
            rec.last["vehicle_id"] = vid
            rec.last["explanation"] = explain_report(rec.last, simulated)
            out = {"vehicle_id": vid, "simulated": simulated, "n_samples": len(samples),
                   "report": rec.last, "transitions": trans}
            ev_pts = pts if len(pts) <= 300 else pts[:: math.ceil(len(pts) / 300)] + [pts[-1]]
            origin = rec.origin()
        if publish:
            self.publish("vehicle", {"vehicle_id": vid, "simulated": simulated, "origin": origin,
                                     "points": ev_pts, "report": rec.last, "n_samples": rec.n})
            for t in trans:
                self.publish("transition", t)
            self.maybe_publish_scene()
        return out

    def get_vehicle(self, vid: str) -> VehicleRec:
        rec = self.vehicles.get(vid)
        if rec is None:
            raise StoreError(404, f"unknown vehicle {vid!r}")
        return rec

    def list_vehicles(self) -> list[dict]:
        with self.lock:
            return [r.summary() for r in self.vehicles.values()]

    def vehicle_trust(self, vid: str) -> dict:
        with self.lock:
            rec = self.get_vehicle(vid)
            if rec.last is None:
                raise StoreError(404, f"vehicle {vid!r} has no samples yet")
            return {"vehicle_id": vid, "simulated": rec.simulated, "preset": rec.preset,
                    "report": rec.last, "explanation": rec.last["explanation"],
                    "recent_transitions": list(rec.transitions)[-5:], "origin": rec.origin()}

    def history(self, vid: str, n: int = 600) -> dict:
        with self.lock:
            rec = self.get_vehicle(vid)
            pts = list(rec.history)[-n:]
            return {"vehicle_id": vid, "simulated": rec.simulated, "origin": rec.origin(),
                    "points": pts, "transitions": list(rec.transitions), "meta": rec.meta}

    def acknowledge(self, vid: str, operator: Optional[str] = None, note: Optional[str] = None) -> dict:
        with self.lock:
            rec = self.get_vehicle(vid)
            rec.engine.acknowledge()
            ev = {"vehicle_id": vid, "t": rec.engine.t_last, "kind": "operator_acknowledge",
                  "operator": operator, "note": note,
                  "message": "Operator acknowledged the current GNSS position; trust state reset to TRUSTED. "
                             "The next sample re-evaluates it."}
            rec.last_state = "TRUSTED"
        self.publish("acknowledge", ev)
        return ev

    def delete_vehicle(self, vid: str) -> None:
        with self.lock:
            self.get_vehicle(vid)
            del self.vehicles[vid]
        self.publish("vehicle_deleted", {"vehicle_id": vid})

    # ------------------------------------------------------------- tracks
    def _get_engine(self):
        m = tracks_mod()
        if self._track_engine is None:
            self._track_engine = m.TrackTrustEngine()
        return self._track_engine

    def _get_imap(self):
        m = tracks_mod()
        if self._imap is None:
            try:
                self._imap = m.InterferenceMap()
            except TypeError:
                self._imap = m.InterferenceMap(cell_km=2.0, half_life_s=900.0)
        return self._imap

    def reset_tracks(self) -> None:
        with self.lock:
            self._track_engine = None
            self._imap = None
            self._track_ids = set()
            self._track_imap_t = {}
            self.track_origin = None

    def ingest_tracks(self, reports: list[dict], origin: str = "api", publish: bool = True) -> dict:
        m = tracks_mod()
        touched: dict = {}
        with self.lock:
            eng = self._get_engine()
            new_ids = {r["track_id"] for r in reports} - self._track_ids
            if len(self._track_ids) + len(new_ids) > MAX_TRACKS:
                raise StoreError(429, f"track capacity reached ({MAX_TRACKS})")
            for r in reports:
                tr = eng.ingest(m.TrackReport(**r))
                touched[r["track_id"]] = tr.to_dict()
                self._track_ids.add(r["track_id"])
                self.clock = max(self.clock, r["t"])
                d = touched[r["track_id"]]
                if d.get("state") != "TRUSTED" and d.get("reasons") \
                        and r["t"] - self._track_imap_t.get(r["track_id"], -1e18) >= 5.0:
                    top = max(d["reasons"], key=lambda x: x.get("weight", 0))
                    self._track_imap_t[r["track_id"]] = r["t"]
                    self._get_imap().report_track_anomaly(d.get("lat", r["lat"]), d.get("lon", r["lon"]),
                                                          r["t"], top.get("kind", "anomaly"), top.get("weight", 0.5))
            if self.track_origin in (None, origin):
                self.track_origin = origin
            else:
                self.track_origin = "mixed"
        out = {"n": len(reports), "tracks": list(touched.values()), "simulated": self.track_origin == "demo"}
        if publish:
            self.maybe_publish_scene()
        return out

    def list_tracks(self, state: Optional[str] = None, max_trust: Optional[float] = None, limit: int = 500) -> list[dict]:
        with self.lock:
            if self._track_engine is None:
                tracks_mod()
                return []
            rows = [t.to_dict() for t in self._track_engine.snapshot()]
        if state:
            rows = [r for r in rows if r["state"] == state.upper()]
        if max_trust is not None:
            rows = [r for r in rows if r["trust"] <= max_trust]
        rows.sort(key=lambda r: r["trust"])
        return rows[:limit]

    def get_track(self, tid: str) -> dict:
        with self.lock:
            if self._track_engine is None:
                raise StoreError(404, f"unknown track {tid!r}")
            t = self._track_engine.get(tid)
            if t is None:
                raise StoreError(404, f"unknown track {tid!r}")
            return t.to_dict()

    def source_health(self) -> dict:
        with self.lock:
            if self._track_engine is None:
                tracks_mod()
                return {}
            return self._track_engine.source_health()

    def interference(self, bbox: Optional[tuple] = None) -> dict:
        """GeoJSON FeatureCollection. bbox = (min_lon, min_lat, max_lon, max_lat)."""
        with self.lock:
            if self._imap is None:
                tracks_mod()
                gj = {"type": "FeatureCollection", "features": []}
            else:
                gj = self._imap.to_geojson(self.clock)
        gj = dict(gj)
        if bbox is not None:
            def inside(f):
                try:
                    ring = f["geometry"]["coordinates"][0]
                    lon = sum(p[0] for p in ring) / len(ring)
                    lat = sum(p[1] for p in ring) / len(ring)
                except Exception:
                    return True
                return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]
            gj["features"] = [f for f in gj.get("features", []) if inside(f)]
        gj["simulated"] = self.track_origin == "demo" or any(v.simulated for v in self.vehicles.values())
        return gj

    def scene(self) -> dict:
        try:
            return {"tracks": self.list_tracks(), "sources": self.source_health(),
                    "map": self.interference(), "simulated": self.track_origin == "demo",
                    "available": True}
        except Unavailable:
            return {"tracks": [], "sources": {}, "map": {"type": "FeatureCollection", "features": []},
                    "simulated": False, "available": False}

    def maybe_publish_scene(self, force: bool = False) -> None:
        now = time.monotonic()
        if not self.subs:
            return
        if not force and now - self._last_scene < 1.0:
            return
        self._last_scene = now
        self.publish("scene", self.scene())

    # ------------------------------------------------------------- misc
    def version_info(self) -> dict:
        try:
            tracks_mod()
            tr = True
        except Unavailable:
            tr = False
        return {"name": "marsad", "version": __version__, "api": API_VERSION,
                "independence_notice": texts.INDEPENDENCE, "simulation_notice": texts.SIM_NOTICE,
                "advisory_only": True, "capabilities": {"vehicle_trust": True, "track_trust": tr,
                                                        "presets": list(PRESETS)}}

    def health(self) -> dict:
        with self.lock:
            return {"status": "ok", "vehicles": len(self.vehicles), "tracks": len(self._track_ids),
                    "subscribers": len(self.subs), "demo_running": bool(self.demo.get("running"))}

    # ------------------------------------------------------------- scenarios
    def scenarios(self) -> dict:
        sim = sim_mod()
        from ..sim.generator import ATTACK_KINDS, TRUTH_CLASS
        return {"simulated": True, "notice": texts.SIM_NOTICE, "splits": list(sim.SPLITS),
                "scenarios": [{"kind": k, "is_attack": k in ATTACK_KINDS,
                               "truth_class": TRUTH_CLASS.get(k), "description": texts.SCENARIO_INFO.get(k, "")}
                              for k in sim.KINDS]}

    def run_scenario_sync(self, kind: str, seed: int = 1, split: str = "dev", vid: Optional[str] = None) -> dict:
        """Run a whole simulated scenario through a fresh engine, store it as a simulated vehicle."""
        sim = sim_mod()
        from ..sim.generator import KINDS, SPLITS
        if kind not in KINDS:
            raise StoreError(422, f"unknown scenario {kind!r}; choose from {KINDS}")
        if split not in SPLITS:
            raise StoreError(422, f"unknown split {split!r}; choose from {list(SPLITS)}")
        run = sim.generate(kind, seed, split)
        vid = vid or f"sim-{kind}-{seed}-{split}"
        with self.lock:
            self.vehicles.pop(vid, None)
        truth = [run.frame.to_geo(float(e), float(n)) for e, n in zip(run.truth_e, run.truth_n)]
        out = None
        for i in range(0, len(run.samples), 500):
            out = self.ingest_samples(vid, run.samples[i:i + 500], simulated=True,
                                      truth=truth[i:i + 500], publish=False)
        rec = self.vehicles[vid]
        rec.meta = {"kind": kind, "seed": seed, "split": split, "attack_start": run.attack_start,
                    "attack_end": run.attack_end, "label": run.truth_class}
        return self.scenario_summary(rec, run, out)

    def scenario_summary(self, rec: VehicleRec, run, out: dict) -> dict:
        pts = list(rec.history)
        a0 = run.attack_start

        def err(p, k):
            if p.get(k) is None or p.get("truth") is None:
                return None
            return math.hypot(p[k][0] - p["truth"][0], p[k][1] - p["truth"][1])
        first_alarm = next((p for p in pts if a0 is not None and p["t"] >= a0 and p["state"] != "TRUSTED"), None)
        first_denied = next((p for p in pts if a0 is not None and p["t"] >= a0 and p["state"] == "DENIED"), None)
        pre = [p for p in pts if a0 is not None and p["t"] >= a0 and (first_alarm is None or p["t"] < first_alarm["t"])]
        raw_pre = [e for e in (err(p, "raw") for p in pre) if e is not None]
        raw_all = [e for e in (err(p, "raw") for p in pts if a0 is not None and p["t"] >= a0) if e is not None]
        nav_all = [e for e in (err(p, "nav") for p in pts if a0 is not None and p["t"] >= a0) if e is not None]
        false_alarm_s = 0.0
        if a0 is None or not run.is_attack:
            false_alarm_s = sum(0.2 for p in pts if p["state"] != "TRUSTED")
        return {"simulated": True, "notice": texts.SIM_NOTICE, "vehicle_id": rec.vid,
                "scenario": {"kind": run.kind, "seed": run.seed, "split": run.split, "label": run.truth_class,
                             "is_attack": run.is_attack, "event_start": a0, "event_end": run.attack_end,
                             "duration_s": float(run.t[-1]) if len(run.t) else 0.0},
                "final": {"state": rec.last["state"], "trust": rec.last["trust"], "action": rec.last["action"]},
                "transitions": [{k: t[k] for k in ("t", "from", "to", "trust", "dominant", "summary")}
                                for t in rec.transitions],
                "detection": {"first_non_trusted_t": first_alarm["t"] if first_alarm else None,
                              "latency_to_non_trusted_s": round(first_alarm["t"] - a0, 1) if first_alarm and a0 is not None else None,
                              "latency_to_denied_s": round(first_denied["t"] - a0, 1) if first_denied and a0 is not None else None,
                              "detected": first_alarm is not None},
                "ground_truth_errors_m": {"max_raw_gnss_error_before_alarm": round(max(raw_pre), 1) if raw_pre else None,
                                          "max_raw_gnss_error_during_event": round(max(raw_all), 1) if raw_all else None,
                                          "max_marsad_nav_error_during_event": round(max(nav_all), 1) if nav_all else None},
                "seconds_not_trusted_in_non_attack_scenario": round(false_alarm_s, 1) if not run.is_attack else None,
                "evidence": [e["message"] for e in rec.last.get("evidence", [])[:4]],
                "explanation": ("SIMULATED scenario. " + rec.last["explanation"])}


_store: Optional[Store] = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store()
        return _store


def reset_store() -> Store:
    global _store
    with _store_lock:
        _store = Store()
        return _store
