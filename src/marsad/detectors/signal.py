"""Signal-level detector: C/N0 level and spread, satellite count, AGC, fix loss.

Separates 'GNSS is degraded' (obstruction/multipath: C/N0 and satellites fall, AGC flat)
from 'GNSS is jammed' (C/N0 falls AND AGC rises) and flags the spoofing power signature
(C/N0 rises, spread across satellites collapses).
"""
from __future__ import annotations
from ..geo import clamp
from ..types import Evidence, Hypothesis as H
from ..config import EngineConfig
from .base import Context


class SignalDetector:
    name = "signal"

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.cn0_b = cfg.cn0_prior
        self.sd_b = cfg.cn0_std_prior
        self.nsat_b = cfg.nsat_prior
        self.agc_b = None
        self._n = 0

    def learn(self, ctx: Context) -> None:
        g = ctx.gnss
        if g is None:
            return
        self._n += 1
        a = 1.0 / min(self._n, 300)  # fast at first, then ~60 s at 5 Hz
        a = max(a, 0.003)
        if g.cn0_mean is not None:
            self.cn0_b += a * (g.cn0_mean - self.cn0_b)
        if g.cn0_std is not None:
            self.sd_b += a * (g.cn0_std - self.sd_b)
        if g.n_sats is not None:
            self.nsat_b += a * (g.n_sats - self.nsat_b)
        if g.agc is not None:
            self.agc_b = g.agc if self.agc_b is None else self.agc_b + a * (g.agc - self.agc_b)

    def update(self, ctx: Context) -> list[Evidence]:
        c, dt, out = self.cfg, ctx.dt, []
        # --- loss of fix -----------------------------------------------------
        if ctx.gnss_gap > c.gnss_gap_timeout:
            r = 2.5 * dt
            out.append(Evidence(self.name, "fix_loss", {H.JAM: r, H.ENV: 0.8 * r},
                                f"no usable GNSS fix for {ctx.gnss_gap:.1f} s", ctx.gnss_gap, r))
        g = ctx.gnss
        if g is None:
            return out
        if self._n < 10:      # calibrating baselines from the first trusted fixes (assumes no attack at power-up)
            return out
        agc_known = g.agc is not None and self.agc_b is not None
        # --- power / satellites down: jamming vs environmental ----------------
        down = 0.0
        if g.cn0_mean is not None:
            drop = self.cn0_b - g.cn0_mean
            down = max(down, clamp((drop - c.cn0_drop_db) / 3.0, -0.2, 3.0))
        if g.n_sats is not None:
            dn = self.nsat_b - g.n_sats
            down = max(down, clamp((dn - 3.0) / 3.0, -0.2, 2.0))
        if down > 0:
            if agc_known:
                rise = g.agc - self.agc_b
                jam_share = clamp((rise - c.agc_rise) / c.agc_rise, 0.0, 1.0)
                out.append(Evidence(
                    self.name, "signal_down",
                    {H.JAM: 1.5 * down * jam_share * dt + (-0.1 * dt if jam_share == 0 else 0.0),
                     H.ENV: down * (1.0 - jam_share) * dt},
                    ("C/N0/satellites down with AGC "
                     + (f"up +{rise:.2f} (jamming signature)" if jam_share > 0.5 else "flat (obstruction-like)")),
                    down, down * dt))
            else:
                out.append(Evidence(self.name, "signal_down",
                                    {H.JAM: 0.5 * down * dt, H.ENV: down * dt},
                                    "C/N0/satellites down; no AGC available to separate jamming from obstruction",
                                    down, down * dt))
        elif down < 0:
            out.append(Evidence(self.name, "signal_ok", {H.JAM: down * dt * 0.5, H.ENV: down * dt * 0.5},
                                "signal quality nominal", down, 0.0))
        # --- jamming signature via AGC alone ---------------------------------
        if agc_known and g.agc - self.agc_b > 2 * c.agc_rise:
            r = clamp((g.agc - self.agc_b - c.agc_rise) / c.agc_rise, 0.0, 3.0) * dt
            out.append(Evidence(self.name, "agc_rise", {H.JAM: 1.5 * r},
                                f"AGC +{g.agc - self.agc_b:.2f} above baseline", g.agc - self.agc_b, r))
        # --- spoofing power signature ----------------------------------------
        sp = 0.0
        if g.cn0_mean is not None:
            rise = g.cn0_mean - self.cn0_b
            sp = max(sp, clamp((rise - c.cn0_rise_db) / 2.0, -0.1, 1.5))
        if g.cn0_std is not None and self.sd_b > 0:
            ratio = g.cn0_std / self.sd_b
            if ratio < 0.5 and (g.cn0_mean is None or g.cn0_mean - self.cn0_b > 0.5):
                sp = max(sp, 0.7)
        if sp > 0:
            r = 0.8 * sp * dt
            out.append(Evidence(self.name, "spoof_power_signature",
                                {H.SPOOF_JUMP: r, H.SPOOF_DRIFT: r, H.REPLAY: r},
                                "C/N0 above baseline with collapsed per-satellite spread (spoofer-like)",
                                sp, r))
        return out
