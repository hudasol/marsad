"""Shared per-sample context and detector protocol."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol

from ..types import Evidence, GnssFix, RefMotion, TrustState


@dataclass
class Context:
    t: float = 0.0
    dt: float = 0.0
    gnss: Optional[GnssFix] = None       # fix delivered this tick (None = nothing new)
    ref: Optional[RefMotion] = None
    pe: float = 0.0                      # GNSS position, local frame (valid iff gnss is not None)
    pn: float = 0.0
    ce: float = 0.0                      # integrated reference displacement (east)
    cn: float = 0.0
    ref_ok: bool = False
    ref_valid_since: float = 0.0         # reference integral continuous since this time
    gnss_gap: float = 0.0                # seconds since last usable fix
    state: TrustState = TrustState.TRUSTED
    p_nominal: float = 1.0
    warmup: bool = True


class Detector(Protocol):
    name: str

    def update(self, ctx: Context) -> list[Evidence]: ...
    def learn(self, ctx: Context) -> None: ...   # adapt baselines; only called while trusted
