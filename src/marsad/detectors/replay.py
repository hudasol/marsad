"""Replay/meaconing discriminator: is the GNSS velocity history a *delayed copy* of the reference history?

A replayed (meaconed) signal re-broadcasts genuine, earlier GNSS data, so the reported velocities are real
vehicle velocities -- from `lag` seconds ago. After the takeover instant the position offset looks like any
other jump, but the velocity *time series* gives it away: it correlates with the independent reference
velocity at a positive lag, and much less at lag zero. Needs the vehicle to manoeuvre (velocity variance)
and an independent reference. Emits REPLAY evidence and *negative* SPOOF_JUMP evidence (replay explains the jump).
"""
from __future__ import annotations
import math
from ..types import Evidence, Hypothesis as H
from ..config import EngineConfig
from .base import Context


class ReplayDetector:
    name = "replay"
    WIN = 30           # s of GNSS history compared
    LMAX = 260         # s, maximum lag searched
    LMIN = 8           # s, smallest lag treated as a replay
    EVERY = 5          # s between evaluations
    MIN_STD = 0.5      # m/s, minimum reference velocity variation for the test to mean anything

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.reset()
        self.lag = None            # last confirmed lag (s) or None
        self.last_corr = (0.0, 0.0)

    def reset(self) -> None:
        self._bin = None
        self._acc = [0.0, 0.0, 0, 0.0, 0.0, 0]      # sum ref e,n,count; sum gnss e,n,count
        self._G: list = []                            # per-second (ge, gn) or None
        self._R: list = []
        self._next_eval = None
        self.lag = None
        self._lags = []
        self._clear = 0

    def learn(self, ctx: Context) -> None:
        pass

    def _push(self):
        a = self._acc
        self._R.append((a[0] / a[2], a[1] / a[2]) if a[2] else None)
        self._G.append((a[3] / a[5], a[4] / a[5]) if a[5] else None)
        if len(self._R) > self.WIN + self.LMAX + 10:
            del self._R[0]; del self._G[0]
        self._acc = [0.0, 0.0, 0, 0.0, 0.0, 0]

    @staticmethod
    def _corr(g, r):
        pts = [(a, b) for a, b in zip(g, r) if a is not None and b is not None]
        n = len(pts)
        if n < 15:
            return None, 0.0
        mg = [sum(p[0][i] for p in pts) / n for i in (0, 1)]
        mr = [sum(p[1][i] for p in pts) / n for i in (0, 1)]
        sgr = sgg = srr = 0.0
        for a, b in pts:
            for i in (0, 1):
                x, y = a[i] - mg[i], b[i] - mr[i]
                sgr += x * y; sgg += x * x; srr += y * y
        if sgg <= 1e-9 or srr <= 1e-9:
            return None, 0.0
        return sgr / math.sqrt(sgg * srr), math.sqrt(srr / (2 * n))

    def update(self, ctx: Context) -> list[Evidence]:
        t = ctx.t
        b = int(t)
        if self._bin is None:
            self._bin = b
        while self._bin < b:
            self._push(); self._bin += 1
        g = ctx.gnss
        if ctx.ref is not None:
            self._acc[0] += ctx.ref.ve; self._acc[1] += ctx.ref.vn; self._acc[2] += 1
        if g is not None and g.ve is not None and g.vn is not None:
            self._acc[3] += g.ve; self._acc[4] += g.vn; self._acc[5] += 1
        if self._next_eval is None:
            self._next_eval = t + self.WIN
        if t < self._next_eval or len(self._G) < self.WIN + self.LMIN:
            return []
        self._next_eval = t + self.EVERY
        Gw = self._G[-self.WIN:]
        n = len(self._R)
        best, best_l = -2.0, None
        cs = {}
        c0 = None
        std0 = 0.0
        for L in range(0, min(self.LMAX, n - self.WIN) + 1):
            Rw = self._R[n - self.WIN - L: n - L]
            c, sd = self._corr(Gw, Rw)
            if c is None:
                continue
            if L == 0:
                c0, std0 = c, sd
            cs[L] = c
            if c > best:
                best, best_l = c, L
        if best_l is not None:      # prefer the smallest lag that is essentially as good (periodic motion aliases)
            best_l = best_l
        if c0 is None:
            self.last_corr = (0.0, 0.0)
            return []
        self.last_corr = (c0, best)
        if std0 < self.MIN_STD:
            return []        # not enough manoeuvring to say anything either way
        if best_l is not None and best_l >= self.LMIN and best >= 0.9 and c0 <= best - 0.3:
            self._lags = (self._lags + [best_l])[-40:]
            # mode (+/-2 s buckets) of the confirmed lags: robust to aliasing glitches from periodic manoeuvres
            self.lag = float(max(self._lags, key=lambda a: sum(abs(a - b) <= 2 for b in self._lags)))
            return [Evidence(self.name, "delayed_copy",
                             {H.REPLAY: 3.0, H.SPOOF_JUMP: -1.5, H.SPOOF_DRIFT: -0.5},
                             f"GNSS velocity history matches the reference delayed by {best_l} s "
                             f"(r={best:.2f} vs r={c0:.2f} at zero lag): replayed signal", float(best_l), 3.0)]
        if c0 >= 0.9 and best - c0 < 0.05:
            self._clear += 1
            if self._clear >= 3:       # three consecutive evaluations that look genuinely live
                self.lag = None
                self._lags = []
        else:
            self._clear = 0
        return []
