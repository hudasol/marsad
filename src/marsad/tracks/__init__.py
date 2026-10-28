"""Track-trust module: score the positional trustworthiness of multi-source tracks."""

from .config import TrackConfig
from .engine import TrackTrustEngine
from .interference import InterferenceMap
from .sim import evaluate, make_demo_stream, make_scenario
from .types import TrackReport, TrackTrust, Zone

__all__ = [
    "TrackReport",
    "TrackTrust",
    "Zone",
    "TrackConfig",
    "TrackTrustEngine",
    "InterferenceMap",
    "make_scenario",
    "evaluate",
    "make_demo_stream",
]
