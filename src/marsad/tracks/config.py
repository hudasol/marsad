"""Track-trust configuration."""
from __future__ import annotations
from dataclasses import dataclass, field, replace


@dataclass
class TrackConfig:
    # --- class envelopes -------------------------------------------------------
    v_max: dict = field(default_factory=lambda: {"air": 350.0, "surface": 30.0, "ground": 45.0, "unknown": 350.0})
    a_max: dict = field(default_factory=lambda: {"air": 40.0, "surface": 3.0, "ground": 8.0, "unknown": 40.0})
    default_accuracy_m: float = 25.0       # used when a report carries no accuracy_m
    min_accuracy_m: float = 3.0            # floor on claimed accuracy (sources over-claim)

    # --- evidence combination (log-odds of 'position is bad') -----------------------
    prior_logit: float = -3.0              # L = 0  -> trust ~ 0.95
    tau_s: float = 150.0                   # leak time constant of track evidence
    l_floor: float = -1.5                  # cap on accumulated 'good' evidence
    l_cap: float = 9.0
    per_report_cap: float = 7.0
    trusted_enter: float = 0.7             # state thresholds with hysteresis
    trusted_exit: float = 0.6
    distrust_enter: float = 0.3
    distrust_exit: float = 0.4

    # --- plausibility ----------------------------------------------------------------
    gap_reset_s: float = 300.0             # longer gaps reset per-source kinematic memory
    baseline_s: float = 20.0               # displacement-vs-speed baseline
    speed_tol_frac: float = 0.3
    course_tol_deg: float = 70.0
    stale_s: float = 90.0                  # report older than engine clock by this => stale
    flatline_n: int = 5
    flatline_min_speed: float = 1.0

    # --- cross-source ------------------------------------------------------------------
    z_start: float = 3.5                   # z (disagreement / combined sigma) where evidence begins
    max_age_s: float = 40.0                # max age of the partner report used for comparison
    assoc_gate_m: float = 1500.0           # proximity association gate (single-source ids)
    proximity_assoc: bool = True
    assoc_min_age_s: float = 60.0          # a track must stay single-source this long before proximity association
    agree_z: float = 2.0

    # --- circle signature ----------------------------------------------------------------
    circle_min_pts: int = 10
    circle_window: int = 40
    circle_horizon_s: float = 420.0
    circle_min_span_s: float = 60.0
    circle_r_min_m: float = 25.0
    circle_r_max_m: float = 600.0
    circle_min_arc_deg: float = 150.0
    circle_speed_ratio: float = 1.8

    # --- source-level common mode -----------------------------------------------------------
    cm_min_offset_m: float = 500.0         # minimum common displacement to consider
    cm_min_tracks: int = 4
    cm_min_frac: float = 0.2               # fraction of fresh paired tracks that must show it
    cm_fresh_s: float = 180.0
    cm_coherence: float = 0.2              # dispersion / |mean offset| bound
    cm_eval_every_s: float = 5.0
    cm_clear_after_s: float = 300.0
    source_penalty: float = 4.5            # log-odds penalty applied to all of a flagged source's tracks
    verified_factor: float = 0.4           # penalty multiplier for tracks verified clean by another source
    # source name fragments treated as independent of GNSS (not spoofable the same way)
    independent_hints: tuple = ("radar", "eo", "optical", "sar", "lidar", "sonar", "ir-")
    source_classes: dict = field(default_factory=dict)   # explicit {source: 'independent'|'cooperative'}

    # --- bounded memory -----------------------------------------------------------------------
    max_tracks: int = 5000
    track_ttl_s: float = 1800.0
    pair_table_max: int = 1024
    reasons_kept: int = 24
    reasons_shown: int = 6

    def with_(self, **kw) -> "TrackConfig":
        return replace(self, **kw)
