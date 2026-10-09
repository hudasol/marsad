"""Fleet interference map: hex-binned, time-decayed aggregation of trust events.

Cells are pointy-top hexagons in axial coordinates (q, r) over a local equirectangular projection
around a fixed reference point, so cell ids are stable across runs. ``cell_km`` is the
centre-to-centre spacing of neighbouring cells. Each cell keeps a decayed weight sum S (half-life
``half_life_s``); confidence = 1 - exp(-S), bounded to [0, 1).
"""
from __future__ import annotations
import math
from typing import Optional

from ..geo import LocalFrame

_SQRT3 = math.sqrt(3.0)

_STATE_WEIGHT = {"TRUSTED": 0.0, "DEGRADED": 0.5, "DENIED": 1.0,
                 "SUSPECT": 0.5, "DISTRUSTED": 1.0}
_HYP_FACTOR = {"nominal": 0.0, "environmental_degradation": 0.5, "jamming": 1.0,
               "spoofing_jump": 1.0, "spoofing_drift": 1.0, "replay_meaconing": 1.0}


class _Cell:
    __slots__ = ("S", "t", "n", "hyp")

    def __init__(self):
        self.S = 0.0
        self.t = -math.inf
        self.n = 0
        self.hyp: dict = {}


class InterferenceMap:
    def __init__(self, cell_km: float = 5.0, half_life_s: float = 1800.0,
                 ref_lat: float = 25.0, ref_lon: float = 55.0, max_cells: int = 20000):
        if cell_km <= 0 or half_life_s <= 0:
            raise ValueError("cell_km and half_life_s must be positive")
        self.cell_km, self.half_life_s = float(cell_km), float(half_life_s)
        self.max_cells = max_cells
        self._frame = LocalFrame(ref_lat, ref_lon)
        self._s = cell_km * 1000.0 / _SQRT3          # hex circumradius (m)
        self._cells: dict = {}

    # ---------------------------------------------------------------- geometry
    def _axial(self, e: float, n: float) -> tuple:
        s = self._s
        q = (_SQRT3 / 3.0 * e - n / 3.0) / s
        r = (2.0 / 3.0 * n) / s
        x, z = q, r
        y = -x - z
        rx, ry, rz = round(x), round(y), round(z)
        dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy > dz:
            ry = -rx - rz
        else:
            rz = -rx - ry
        return int(rx), int(rz)

    def _center(self, q: int, r: int) -> tuple:
        s = self._s
        return s * _SQRT3 * (q + r / 2.0), s * 1.5 * r

    def cell_id(self, lat: float, lon: float) -> str:
        q, r = self._axial(*self._frame.to_local(lat, lon))
        return f"{q},{r}"

    def _polygon(self, q: int, r: int) -> list:
        cx, cy = self._center(q, r)
        pts = []
        for i in range(6):
            a = math.radians(60.0 * i + 30.0)
            pts.append(self._frame.to_geo(cx + self._s * math.cos(a), cy + self._s * math.sin(a)))
        return pts

    # ---------------------------------------------------------------- updates
    def _decay(self, c: _Cell, t: float) -> None:
        if math.isfinite(c.t) and t > c.t:
            f = 0.5 ** ((t - c.t) / self.half_life_s)
            c.S *= f
            for k in c.hyp:
                c.hyp[k] *= f
        if t > c.t:
            c.t = t

    def _add(self, lat: float, lon: float, t: float, hyp: str, w: float) -> None:
        if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(t)):
            return
        key = self._axial(*self._frame.to_local(lat, lon))
        c = self._cells.get(key)
        if c is None:
            c = self._cells[key] = _Cell()
        self._decay(c, t)
        c.n += 1
        if w > 0:
            # an older-than-last report is added undecayed (cannot rewind the cell clock)
            c.S += w
            c.hyp[hyp] = c.hyp.get(hyp, 0.0) + w
        if len(self._cells) > self.max_cells:
            self._prune(t)

    def report_vehicle(self, lat: float, lon: float, t: float, state: str, hypothesis: str,
                       confidence: float) -> None:
        """Vehicle-trust event. TRUSTED/nominal reports count as observations but add no weight."""
        state = getattr(state, "value", state)
        hypothesis = getattr(hypothesis, "value", hypothesis)
        conf = min(1.0, max(0.0, float(confidence)))
        w = _STATE_WEIGHT.get(str(state).upper(), 0.0) * _HYP_FACTOR.get(str(hypothesis), 0.7) * conf
        self._add(lat, lon, t, str(hypothesis), w)

    def report_track_anomaly(self, lat: float, lon: float, t: float, kind: str, weight: float) -> None:
        self._add(lat, lon, t, str(kind), max(0.0, float(weight)))

    def _prune(self, t: float) -> None:
        keep = sorted(self._cells.items(), key=lambda kv: -self._conf(kv[1], t))[: int(self.max_cells * 0.9)]
        self._cells = dict(keep)

    # ---------------------------------------------------------------- queries
    def _conf(self, c: _Cell, t: float) -> float:
        dt = max(0.0, t - c.t) if math.isfinite(c.t) else 0.0
        S = c.S * 0.5 ** (dt / self.half_life_s)
        return 1.0 - math.exp(-S)

    def confidence(self, lat: float, lon: float, t: float) -> float:
        c = self._cells.get(self._axial(*self._frame.to_local(lat, lon)))
        return 0.0 if c is None else min(1.0, max(0.0, self._conf(c, t)))

    def cells(self, t: float, min_confidence: float = 1e-3) -> list:
        out = []
        for (q, r), c in self._cells.items():
            conf = self._conf(c, t)
            if conf < min_confidence:
                continue
            dom = max(c.hyp.items(), key=lambda kv: (kv[1], kv[0]))[0] if c.hyp else "none"
            lat, lon = self._frame.to_geo(*self._center(q, r))
            out.append({"id": f"{q},{r}", "lat": lat, "lon": lon, "confidence": min(1.0, conf),
                        "last_update": c.t, "n_reports": c.n, "dominant": dom,
                        "polygon": self._polygon(q, r)})
        out.sort(key=lambda d: (-d["confidence"], d["id"]))
        return out

    def to_geojson(self, t: float, min_confidence: float = 1e-3) -> dict:
        feats = []
        for c in self.cells(t, min_confidence):
            ring = [[lon, lat] for lat, lon in c["polygon"]]
            ring.append(ring[0])
            feats.append({"type": "Feature", "id": c["id"],
                          "geometry": {"type": "Polygon", "coordinates": [ring]},
                          "properties": {"id": c["id"], "confidence": round(c["confidence"], 4),
                                         "last_update": c["last_update"], "n_reports": c["n_reports"],
                                         "dominant": c["dominant"], "lat": c["lat"], "lon": c["lon"]}})
        return {"type": "FeatureCollection", "features": feats,
                "properties": {"cell_km": self.cell_km, "half_life_s": self.half_life_s, "t": t}}
