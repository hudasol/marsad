"""Engine configuration and vehicle presets."""
from __future__ import annotations
from dataclasses import dataclass, field, replace


@dataclass
class EngineConfig:
    # --- platform envelope -------------------------------------------------
    v_max: float = 30.0            # m/s, max plausible speed
    a_max: float = 8.0             # m/s^2, max plausible acceleration
    sigma_pos: float = 2.0         # m, nominal 1-sigma GNSS horizontal noise
    sigma_vel: float = 0.25        # m/s, nominal receiver velocity noise

    # --- reference (non-GNSS) motion source ----------------------------------
    ref_bias_bound: float = 0.08   # m/s, assumed bound on reference velocity bias (sets detectability floor)
    ref_noise: float = 0.2         # m/s, reference white velocity noise
    ref_timeout: float = 2.0       # s, reference considered lost after this gap

    # --- GNSS signal baselines (priors; adapted online while trusted) --------
    cn0_prior: float = 42.0        # dB-Hz
    cn0_std_prior: float = 3.0
    nsat_prior: float = 12.0
    gnss_gap_timeout: float = 1.5  # s without a usable fix => loss
    warmup_s: float = 20.0

    # --- detector tunables -------------------------------------------------
    cn0_drop_db: float = 5.0       # drop before jam/env evidence accrues
    cn0_rise_db: float = 2.0       # power advantage before spoof evidence accrues
    agc_rise: float = 0.06         # normalised AGC rise considered a jamming signature
    drift_windows: tuple = (5.0, 15.0, 45.0, 120.0)
    drift_z0: float = 2.0          # z-score before drift evidence accrues
    jump_x0: float = 3.0           # normalised innovation before jump evidence accrues
    clock_step_s: float = 0.25     # GNSS-vs-host clock step considered anomalous

    # --- fusion --------------------------------------------------------------
    tau: dict = field(default_factory=lambda: {
        "environmental_degradation": 10.0, "jamming": 10.0, "spoofing_jump": 30.0,
        "spoofing_drift": 30.0, "replay_meaconing": 30.0})
    prior_logit: dict = field(default_factory=lambda: {
        "environmental_degradation": -4.0, "jamming": -4.5, "spoofing_jump": -5.5,
        "spoofing_drift": -5.5, "replay_meaconing": -5.5})
    llr_clip: tuple = (-1.5, 10.0)

    # --- state machine -------------------------------------------------------
    degrade_below: float = 0.5     # p_nominal below this => at least DEGRADED
    deny_spoof_above: float = 0.5
    deny_jam_above: float = 0.75
    trust_resume_above: float = 0.8
    hold_to_degraded_s: float = 10.0
    hold_to_trusted_s: float = 6.0
    min_denied_s: float = 5.0
    spoof_hold_s: float = 30.0     # after spoof suspicion, stay below TRUSTED at least this long
    reacq_cap_m: float = 60.0      # beyond this dead-reckoning uncertainty, re-acquisition is unverifiable
    rewind_margin_s: float = 3.0   # anchor rewind margin before first suspicious evidence

    def with_(self, **kw) -> "EngineConfig":
        return replace(self, **kw)


_PRESETS = {
    "uav_multirotor": dict(v_max=25.0, a_max=10.0, ref_bias_bound=0.08),
    "uav_fixedwing": dict(v_max=60.0, a_max=12.0, ref_bias_bound=0.15, ref_noise=0.4),
    "ground_robot": dict(v_max=6.0, a_max=3.0, ref_bias_bound=0.03, ref_noise=0.08, sigma_pos=2.5),
    "vessel": dict(v_max=25.0, a_max=1.5, ref_bias_bound=0.12, ref_noise=0.3, sigma_pos=3.0),
}


def preset(name: str = "uav_multirotor", **overrides) -> EngineConfig:
    if name not in _PRESETS:
        raise KeyError(f"unknown preset {name!r}; choose from {sorted(_PRESETS)}")
    return EngineConfig(**{**_PRESETS[name], **overrides})
