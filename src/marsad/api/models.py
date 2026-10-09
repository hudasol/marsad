"""Pydantic request models shared by the REST service and the MCP server.

Field names match ``marsad.types.GnssFix`` / ``RefMotion`` so a JSON sample is a direct
serialisation of the core dataclasses. Validation rejects NaN/Inf and out-of-range values.
"""
from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..config import _PRESETS
from ..types import GnssFix, NavSample, RefMotion

MAX_BATCH = int(os.environ.get("MARSAD_MAX_BATCH", "2000"))
PRESETS = tuple(sorted(_PRESETS))
TRACK_CLASSES = ("vessel", "aircraft", "ground", "unknown")

_F = dict(allow_inf_nan=False)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class GnssIn(_Strict):
    t: Optional[float] = Field(None, description="Host time (s). Defaults to the sample time.", **_F)
    lat: float = Field(..., ge=-90, le=90, **_F)
    lon: float = Field(..., ge=-180, le=180, **_F)
    alt: float = Field(0.0, ge=-1000, le=100000, **_F)
    ve: Optional[float] = Field(None, ge=-5000, le=5000, **_F)
    vn: Optional[float] = Field(None, ge=-5000, le=5000, **_F)
    cn0_mean: Optional[float] = Field(None, ge=0, le=100, **_F)
    cn0_std: Optional[float] = Field(None, ge=0, le=100, **_F)
    n_sats: Optional[int] = Field(None, ge=0, le=200)
    agc: Optional[float] = Field(None, ge=0, le=1, description="Normalised 0..1", **_F)
    hdop: Optional[float] = Field(None, ge=0, le=1000, **_F)
    fix_type: int = Field(3, ge=0, le=6)
    t_gnss: Optional[float] = Field(None, **_F)


class RefIn(_Strict):
    t: Optional[float] = Field(None, **_F)
    ve: float = Field(..., ge=-5000, le=5000, **_F)
    vn: float = Field(..., ge=-5000, le=5000, **_F)
    sigma: Optional[float] = Field(None, ge=0, le=1000, **_F)
    source: str = Field("ref", min_length=1, max_length=32)


class SampleIn(_Strict):
    t: float = Field(..., ge=0, le=1e11, description="Sample time in seconds, non-decreasing", **_F)
    gnss: Optional[GnssIn] = None
    ref: Optional[RefIn] = None

    def to_nav(self) -> NavSample:
        g = r = None
        if self.gnss is not None:
            d = self.gnss.model_dump()
            if d["t"] is None:
                d["t"] = self.t
            g = GnssFix(**d)
        if self.ref is not None:
            d = self.ref.model_dump()
            if d["t"] is None:
                d["t"] = self.t
            r = RefMotion(**d)
        return NavSample(t=self.t, gnss=g, ref=r)


class SamplesBody(_Strict):
    samples: list[SampleIn] = Field(..., min_length=1, max_length=MAX_BATCH)
    preset: Optional[str] = Field(None, description=f"Vehicle preset, one of {PRESETS}. Used when the vehicle is created.")


class TrackReportIn(_Strict):
    track_id: str = Field(..., min_length=1, max_length=128)
    source: str = Field(..., min_length=1, max_length=64)
    t: float = Field(..., ge=0, le=1e11, **_F)
    lat: float = Field(..., ge=-90, le=90, **_F)
    lon: float = Field(..., ge=-180, le=180, **_F)
    speed: Optional[float] = Field(None, ge=0, le=100000, description="m/s", **_F)
    course: Optional[float] = Field(None, ge=0, le=360, description="degrees", **_F)
    cls: str = Field("unknown", pattern="^(vessel|aircraft|ground|unknown)$")
    accuracy_m: Optional[float] = Field(None, ge=0, le=1e6, **_F)
    ident: Optional[str] = Field(None, max_length=64)


class TracksBody(_Strict):
    reports: list[TrackReportIn] = Field(..., min_length=1, max_length=MAX_BATCH)


class DemoStart(_Strict):
    kind: str = "spoof_drift"
    seed: int = Field(1, ge=0, le=2**31 - 1)
    split: str = Field("dev", pattern="^(dev|heldout)$")
    speed: float = Field(10.0, ge=0.5, le=100.0, description="Simulated seconds per wall-clock second", **_F)


class Acknowledge(_Strict):
    operator: Optional[str] = Field(None, max_length=64)
    note: Optional[str] = Field(None, max_length=500)
