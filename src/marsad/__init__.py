"""Marsad (مرصد): position-trust layer for autonomous systems and decision platforms."""

from .config import EngineConfig, preset
from .engine import TrustEngine
from .types import Evidence, GnssFix, Hypothesis, NavAction, NavSample, RefMotion, TrustReport, TrustState

__version__ = "1.4.0"
__all__ = [
    "GnssFix",
    "RefMotion",
    "NavSample",
    "Evidence",
    "TrustReport",
    "TrustState",
    "NavAction",
    "Hypothesis",
    "EngineConfig",
    "preset",
    "TrustEngine",
    "__version__",
]
