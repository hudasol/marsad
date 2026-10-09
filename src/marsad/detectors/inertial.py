"""Inertial/reference detector: GNSS displacement vs independently integrated reference velocity.

This is the detector that sees carry-off spoofing. A spoofer that drags the receiver away slowly
can stay below innovation gates (an EKF absorbs slow drift), but it cannot move the vehicle's
visual/optical-flow/odometry reference. For each window W:

    d_W = (p_gnss(t) - p_gnss(t-W)) - (c(t) - c(t-W)),   c = integral of reference velocity

Under nominal conditions |d_W| is bounded by GNSS noise, reference white noise and reference bias*W.
The ratio of |d_W| to that bound is a z-score; sustained z above the threshold accrues drift evidence.
Detectability floor: a drift slower than ~ref_bias_bound m/s cannot be separated from reference bias.
"""
from __future__ import annotations
import bisect
import math
from ..geo import clamp
from ..types import Evidence, Hypothesis as H
from ..config import EngineConfig
from .base import Context


class InertialDetector:
    name = "inertial"

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.ts: list[float] = []
        self.rows: list[tuple] = []     # (pe-ce, pn-cn)
        self.last_z = 0.0
        self.last_z_short = 0.0
        self.last_mag = 0.0

    def learn(self, ctx: Context) -> None:
        pass

    def reset(self) -> None:
        self.ts.clear(); self.rows.clear()

    def _prune(self, t: float) -> None:
        horizon = max(self.cfg.drift_windows) * 1.6
        if len(self.ts) > 4000 and t - self.ts[0] > horizon:
            k = bisect.bisect_left(self.ts, t - horizon)
            del self.ts[:k]; del self.rows[:k]

    def update(self, ctx: Context) -> list[Evidence]:
        out: list[Evidence] = []
        g, c = ctx.gnss, self.cfg
        self.last_z = 0.0
        self.last_z_short = 0.0
        if g is None or not ctx.ref_ok:
            return out
        self.ts.append(ctx.t)
        self.rows.append((ctx.pe - ctx.ce, ctx.pn - ctx.cn))
        self._prune(ctx.t)
        cur = self.rows[-1]
        best_rate, best_msg, best_mag, best_z = 0.0, "", 0.0, 0.0
        for W in c.drift_windows:
            k = bisect.bisect_left(self.ts, ctx.t - W)
            if k >= len(self.ts) - 1:
                continue
            t0 = self.ts[k]
            Weff = ctx.t - t0
            if Weff < 0.8 * W or Weff > 1.6 * W or t0 < ctx.ref_valid_since:
                continue
            r0 = self.rows[k]
            mag = math.hypot(cur[0] - r0[0], cur[1] - r0[1])
            allowed = math.sqrt(
                (2.0 * c.sigma_pos) ** 2 * 2
                + (ctx.ref_noise_eff * math.sqrt(Weff * max(ctx.dt, 0.05))) ** 2
                + (ctx.ref_bias_eff * Weff) ** 2)
            z = mag / allowed
            rate = clamp(1.6 * (z - c.drift_z0), -0.3, 4.0)
            if z > best_z:
                best_z, best_mag = z, mag
            if W <= 15.0:
                self.last_z_short = max(self.last_z_short, z)
            if rate > best_rate:
                best_rate = rate
                best_msg = (f"GNSS moved {mag:.1f} m away from reference-integrated motion over "
                            f"{Weff:.0f} s ({z:.1f}x the nominal bound)")
        self.last_z = best_z
        self.last_mag = best_mag
        if best_rate > 0:
            r = best_rate * ctx.dt
            out.append(Evidence(self.name, "gnss_vs_reference_drift",
                                {H.SPOOF_DRIFT: r, H.SPOOF_JUMP: 0.4 * r, H.REPLAY: 0.3 * r},
                                best_msg, best_mag, r))
        elif best_z < 1.0 and best_z > 0:
            out.append(Evidence(self.name, "gnss_matches_reference", {H.SPOOF_DRIFT: -0.15 * ctx.dt,
                                                                      H.SPOOF_JUMP: -0.1 * ctx.dt},
                                "GNSS motion agrees with independent reference", best_z, 0.0))
        return out
