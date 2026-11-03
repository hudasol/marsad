"""Tests for scripts/real_corpus.py on small synthetic inputs (no downloaded logs are used)."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location(
    "real_corpus", Path(__file__).resolve().parents[1] / "scripts" / "real_corpus.py"
)
rc = importlib.util.module_from_spec(_spec)
sys.modules["real_corpus"] = rc
_spec.loader.exec_module(rc)


def test_clopper_pearson_matches_known_values():
    lo, hi = rc.clopper_pearson(0, 30)
    assert lo == 0.0 and hi == pytest.approx(0.1157, abs=2e-4)  # exact upper bound for 0 of 30
    lo, hi = rc.clopper_pearson(5, 20)
    assert (lo, hi) == (pytest.approx(0.0866, abs=2e-4), pytest.approx(0.4910, abs=2e-4))
    assert rc.clopper_pearson(10, 10)[1] == 1.0 and rc.clopper_pearson(0, 0) == (0.0, 1.0)


def test_mcnemar_exact():
    assert rc.mcnemar_exact(0, 0) == 1.0
    assert rc.mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    assert rc.mcnemar_exact(3, 3) == 1.0


def test_episodes_merge_close_runs_and_close_open_runs():
    t = list(range(20))
    f = [False] * 3 + [True] * 2 + [False] * 2 + [True] * 2 + [False] * 8 + [True] * 3
    assert rc.episodes(t, f, merge_s=5.0) == [[3, 8], [17, 19]]
    assert rc.episodes(t, f, merge_s=0.5) == [[3, 4], [7, 8], [17, 19]]
    assert rc.overlap([[3, 8], [17, 19]], [[10, 11]], 3.0) == 1


def test_design_subset_is_a_stable_fifth():
    ids = [f"log-{i}" for i in range(2000)]
    share = sum(rc.design_subset(i) for i in ids) / len(ids)
    assert 0.17 < share < 0.23
    assert rc.design_subset("log-7") == rc.design_subset("log-7")


def _entry(i, hw, ver="v1.15.0 0", **kw):
    d = {
        "log_id": f"id{i}",
        "download_url": f"https://example.invalid/id{i}.ulg",
        "ver_sw_release": ver,
        "sys_hw": hw,
        "mav_type": "Quadrotor",
        "duration_s": 600,
        "estimator": "EKF2",
        "vehicle_uuid": f"veh{i // 5}",
        "error_labels": [],
    }
    d.update(kw)
    return d


def test_selection_filters_and_caps_and_is_deterministic():
    entries = [_entry(i, f"HW{i % 8}") for i in range(300)]
    entries += [_entry(1000, "PX4_SITL"), _entry(1001, "HWX", ver="v1.10.0 0"), _entry(1002, "HWX", duration_s=30)]
    entries += [_entry(1003, "HWX", estimator="LPE"), _entry(1004, "HWX", mav_type="Rover")]
    a = rc.select_candidates(entries, n_main=100, n_err=0)
    b = rc.select_candidates(entries, n_main=100, n_err=0)
    assert a == b
    ids = {c["log_id"] for c in a}
    assert not ids & {"id1000", "id1001", "id1002", "id1003", "id1004"}
    assert max(sum(c["hardware"] == h for c in a) for h in {c["hardware"] for c in a}) <= rc.MAX_PER_HW
    veh = [e["vehicle_uuid"] for e in entries if e["log_id"] in ids]
    assert max(veh.count(v) for v in set(veh)) <= rc.MAX_PER_VEHICLE


def test_error_labelled_logs_form_their_own_stratum():
    entries = [_entry(i, f"HW{i % 4}") for i in range(40)] + [
        _entry(100 + i, "HWE", error_labels=[2]) for i in range(6)
    ]
    sel = rc.select_candidates(entries, n_main=10, n_err=4)
    assert {c["stratum"] for c in sel} == {"main", "error_labels"}
    assert all(c["log_id"].startswith("id1") for c in sel if c["stratum"] == "error_labels")


class _D:
    def __init__(self, name, data, multi_id=0):
        self.name, self.data, self.multi_id = name, data, multi_id


def test_ekf2_rejection_and_fault_episodes_are_read_from_topics():
    t = np.arange(0, 30, 0.5)
    rej = np.zeros(len(t), dtype=bool)
    rej[10:16] = True  # 5 s to 8 s
    flags_gnss = np.ones(len(t), dtype=bool)
    flags_gnss[40:44] = False  # fused position off while airborne
    ul = SimpleNamespace(
        data_list=[
            _D("estimator_aid_src_gnss_pos", {"timestamp": (t * 1e6).astype(np.uint64), "innovation_rejected": rej}),
            _D("estimator_aid_src_gnss_vel", {"timestamp": (t * 1e6).astype(np.uint64), "fused": np.ones(len(t))}),
            _D(
                "estimator_status_flags",
                {
                    "timestamp": (t * 1e6).astype(np.uint64),
                    "cs_gnss_pos": flags_gnss,
                    "cs_in_air": np.ones(len(t), dtype=bool),
                },
            ),
        ]
    )
    ek = rc.ekf2_episodes(ul)
    assert ek["pos_rejected"] == [[5.0, 7.5]] and ek["vel_rejected"] == []
    assert ek["fault"] == [[20.0, 21.5]]
    assert set(ek["topics"]) == {"estimator_aid_src_gnss_pos", "estimator_aid_src_gnss_vel", "estimator_status_flags"}


def test_longest_run():
    assert rc.longest_run([0, 1, 2, 3, 4, 5], [False, True, True, True, False, True]) == 2
    assert rc.longest_run([], []) == 0.0


def test_release_minor():
    assert rc.release_minor("v1.15.4 255") == "v1.15" and rc.release_minor("") == ""


def test_analyze_and_summarise_on_a_synthetic_clean_log(tmp_path):
    pytest.importorskip("pyulog")
    from marsad.adapters.ulog_writer import write_ulog
    from marsad.sim import generate

    run = generate("nominal", 3, "dev", duration=120.0, cadence=1.0)
    p = tmp_path / "clean.ulg"
    write_ulog(str(p), run)
    out = rc.analyze_log(str(p), "Quadrotor")
    assert out["marsad"]["has_alarm"] is False and out["marsad"]["share_trusted"] == 1.0
    assert set(out["baselines"]) >= {"window", "ekf2_gate", "signal"}
    assert out["ekf2"]["topics"] == []
    manifest = [
        {"log_id": "a", "design_subset": "false", "stratum": "main", "release": "v1.15.0 0", "hardware": "H1"},
        {"log_id": "b", "design_subset": "true", "stratum": "main", "release": "v1.15.0 0", "hardware": "H1"},
    ]
    s = rc.summarise({"a": out, "b": out}, manifest)
    assert s["n_scored"] == 1 and s["n_design_subset"] == 1
    assert s["R1_all_trusted"]["k"] == 1 and s["R2_any_denied"]["rule_of_three_upper"] == 3.0
    assert not math.isnan(s["flight_hours"])
