"""Core data types. Plain dataclasses; JSON-friendly via to_dict()."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Hypothesis(str, Enum):
    NOMINAL = "nominal"
    ENV = "environmental_degradation"   # obstruction / multipath: degraded, not malicious
    JAM = "jamming"
    SPOOF_JUMP = "spoofing_jump"        # abrupt position/time takeover
    SPOOF_DRIFT = "spoofing_drift"      # gradual carry-off
    REPLAY = "replay_meaconing"         # delayed re-broadcast of genuine signals


class TrustState(str, Enum):
    TRUSTED = "TRUSTED"
    DEGRADED = "DEGRADED"
    DENIED = "DENIED"


class NavAction(str, Enum):
    USE_GNSS = "USE_GNSS"
    USE_GNSS_WITH_CAUTION = "USE_GNSS_WITH_CAUTION"
    FALLBACK_REFERENCE = "FALLBACK_REFERENCE"   # navigate on dead-reckoning / VIO / flow
    HOLD_AND_ALERT = "HOLD_AND_ALERT"           # no usable fallback: stop trusting, alert operator


@dataclass(slots=True)
class GnssFix:
    t: float                                 # host time (s)
    lat: float
    lon: float
    alt: float = 0.0
    ve: Optional[float] = None               # receiver-reported velocity east (m/s)
    vn: Optional[float] = None
    cn0_mean: Optional[float] = None         # dB-Hz, mean over tracked satellites
    cn0_std: Optional[float] = None          # dB-Hz, spread over satellites
    n_sats: Optional[int] = None
    agc: Optional[float] = None              # front-end AGC, normalised 0..1 (higher = more RF power)
    hdop: Optional[float] = None
    fix_type: int = 3                        # 3 = 3D fix; <3 treated as no usable fix
    t_gnss: Optional[float] = None           # receiver/GNSS time (s) for clock-consistency checks


@dataclass(slots=True)
class RefMotion:
    """Independent (non-GNSS) velocity reference: VIO, optical flow + range, wheel/DVL odometry, INS."""
    t: float
    ve: float
    vn: float
    sigma: Optional[float] = None            # 1-sigma velocity noise (m/s), optional
    source: str = "ref"
    quality: Optional[float] = None          # 0..1 tracking quality (e.g. VIO); low => sample is ignored


@dataclass(slots=True)
class NavSample:
    t: float
    gnss: Optional[GnssFix] = None
    ref: Optional[RefMotion] = None


@dataclass(slots=True)
class Evidence:
    detector: str
    kind: str
    llr: dict                                # Hypothesis -> log-likelihood-ratio contribution vs nominal
    message: str
    value: Optional[float] = None
    weight: float = 0.0                      # magnitude used to rank evidence for display

    def to_dict(self):
        return {"detector": self.detector, "kind": self.kind, "message": self.message,
                "value": self.value, "weight": round(self.weight, 3),
                "llr": {getattr(k, "value", k): round(v, 3) for k, v in self.llr.items()}}


@dataclass
class TrustReport:
    t: float
    state: TrustState
    trust: float                             # 0..1, probability the position can be believed
    probs: dict                              # hypothesis value -> posterior probability
    dominant: str                            # most probable non-nominal hypothesis (value)
    action: NavAction
    evidence: list = field(default_factory=list)
    nav_e: Optional[float] = None            # recommended position, local east (m)
    nav_n: Optional[float] = None
    nav_lat: Optional[float] = None
    nav_lon: Optional[float] = None
    gnss_offset_m: Optional[float] = None    # |GNSS - dead-reckoned continuation| when computable
    ref_ok: bool = False
    warmup: bool = False
    summary: str = ""

    def to_dict(self):
        return {
            "t": self.t, "state": self.state.value, "trust": round(self.trust, 4),
            "probs": {k: round(v, 4) for k, v in self.probs.items()},
            "dominant": self.dominant, "action": self.action.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "nav": {"e": self.nav_e, "n": self.nav_n, "lat": self.nav_lat, "lon": self.nav_lon},
            "gnss_offset_m": self.gnss_offset_m, "ref_ok": self.ref_ok,
            "warmup": self.warmup, "summary": self.summary,
        }
