"""Baseline: a simplified autopilot-style GNSS health gate (NOT PX4 itself).

It stands in for what a typical stack does today: fix-quality checks (fix type, satellite count),
a position-innovation gate against velocity-propagated prediction, a latch after a failure, and
dead-reckoning on the same reference sensor during the latch. It uses the same reference sensor
as Marsad so the comparison isolates the detection logic, not the sensor.
"""
from __future__ import annotations
import math
from ..types import NavSample, TrustState


class GateBaseline:
    def __init__(self, sigma_pos=2.0, gate_sigmas=5.0, min_sats=6, latch_s=10.0, gap_s=2.0, a_max=8.0):
        self.sp, self.gs, self.min_sats, self.latch, self.gap, self.a_max = sigma_pos, gate_sigmas, min_sats, latch_s, gap_s, a_max
        self.frame = None
        self.prev = None
        self.ce = self.cn = 0.0
        self.ref_t = None
        self.acc = None           # (pos_e - ce, pos_n - cn) at last accepted fix
        self.latch_until = -1.0
        self.last_fix_t = None
        self.state = TrustState.TRUSTED

    def update(self, s: NavSample):
        from ..geo import LocalFrame
        t = s.t
        if s.ref is not None:
            if self.ref_t is not None and t - self.ref_t < 2.0:
                self.ce += s.ref.ve * (t - self.ref_t); self.cn += s.ref.vn * (t - self.ref_t)
            self.ref_t = t
        g = s.gnss if (s.gnss is not None and s.gnss.fix_type >= 3) else None
        pos = None
        if g is not None:
            if self.frame is None:
                self.frame = LocalFrame(g.lat, g.lon)
            e, n = self.frame.to_local(g.lat, g.lon)
            self.last_fix_t = t
            ok = (g.n_sats is None or g.n_sats >= self.min_sats)
            if self.prev is not None and 0 < t - self.prev[0] <= 2.0:
                dt = t - self.prev[0]
                pe = self.prev[1] + (g.ve or 0.0) * dt
                pn = self.prev[2] + (g.vn or 0.0) * dt
                gate = self.gs * self.sp + 0.5 * self.a_max * dt * dt + 0.5 * dt
                if math.hypot(e - pe, n - pn) > gate:
                    ok = False
            self.prev = (t, e, n)
            if not ok:
                self.latch_until = t + self.latch
            pos = (e, n)
        lost = self.last_fix_t is None or (t - self.last_fix_t) > self.gap
        latched = t < self.latch_until
        if lost or latched:
            self.state = TrustState.DENIED
            if self.acc is not None:
                return self.state, (self.ce + self.acc[0], self.cn + self.acc[1])
            return self.state, pos
        self.state = TrustState.TRUSTED
        if pos is not None:
            self.acc = (pos[0] - self.ce, pos[1] - self.cn)
        return self.state, pos
