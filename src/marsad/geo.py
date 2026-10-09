"""Small geodesy helpers (stdlib only). Local tangent-plane frame: x=east, y=north, metres."""
from __future__ import annotations
import math

R_EARTH = 6378137.0


class LocalFrame:
    """Equirectangular local frame around an origin. Accurate to ~cm over tens of km."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self._k = math.cos(math.radians(lat0))

    def to_local(self, lat: float, lon: float) -> tuple[float, float]:
        e = math.radians(lon - self.lon0) * R_EARTH * self._k
        n = math.radians(lat - self.lat0) * R_EARTH
        return e, n

    def to_geo(self, e: float, n: float) -> tuple[float, float]:
        lat = self.lat0 + math.degrees(n / R_EARTH)
        lon = self.lon0 + math.degrees(e / (R_EARTH * self._k))
        return lat, lon


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x
