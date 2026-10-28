import math

import pytest

from marsad.config import preset
from marsad.fusion import Fusion
from marsad.geo import LocalFrame, haversine
from marsad.types import Evidence
from marsad.types import Hypothesis as H


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


def test_load_config_overrides_and_rejects_typos(tmp_path):
    import json

    import pytest

    from marsad.config import load_config

    good = tmp_path / "c.json"
    good.write_text(json.dumps({"preset": "ground_robot", "sigma_pos": 3.5, "drift_windows": [10, 60]}))
    cfg = load_config(str(good))
    assert cfg.sigma_pos == 3.5 and cfg.v_max == 6.0 and cfg.drift_windows == (10.0, 60.0)
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"sigma_posn": 3.5}))
    with pytest.raises(ValueError, match="sigma_posn"):
        load_config(str(bad))
