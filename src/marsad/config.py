"""Engine configuration and vehicle presets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from typing import Any


@dataclass
class EngineConfig:
    # --- platform envelope -------------------------------------------------
    v_max: float = 30.0  # m/s, max plausible speed
    a_max: float = 8.0  # m/s^2, max plausible acceleration
    sigma_pos: float = 2.0  # m, nominal 1-sigma GNSS horizontal noise
    sigma_vel: float = 0.25  # m/s, nominal receiver velocity noise

    # --- reference (non-GNSS) motion source ----------------------------------
    ref_bias_bound: float = 0.08  # m/s, assumed bound on reference velocity bias (sets detectability floor)
    ref_noise: float = 0.2  # m/s, reference white velocity noise
    ref_timeout: float = 2.0  # s, reference considered lost after this gap
    ref_min_quality: float = 0.3  # RefMotion.quality below this => sample ignored (counts as a reference gap)
    bias_est: bool = True  # learn reference velocity bias against GNSS velocity while trusted
    bias_tau: float = 900.0  # s, time constant of the (deliberately slow) bias estimator
    bias_min_s: float = 150.0  # s of clean learning before the tighter bias bound is used
    ref_bias_residual: float = 0.03  # m/s, bias bound assumed AFTER estimation (random-walk residual)

    # --- GNSS signal baselines (priors; adapted online while trusted) --------
    cn0_prior: float = 42.0  # dB-Hz
    cn0_std_prior: float = 3.0
    nsat_prior: float = 12.0
    gnss_gap_timeout: float = 1.5  # s without a usable fix => loss
    warmup_s: float = 20.0

    # --- detector tunables -------------------------------------------------
    cn0_drop_db: float = 4.0  # drop before jam/env evidence accrues
    cn0_rise_db: float = 2.0  # power advantage before spoof evidence accrues
    agc_rise: float = 0.06  # normalised AGC rise considered a jamming signature
    drift_windows: tuple = (5.0, 15.0, 45.0, 120.0, 240.0)
    drift_z0: float = 2.0  # z-score before drift evidence accrues
    jump_x0: float = 3.0  # normalised innovation before jump evidence accrues
    clock_step_s: float = 0.25  # GNSS-vs-host clock step considered anomalous

    # --- fusion --------------------------------------------------------------
    tau: dict = field(
        default_factory=lambda: {
            "environmental_degradation": 10.0,
            "jamming": 10.0,
            "spoofing_jump": 30.0,
            "spoofing_drift": 30.0,
            "replay_meaconing": 30.0,
        }
    )
    prior_logit: dict = field(
        default_factory=lambda: {
            "environmental_degradation": -4.0,
            "jamming": -4.5,
            "spoofing_jump": -5.5,
            "spoofing_drift": -5.5,
            "replay_meaconing": -5.5,
        }
    )
    llr_clip: tuple = (-1.5, 10.0)

    # --- state machine -------------------------------------------------------
    degrade_below: float = 0.5  # p_nominal below this => at least DEGRADED
    deny_spoof_above: float = 0.5
    deny_jam_above: float = 0.75
    trust_resume_above: float = 0.8
    hold_to_degraded_s: float = 10.0
    hold_to_trusted_s: float = 6.0
    min_denied_s: float = 5.0
    spoof_hold_s: float = 30.0  # after spoof suspicion, stay below TRUSTED at least this long
    reacq_cap_m: float = 60.0  # beyond this dead-reckoning uncertainty, re-acquisition is unverifiable
    rewind_margin_s: float = 3.0  # anchor rewind margin before first suspicious evidence

    # --- engine bookkeeping (values unchanged from version 1.4.0; moved out of the update method) -------------------
    dt_max_s: float = 5.0  # s, largest time step the engine integrates over
    jump_attribution_weight: float = 2.0  # a position jump heavier than this explains the drift windows lighting up
    jump_attribution_windows: float = 1.7  # ... for this multiple of the longest drift window
    jump_replay_share: float = 0.3  # share of that drift evidence passed to the replay hypothesis
    persistent_offset_rate: float = 1.2  # evidence per second while GNSS sits off the dead reckoned track
    verify_hold_s: float = 10.0  # s of verified agreement before the inertial windows are cut
    verify_z_max: float = 1.0  # short window z below which agreement counts as independent proof
    verified_rate: float = -2.0  # evidence per second against every attack hypothesis while verified
    learn_p_nominal: float = 0.9  # learn and anchor only while P(nominal) is above this
    bias_limit_factor: float = 1.5  # estimated bias is clipped to this multiple of the prior bound
    anchor_tau_s: float = 10.0  # s, smoothing time of the anchor
    anchor_history_max: int = 3000  # entries kept for the anchor rewind
    anchor_history_trim: int = 1000  # entries dropped when the history is full
    clean_onset_below: float = 0.5  # onset evidence below this counts as clean for the rewind point
    reacq_sigma_factor: float = 3.0  # re-acquisition allowance: this many position sigmas ...
    reacq_bias_factor: float = 1.25  # ... plus this multiple of the bias bound times the elapsed time
    spoof_hold_trigger: float = 0.2  # spoof probability above this restarts the spoof hold timer
    replay_report_below: float = 0.95  # P(nominal) below which a measured replay lag decides the reported class
    none_report_above: float = 0.95  # P(nominal) at or above which no dominant class is reported
    trust_cap_degraded: float = 0.49  # reported trust ceiling while DEGRADED
    trust_cap_denied: float = 0.14  # reported trust ceiling while DENIED
    explain_window_s: float = 15.0  # s, how long evidence stays available for the explanation
    explain_keep: int = 200  # evidence entries kept
    explain_top: int = 4  # evidence entries reported
    explain_min_weight: float = 0.02  # weight below which evidence is not listed

    def with_(self, **kw: Any) -> "EngineConfig":
        return replace(self, **kw)


_PRESETS = {
    "uav_multirotor": dict(v_max=25.0, a_max=10.0, ref_bias_bound=0.08),
    "uav_fixedwing": dict(v_max=60.0, a_max=12.0, ref_bias_bound=0.15, ref_noise=0.4),
    "ground_robot": dict(v_max=6.0, a_max=3.0, ref_bias_bound=0.03, ref_noise=0.08, sigma_pos=2.5),
    "vessel": dict(v_max=25.0, a_max=1.5, ref_bias_bound=0.12, ref_noise=0.3, sigma_pos=3.0),
}


def preset(name: str = "uav_multirotor", **overrides: Any) -> EngineConfig:
    if name not in _PRESETS:
        raise KeyError(f"unknown preset {name!r}; choose from {sorted(_PRESETS)}")
    return EngineConfig(**{**_PRESETS[name], **overrides})


def load_config(path: str) -> EngineConfig:
    """Build an EngineConfig from a JSON file: an optional "preset" name plus any EngineConfig field to override.

    Example: {"preset": "ground_robot", "ref_bias_bound": 0.05, "sigma_pos": 3.0}
    Unknown keys are an error, so a typo cannot silently leave a threshold at its default.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    name = data.pop("preset", "uav_multirotor")
    known = {f.name for f in fields(EngineConfig)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"{path}: unknown configuration key(s) {unknown}; valid keys: {sorted(known)}")
    if "drift_windows" in data:
        data["drift_windows"] = tuple(float(x) for x in data["drift_windows"])
    return preset(name, **data)
