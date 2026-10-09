"""Server-side SIMULATED demo: replays a measurement-level scenario at an accelerated rate.

The ground-truth position is included in the stream ONLY for the demo vehicle, flagged simulated.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from . import texts
from .state import DEMO_VEHICLE, Store, StoreError, sim_mod, tracks_mod, Unavailable

TICK = 0.1


class DemoRunner:
    def __init__(self, store: Store):
        self.store = store
        self.task: Optional[asyncio.Task] = None

    def status(self) -> dict:
        return dict(self.store.demo)

    async def start(self, kind: str, seed: int, split: str, speed: float) -> dict:
        sim = sim_mod()
        from ..sim.generator import KINDS, SPLITS
        if kind not in KINDS:
            raise StoreError(422, f"unknown scenario {kind!r}; choose from {KINDS}")
        if split not in SPLITS:
            raise StoreError(422, f"unknown split {split!r}")
        await self.stop(quiet=True)
        run = await asyncio.to_thread(sim.generate, kind, seed, split)
        stream = []
        try:
            m = tracks_mod()
            stream = await asyncio.to_thread(m.make_demo_stream, seed)
        except Unavailable:
            pass
        truth = [run.frame.to_geo(float(e), float(n)) for e, n in zip(run.truth_e, run.truth_n)]
        st = self.store
        with st.lock:
            st.vehicles.pop(DEMO_VEHICLE, None)
            st.reset_tracks()
            st.clock = 0.0
            st.demo = {"running": True, "simulated": True, "vehicle_id": DEMO_VEHICLE, "kind": kind, "seed": seed,
                       "split": split, "speed": speed, "sim_t": 0.0, "duration": float(run.t[-1]),
                       "event_start": run.attack_start, "event_end": run.attack_end,
                       "label": run.truth_class, "is_attack": run.is_attack,
                       "tracks": bool(stream), "notice": texts.SIM_NOTICE}
        st.publish("demo", dict(st.demo))
        self.task = asyncio.create_task(self._loop(run, truth, stream, speed))
        return dict(st.demo)

    async def stop(self, quiet: bool = False) -> dict:
        t, self.task = self.task, None
        if t is not None and not t.done():
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        st = self.store
        if st.demo.get("running"):
            st.demo = {**st.demo, "running": False, "stopped": True}
            if not quiet:
                st.publish("demo", dict(st.demo))
        return dict(st.demo)

    async def _loop(self, run, truth, stream, speed) -> None:
        st = self.store
        samples = run.samples
        n, i, j = len(samples), 0, 0
        off = stream[0].t if stream else 0.0
        sim_t, last = 0.0, time.monotonic()
        last_status = 0.0
        try:
            while i < n or j < len(stream):
                await asyncio.sleep(TICK)
                now = time.monotonic()
                sim_t += (now - last) * speed
                last = now
                i0 = i
                while i < n and samples[i].t <= sim_t:
                    i += 1
                if i > i0:
                    st.ingest_samples(DEMO_VEHICLE, samples[i0:i], simulated=True, truth=truth[i0:i])
                    rec = st.vehicles[DEMO_VEHICLE]
                    rec.meta = {k: st.demo.get(k) for k in ("kind", "seed", "split", "event_start", "event_end", "label")}
                batch = []
                while j < len(stream) and stream[j].t - off <= sim_t:
                    r = stream[j]
                    batch.append({"track_id": r.track_id, "source": r.source, "t": r.t - off, "lat": r.lat,
                                  "lon": r.lon, "speed": r.speed, "course": r.course, "cls": r.cls,
                                  "accuracy_m": r.accuracy_m, "ident": r.ident})
                    j += 1
                if batch:
                    st.ingest_tracks(batch, origin="demo")
                if now - last_status >= 1.0:
                    last_status = now
                    st.demo = {**st.demo, "sim_t": round(min(sim_t, st.demo["duration"]), 1)}
                    st.publish("demo", dict(st.demo))
                    st.maybe_publish_scene(force=True)
            st.demo = {**st.demo, "running": False, "finished": True, "sim_t": st.demo["duration"]}
            st.publish("demo", dict(st.demo))
            st.maybe_publish_scene(force=True)
        except asyncio.CancelledError:
            raise
        except Exception as e:   # surface, never crash the server
            st.demo = {**st.demo, "running": False, "error": f"{type(e).__name__}: {e}"}
            st.publish("demo", dict(st.demo))
