"""FastAPI application: REST + Server-Sent Events + dashboard."""
from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .demo import DemoRunner
from .models import Acknowledge, DemoStart, SamplesBody, TracksBody
from .state import HISTORY, Store, StoreError, dumps, get_store

MAX_BODY = int(os.environ.get("MARSAD_MAX_BODY_BYTES", str(8 * 1024 * 1024)))
VID = PathParam(..., pattern=r"^[A-Za-z0-9_.\-]{1,64}$", description="Vehicle id")
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


def create_app(api_key: Optional[str] = None, store: Optional[Store] = None,
               cors_origins: Optional[list[str]] = None) -> FastAPI:
    """Build the service. ``api_key`` falls back to env MARSAD_API_KEY (unset = open, for local use).
    CORS is off unless ``cors_origins`` or env MARSAD_CORS_ORIGINS (comma separated) is given."""
    st = store or get_store()
    key = api_key if api_key is not None else os.environ.get("MARSAD_API_KEY") or None
    if cors_origins is None:
        env = os.environ.get("MARSAD_CORS_ORIGINS", "")
        cors_origins = [o.strip() for o in env.split(",") if o.strip()]
    demo = DemoRunner(st)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await demo.stop(quiet=True)

    app = FastAPI(title="Marsad API", version="v1", lifespan=lifespan,
                  description="Position-trust service. Advisory only. Simulated data is always flagged `simulated: true`.")
    app.state.store, app.state.demo = st, demo
    if cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST", "DELETE"],
                           allow_headers=["X-API-Key", "Authorization", "Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        # drop echoed input: it may hold NaN/Inf, which is not valid JSON
        errs = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
        return JSONResponse({"detail": errs}, status_code=422)

    @app.exception_handler(StoreError)
    async def _store_error(_: Request, exc: StoreError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    def guard(request: Request) -> None:
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY:
            raise HTTPException(413, f"request body exceeds {MAX_BODY} bytes")
        if key is None:
            return
        got = request.headers.get("x-api-key")
        if got is None:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                got = auth[7:].strip()
        if got is None and request.url.path.endswith("/stream"):
            got = request.query_params.get("api_key")   # EventSource cannot set headers
        if got is None or not hmac.compare_digest(got.encode(), key.encode()):
            raise HTTPException(401, "missing or invalid API key", headers={"WWW-Authenticate": "Bearer"})

    pub = APIRouter(prefix="/v1", tags=["meta"])
    r = APIRouter(prefix="/v1", dependencies=[Depends(guard)])

    @pub.get("/health")
    def health():
        return {**st.health(), "auth_required": key is not None}

    @pub.get("/version")
    def version():
        return st.version_info()

    # ---- vehicles -----------------------------------------------------------------
    @r.post("/vehicles/{vid}/samples", tags=["vehicles"])
    def post_samples(body: SamplesBody, vid: str = VID):
        """Feed a time-ordered batch of samples; returns the latest TrustReport and state transitions."""
        return st.ingest_samples(vid, [s.to_nav() for s in body.samples], body.preset)

    @r.get("/vehicles", tags=["vehicles"])
    def list_vehicles():
        return {"vehicles": st.list_vehicles()}

    @r.get("/vehicles/{vid}/trust", tags=["vehicles"])
    def vehicle_trust(vid: str = VID):
        return st.vehicle_trust(vid)

    @r.get("/vehicles/{vid}/history", tags=["vehicles"])
    def vehicle_history(vid: str = VID, n: int = Query(600, ge=1, le=HISTORY)):
        return st.history(vid, n)

    @r.post("/vehicles/{vid}/acknowledge", tags=["vehicles"])
    def vehicle_ack(body: Optional[Acknowledge] = None, vid: str = VID):
        """Operator override: accept the current GNSS as trusted (engine.acknowledge())."""
        b = body or Acknowledge()
        return st.acknowledge(vid, b.operator, b.note)

    @r.delete("/vehicles/{vid}", tags=["vehicles"])
    def vehicle_delete(vid: str = VID):
        st.delete_vehicle(vid)
        return {"deleted": vid}

    # ---- tracks -------------------------------------------------------------------
    @r.post("/tracks/reports", tags=["tracks"])
    def post_tracks(body: TracksBody):
        return st.ingest_tracks([x.model_dump() for x in body.reports])

    @r.get("/tracks", tags=["tracks"])
    def list_tracks(state: Optional[str] = Query(None, pattern="^(?i:TRUSTED|SUSPECT|DISTRUSTED)$"),
                    max_trust: Optional[float] = Query(None, ge=0, le=1),
                    limit: int = Query(500, ge=1, le=5000)):
        """Tracks sorted most-distrusted first."""
        rows = st.list_tracks(state, max_trust, limit)
        return {"tracks": rows, "n": len(rows), "simulated": st.track_origin == "demo"}

    @r.get("/tracks/{tid}", tags=["tracks"])
    def get_track(tid: str = PathParam(..., min_length=1, max_length=128)):
        return st.get_track(tid)

    @r.get("/sources", tags=["tracks"])
    def sources():
        return {"sources": st.source_health(), "simulated": st.track_origin == "demo"}

    @r.get("/map/interference", tags=["map"])
    def interference(bbox: Optional[str] = Query(None, description="min_lon,min_lat,max_lon,max_lat")):
        bb = None
        if bbox:
            try:
                bb = tuple(float(x) for x in bbox.split(","))
                assert len(bb) == 4 and bb[0] <= bb[2] and bb[1] <= bb[3]
            except Exception:
                raise HTTPException(422, "bbox must be min_lon,min_lat,max_lon,max_lat")
        return st.interference(bb)

    # ---- stream -------------------------------------------------------------------
    @r.get("/stream", tags=["stream"])
    async def stream(max_events: Optional[int] = Query(None, ge=1, le=100000, description="close after N events (testing)")):
        """Server-Sent Events: hello, scene, vehicle, transition, acknowledge, demo, vehicle_deleted."""
        loop = asyncio.get_running_loop()
        sub = st.subscribe(loop)

        def fmt(i, kind, data):
            return f"id: {i}\nevent: {kind}\ndata: {data}\n\n"

        async def gen():
            try:
                yield "retry: 2000\n\n"
                hello = {**st.version_info(), "vehicles": st.list_vehicles(), "demo": st.demo}
                yield fmt(0, "hello", dumps(hello))
                yield fmt(0, "scene", dumps(st.scene()))
                sent = 2
                while max_events is None or sent < max_events:
                    try:
                        i, kind, data = await asyncio.wait_for(sub.q.get(), 15.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    yield fmt(i, kind, data)
                    sent += 1
            finally:
                st.unsubscribe(sub)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---- demo ---------------------------------------------------------------------
    @r.post("/demo/start", tags=["demo"])
    async def demo_start(body: Optional[DemoStart] = None):
        b = body or DemoStart()
        return await demo.start(b.kind, b.seed, b.split, b.speed)

    @r.post("/demo/stop", tags=["demo"])
    async def demo_stop():
        return await demo.stop()

    @r.get("/demo/status", tags=["demo"])
    def demo_status():
        return demo.status()

    @r.get("/demo/scenarios", tags=["demo"])
    def demo_scenarios():
        return st.scenarios()

    app.include_router(pub)
    app.include_router(r)

    if (DASHBOARD_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
    return app
