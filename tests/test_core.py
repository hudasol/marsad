import math
from marsad.geo import LocalFrame, haversine
from marsad.fusion import Fusion
from marsad.config import preset, EngineConfig
from marsad.types import Evidence, Hypothesis as H
import pytest


def test_local_frame_roundtrip():
    f = LocalFrame(24.45, 54.38)
    e, n = f.to_local(24.46, 54.39)
    lat, lon = f.to_geo(e, n)
    assert abs(lat - 24.46) < 1e-9 and abs(lon - 54.39) < 1e-9
    assert abs(math.hypot(e, n) - haversine(24.45, 54.38, 24.46, 54.39)) < 5.0


def test_fusion_quiet_detectors_give_no_evidence():
    f = Fusion(preset())
    for _ in range(1000):
        p = f.step(0.2, [])
    assert p["nominal"] > 0.95


def test_fusion_evidence_accumulates_and_decays():
    f = Fusion(preset())
    p = f.step(0.2, [Evidence("x", "k", {H.SPOOF_JUMP: 8.0}, "m")])
    assert p["spoofing_jump"] > 0.8
    for _ in range(2000):
        p = f.step(0.2, [])
    assert p["nominal"] > 0.9


def test_presets():
    assert preset("ground_robot").v_max < preset("uav_fixedwing").v_max
    with pytest.raises(KeyError):
        preset("nope")
