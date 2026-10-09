"""Kinematic detector: position innovation vs velocity-propagated prediction, implied speed,
and position/velocity self-consistency over a short window."""
from __future__ import annotations
import math
from ..geo import clamp
from ..types import Evidence, Hypothesis as H
from ..config import EngineConfig
from .base import Context


class KinematicDetector:
    name = "kinematic"

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self._prev = None            # (t, e, n, ve, vn)
        self._win = []               # (t, e, n, cum_ve, cum_vn) for pos-vs-vel consistency
        self._cum = [0.0, 0.0]
        self._xe = 0.0               # EWMA of normalised innovation (noise inflation => degraded/jammed receiver)
        self._last_jump = None       # (t, res_e, res_n, llr) for revert (multipath spike) detection

    def learn(self, ctx: Context) -> None:  # no learned baselines
        pass

    def update(self, ctx: Context) -> list[Evidence]:
        g, c, out = ctx.gnss, self.cfg, []
        if g is None:
            return out
        have_v = g.ve is not None and g.vn is not None
        prev = self._prev
        if prev is not None and ctx.t - prev[0] <= 2.0 and ctx.t > prev[0]:
            dt = ctx.t - prev[0]
            if have_v and prev[3] is not None:
                pe = prev[1] + 0.5 * (prev[3] + g.ve) * dt
                pn = prev[2] + 0.5 * (prev[4] + g.vn) * dt
            else:
                pe, pn = prev[1], prev[2]
            res = math.hypot(ctx.pe - pe, ctx.pn - pn)
            allowed = math.sqrt(2.0) * c.sigma_pos + 0.5 * c.a_max * dt * dt + c.v_max * dt * (0.0 if have_v else 0.5)
            x = res / allowed
            self._xe += min(1.0, dt / 2.0) * (min(x, 6.0) - self._xe)
            if self._xe > 1.2:
                r = 1.5 * min(2.0, self._xe - 1.2) * dt
                out.append(Evidence(self.name, "noise_inflation", {H.JAM: r, H.ENV: r},
                                    f"GNSS position noise inflated ({self._xe:.1f}x nominal innovation)", self._xe, r))
            llr = clamp(0.9 * (x - c.jump_x0), -0.1, 8.0)
            disp = math.hypot(ctx.pe - prev[1], ctx.pn - prev[2])
            speed = disp / dt
            if llr > 0.05:
                re_, rn_ = ctx.pe - pe, ctx.pn - pn
                lj = self._last_jump
                if (lj is not None and ctx.t - lj[0] <= 4.0 and re_ * lj[1] + rn_ * lj[2] < 0
                        and math.hypot(re_ + lj[1], rn_ + lj[2]) < 0.6 * math.hypot(lj[1], lj[2])):
                    # the position snapped back: a transient excursion (multipath), not a takeover
                    c_ = -(lj[3] + llr)
                    out.append(Evidence(self.name, "jump_reverted", {H.SPOOF_JUMP: c_, H.REPLAY: 0.5 * c_},
                                        "position excursion reverted within seconds (multipath-like, not takeover)", res, 0.0))
                    self._last_jump = None
                else:
                    out.append(Evidence(self.name, "position_jump", {H.SPOOF_JUMP: llr, H.REPLAY: 0.5 * llr},
                                        f"position innovation {res:.1f} m vs {allowed:.1f} m allowed", res, llr))
                    self._last_jump = (ctx.t, re_, rn_, llr)
            if disp > 1.5 * c.v_max * dt + 5.0 * math.sqrt(2.0) * c.sigma_pos:
                out.append(Evidence(self.name, "implied_speed", {H.SPOOF_JUMP: 4.0, H.REPLAY: 2.0},
                                    f"implied speed {speed:.0f} m/s exceeds platform envelope", speed, 4.0))
        # --- pos/vel self-consistency over ~10 s window ----------------------
        if have_v:
            if self._prev is not None and 0 < ctx.t - self._prev[0] <= 2.0:
                dt = ctx.t - self._prev[0]
                self._cum[0] += 0.5 * (self._prev[3] + g.ve) * dt if self._prev[3] is not None else g.ve * dt
                self._cum[1] += 0.5 * (self._prev[4] + g.vn) * dt if self._prev[4] is not None else g.vn * dt
            self._win.append((ctx.t, ctx.pe, ctx.pn, self._cum[0], self._cum[1]))
            while self._win and ctx.t - self._win[0][0] > 12.0:
                self._win.pop(0)
            w0 = self._win[0]
            W = ctx.t - w0[0]
            if W >= 8.0:
                de = (ctx.pe - w0[1]) - (self._cum[0] - w0[3])
                dn = (ctx.pn - w0[2]) - (self._cum[1] - w0[4])
                mag = math.hypot(de, dn)
                allowed = 3.0 * (math.sqrt(2) * c.sigma_pos + c.sigma_vel * W)
                z = mag / allowed
                r = clamp(2.0 * (z - 1.0), -0.2, 3.0) * ctx.dt
                if r > 0.01:
                    out.append(Evidence(self.name, "pos_vel_inconsistent",
                                        {H.SPOOF_DRIFT: r, H.SPOOF_JUMP: 0.5 * r},
                                        f"position moved {mag:.1f} m more than reported velocity explains over {W:.0f} s",
                                        mag, r))
        self._prev = (ctx.t, ctx.pe, ctx.pn, g.ve if have_v else None, g.vn if have_v else None)
        return out
