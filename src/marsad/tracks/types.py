"""Track-trust data types. Plain dataclasses, JSON-friendly via to_dict()/from_dict()."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

CLASSES = ("air", "surface", "ground", "unknown")
STATES = ("TRUSTED", "SUSPECT", "DISTRUSTED")


@dataclass(slots=True)
class TrackReport:
    """One position report for one track from one source."""
    track_id: str
    source: str
    t: float                                  # report timestamp (s)
    lat: float
    lon: float
    speed: Optional[float] = None             # m/s
    course: Optional[float] = None            # deg true
    cls: str = "unknown"                      # 'air' | 'surface' | 'ground' | 'unknown'
    accuracy_m: Optional[float] = None        # claimed 1-sigma horizontal accuracy (per axis)
    ident: Optional[str] = None               # cross-source identity (e.g. MMSI / ICAO), if any

    def to_dict(self) -> dict:
        return {"track_id": self.track_id, "source": self.source, "t": self.t,
                "lat": self.lat, "lon": self.lon, "speed": self.speed, "course": self.course,
                "cls": self.cls, "accuracy_m": self.accuracy_m, "ident": self.ident}

    @classmethod
    def from_dict(cls, d: dict) -> "TrackReport":
        keys = ("track_id", "source", "t", "lat", "lon", "speed", "course", "cls", "accuracy_m", "ident")
        return cls(**{k: d[k] for k in keys if k in d})


@dataclass(slots=True)
class Zone:
    """Circular zone in which some track classes are implausible (e.g. a vessel on an airport)."""
    name: str
    lat: float
    lon: float
    radius_m: float
    forbidden_classes: set = field(default_factory=set)

    def to_dict(self) -> dict:
        return {"name": self.name, "lat": self.lat, "lon": self.lon, "radius_m": self.radius_m,
                "forbidden_classes": sorted(self.forbidden_classes)}


@dataclass
class TrackTrust:
    track_id: str
    trust: float                              # 0..1, probability the position can be believed
    state: str                                # 'TRUSTED' | 'SUSPECT' | 'DISTRUSTED'
    reasons: list = field(default_factory=list)   # dicts: kind, message, weight (+ t)
    sources: list = field(default_factory=list)
    last_t: float = 0.0
    n_reports: int = 0
    lat: float = 0.0
    lon: float = 0.0

    def to_dict(self) -> dict:
        return {"track_id": self.track_id, "trust": round(self.trust, 4), "state": self.state,
                "reasons": [dict(r) for r in self.reasons], "sources": list(self.sources),
                "last_t": self.last_t, "n_reports": self.n_reports,
                "lat": self.lat, "lon": self.lon}
