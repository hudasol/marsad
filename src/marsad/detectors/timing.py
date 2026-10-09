"""Timing detector: step changes / non-monotonic behaviour of GNSS time against the host clock."""
from __future__ import annotations
from ..types import Evidence, Hypothesis as H
from ..config import EngineConfig
from .base import Context


class TimingDetector:
    name = "timing"

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self._off = None
        self._last_tg = None

    def learn(self, ctx: Context) -> None:
        g = ctx.gnss
        if g is None or g.t_gnss is None:
            return
        off = g.t - g.t_gnss
        self._off = off if self._off is None else self._off + 0.02 * (off - self._off)

    def update(self, ctx: Context) -> list[Evidence]:
        g, out = ctx.gnss, []
        if g is None or g.t_gnss is None:
            return out
        if self._last_tg is not None and g.t_gnss <= self._last_tg:
            out.append(Evidence(self.name, "time_non_monotonic", {H.REPLAY: 3.0, H.SPOOF_JUMP: 1.5},
                                "GNSS time did not advance (stale or replayed data)", g.t_gnss - self._last_tg, 3.0))
        self._last_tg = g.t_gnss
        if self._off is None:
            self._off = g.t - g.t_gnss
            return out
        step = (g.t - g.t_gnss) - self._off
        if abs(step) > self.cfg.clock_step_s:
            llr = min(6.0, 2.0 + abs(step) / self.cfg.clock_step_s)
            out.append(Evidence(self.name, "clock_step", {H.REPLAY: llr, H.SPOOF_JUMP: llr},
                                f"GNSS clock stepped {step:+.2f} s against the host clock", step, llr))
        return out
