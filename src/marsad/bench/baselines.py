"""Reference detectors the engine is compared against.

Every class here has the same interface, ``update(sample) -> (TrustState, (east, north) | None)``, and reads the
same ``NavSample`` stream (and the same independent velocity reference) as the trust engine, so a comparison
isolates the detection logic and not the sensor.

* ``GateBaseline``     simplified autopilot style gate (the original baseline, unchanged).
* ``Ekf2Gate``         PX4 EKF2 style GNSS fusion gate: a position filter, 5 sigma position and velocity innovation
                       gates, reset to GNSS after 7 s of rejection. ``use_reference=False`` is the autopilot as
                       flown (its own velocity follows the receiver); ``True`` also gives it the independent reference.
* ``WindowConsistency`` INS/GNSS displacement consistency test over a sliding window (chi square style).
* ``SignalMonitor``    receiver level power monitoring (AGC and C/N0 steps), as in commercial receivers.
* ``AnyOf``            logical OR of several detectors.

None of these is PX4 or ArduPilot code; see docs/BASELINES.md for what each reproduces and what it does not.
"""
from __future__ import annotations
import math
from collections import deque
from typing import Optional
from ..geo import LocalFrame
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


class _Motion:
    """Local frame and the integral of the velocity used to propagate a position.

    The propagation velocity is the independent reference when ``use_ref`` is set and a reference sample is recent;
    otherwise it is the last accepted receiver velocity (what an autopilot without an external aiding sensor has).
    """

    def __init__(self, use_ref=True, ref_max_age=1.0):
        self.use_ref, self.max_age = use_ref, ref_max_age
        self.frame: Optional[LocalFrame] = None
        self.t: Optional[float] = None
        self.v_ref: Optional[tuple] = None
        self.v_ref_t = -1e9
        self.v_gnss = (0.0, 0.0)
        self.ce = self.cn = 0.0
        self.anchor: Optional[tuple] = None
        self.vel = (0.0, 0.0)

    def feed(self, s: NavSample, max_gap=2.0):
        """Integrate the current propagation velocity up to s.t; returns the step taken."""
        dt = 0.0
        if self.t is not None and 0 < s.t - self.t < max_gap:
            dt = s.t - self.t
            self.ce += self.vel[0] * dt
            self.cn += self.vel[1] * dt
        self.t = s.t
        if s.ref is not None:
            self.v_ref, self.v_ref_t = (s.ref.ve, s.ref.vn), s.t
        if self.use_ref and self.v_ref is not None and s.t - self.v_ref_t <= self.max_age:
            self.vel = self.v_ref
        else:
            self.vel = self.v_gnss
        return dt

    def accept_velocity(self, g):
        if g.ve is not None and g.vn is not None:
            self.v_gnss = (g.ve, g.vn)

    def local(self, g):
        if self.frame is None:
            self.frame = LocalFrame(g.lat, g.lon)
        return self.frame.to_local(g.lat, g.lon)

    def accept(self, e, n):
        self.anchor = (e - self.ce, n - self.cn)

    def fallback(self):
        return None if self.anchor is None else (self.ce + self.anchor[0], self.cn + self.anchor[1])


def _usable(s: NavSample, min_sats: int):
    g = s.gnss
    if g is None or g.fix_type < 3:
        return None
    if g.n_sats is not None and g.n_sats < min_sats:
        return None
    return g


class Ekf2Gate:
    """PX4 EKF2 style GNSS fusion gate.

    Reproduces the logic that decides whether an autopilot keeps fusing GNSS, using documented defaults:
    ``EKF2_GPS_P_GATE`` = 5.0 and ``EKF2_GPS_V_GATE`` = 5.0 standard deviations, ``EKF2_REQ_NSATS`` = 6,
    ``EKF2_GPS_V_NOISE`` = 0.3 m/s, and the 7 s ``reset_timeout_max`` after which the estimator resets its position
    to the GNSS fix. A 2D position filter is propagated with a velocity; each fix is gated on the position
    innovation and on the velocity innovation, and a rejected fix is not fused. This reimplements the gating idea,
    not the EKF2 code: there is no attitude, no IMU and no bias states.

    ``use_reference=False`` is the autopilot as flown: the propagation velocity follows the receiver (in EKF2 the
    velocity state is corrected by the GNSS velocity), so a spoofer that moves position and velocity together is
    absorbed. ``use_reference=True`` gives the filter the same independent velocity Marsad reads, which is the
    strongest version of this idea that needs no new algorithm.

    ``pos_noise`` is not a PX4 default; it is calibrated on nominal dev scenarios (scripts/calibrate_baselines.py).
    """

    def __init__(self, use_reference=False, pos_noise=1.9, vel_noise=0.3, gate_p=5.0, gate_v=5.0, min_sats=6,
                 reset_timeout_s=7.0, noaid_timeout_s=5.0, vel_walk=0.1, ref_sigma=0.15):
        self.use_ref = use_reference
        self.R, self.Rv, self.gp, self.gv = pos_noise ** 2, vel_noise ** 2, gate_p, gate_v
        self.min_sats, self.reset_to, self.noaid_to = min_sats, reset_timeout_s, noaid_timeout_s
        self.q, self.ref_sigma = vel_walk ** 2, ref_sigma
        self.mo = _Motion(use_reference)
        self.p = None                # filter position (e, n)
        self.P = 0.0
        self.last_accept_t: Optional[float] = None
        self.last_fix_t: Optional[float] = None
        self.rejecting = False
        self.state = TrustState.TRUSTED

    def update(self, s: NavSample):
        dt = self.mo.feed(s)
        if self.p is not None and dt > 0:
            self.p = (self.p[0] + self.mo.vel[0] * dt, self.p[1] + self.mo.vel[1] * dt)
            self.P += self.q * dt
        g = _usable(s, self.min_sats)
        if g is not None:
            self.last_fix_t = s.t
            e, n = self.mo.local(g)
            if self.p is None:
                self.p, self.P, self.last_accept_t = (e, n), self.R, s.t
                self.mo.accept(e, n)
                self.mo.accept_velocity(g)
            else:
                S = self.P + self.R
                ie, in_ = e - self.p[0], n - self.p[1]
                ok = max(ie * ie, in_ * in_) <= (self.gp ** 2) * S
                if ok and g.ve is not None and g.vn is not None:
                    sv = self.Rv + (self.ref_sigma ** 2 if self.use_ref else 0.0) + 0.25   # 0.25: manoeuvre allowance
                    ok = max((g.ve - self.mo.vel[0]) ** 2, (g.vn - self.mo.vel[1]) ** 2) <= (self.gv ** 2) * sv
                if ok:
                    k = self.P / S
                    self.p = (self.p[0] + k * ie, self.p[1] + k * in_)
                    self.P *= (1 - k)
                    self.last_accept_t, self.rejecting = s.t, False
                    self.mo.accept(*self.p)
                    self.mo.accept_velocity(g)
                else:
                    self.rejecting = True
                    if s.t - self.last_accept_t > self.reset_to:      # the estimator resets to the GNSS fix
                        self.p, self.P, self.last_accept_t = (e, n), self.R, s.t
                        self.rejecting = False
                        self.mo.accept(e, n)
                        self.mo.accept_velocity(g)
        stale = self.last_fix_t is None or s.t - self.last_fix_t > self.noaid_to
        if self.rejecting or stale:
            self.state = TrustState.DENIED
            return self.state, self.mo.fallback()
        self.state = TrustState.TRUSTED
        return self.state, self.p


class WindowConsistency:
    """Displacement consistency between GNSS and the integrated velocity over a sliding window.

    D = (GNSS position now - GNSS position one window ago) - (integral of the velocity over the same interval).
    The velocity is the independent reference when one is present and the receiver velocity otherwise. Without an
    attack D is the sum of GNSS noise and velocity bias times the window length. The test alarms when |D| exceeds
    ``z`` combined standard deviations plus the largest reference bias the sensor is allowed (``bias_bound`` times
    the window). This is the classic INS versus GNSS position difference test; unlike the trust engine it has no
    bias estimator and no multi hypothesis reasoning.

    ``pos_noise`` is calibrated on nominal dev scenarios; ``bias_bound`` is the bound documented for the simulated
    reference (0.08 m/s on the held out split).
    """

    def __init__(self, window_s=60.0, pos_noise=1.3, z=4.3, bias_bound=0.08, ref_sigma=0.15, min_sats=6,
                 deny_after_s=5.0, sample_dt=0.2):
        self.W, self.sg, self.z, self.b = window_s, pos_noise, z, bias_bound
        self.ref_sigma, self.min_sats, self.deny_after, self.sdt = ref_sigma, min_sats, deny_after_s, sample_dt
        self.mo = _Motion(True)
        self.hist: deque = deque()   # (t, e, n, ce, cn) at each usable fix
        self.last_fix_t: Optional[float] = None
        self.alarm = False
        self.state = TrustState.TRUSTED

    def update(self, s: NavSample):
        self.mo.feed(s)
        g = _usable(s, self.min_sats)
        pos = None
        if g is not None:
            if self.last_fix_t is not None and s.t - self.last_fix_t > self.deny_after:
                self.hist.clear()     # a long outage breaks the displacement chain
            self.last_fix_t = s.t
            self.mo.accept_velocity(g)
            e, n = self.mo.local(g)
            pos = (e, n)
            self.hist.append((s.t, e, n, self.mo.ce, self.mo.cn))
            while len(self.hist) > 1 and self.hist[1][0] <= s.t - self.W:
                self.hist.popleft()
            t0, e0, n0, ce0, cn0 = self.hist[0]
            span = s.t - t0
            if span >= 0.5 * self.W:
                d = math.hypot((e - e0) - (self.mo.ce - ce0), (n - n0) - (self.mo.cn - cn0))
                sd = math.sqrt(2 * self.sg ** 2 + (self.ref_sigma ** 2) * span * self.sdt)
                self.alarm = d > self.z * sd + self.b * span
            if not self.alarm:
                self.mo.accept(e, n)
        stale = self.last_fix_t is None or s.t - self.last_fix_t > self.deny_after
        if self.alarm or stale:
            self.state = TrustState.DENIED
            return self.state, self.mo.fallback()
        self.state = TrustState.TRUSTED
        return self.state, pos


class SignalMonitor:
    """Receiver level power monitoring: step changes of AGC and mean C/N0 against their own running average.

    Commercial receivers expose jamming indicators built the same way (an AGC or noise floor rise, a C/N0 drop).
    A spoofer that matches the genuine power level, or ramps it slowly, passes this check; that is the point of
    including it. Thresholds are 1.5 times the largest deviation seen on nominal dev scenarios
    (scripts/calibrate_baselines.py). The running average is initialised over the first ``warm_s`` seconds.
    """

    def __init__(self, agc_step=0.077, cn0_step=3.5, tau_s=120.0, hold_s=10.0, min_sats=4, warm_s=10.0):
        self.agc_step, self.cn0_step, self.tau, self.hold, self.min_sats = agc_step, cn0_step, tau_s, hold_s, min_sats
        self.warm = warm_s
        self.t0: Optional[float] = None
        self.m_agc: Optional[float] = None
        self.m_cn0: Optional[float] = None
        self.n_warm = 0
        self.t_prev: Optional[float] = None
        self.until = -1.0
        self.mo = _Motion(True)
        self.state = TrustState.TRUSTED

    def update(self, s: NavSample):
        self.mo.feed(s)
        g = s.gnss
        pos = None
        if g is not None:
            self.mo.accept_velocity(g)
            flagged = g.fix_type < 3 or (g.n_sats is not None and g.n_sats < self.min_sats)
            if not flagged:
                pos = self.mo.local(g)
            if self.t0 is None:
                self.t0 = s.t
            dt = 0.0 if self.t_prev is None else min(s.t - self.t_prev, 5.0)
            self.t_prev = s.t
            warming = s.t - self.t0 < self.warm
            for name, val, step in (("m_agc", g.agc, self.agc_step), ("m_cn0", g.cn0_mean, self.cn0_step)):
                if val is None:
                    continue
                cur = getattr(self, name)
                if cur is None:
                    setattr(self, name, val)
                elif warming:
                    setattr(self, name, cur + (val - cur) / (self.n_warm + 1))
                else:
                    if abs(val - cur) > step:
                        flagged = True
                    elif not flagged:
                        setattr(self, name, cur + min(1.0, dt / self.tau) * (val - cur))
            self.n_warm += 1 if warming else 0
            if flagged:
                self.until = s.t + self.hold
            elif pos is not None and s.t >= self.until:
                self.mo.accept(*pos)
        if s.t < self.until:
            self.state = TrustState.DENIED
            return self.state, self.mo.fallback()
        self.state = TrustState.TRUSTED
        return self.state, pos


class AnyOf:
    """Alarm when any member alarms (what an integrator gets by stacking every check)."""

    def __init__(self, *members):
        self.members = members
        self.state = TrustState.TRUSTED

    def update(self, s: NavSample):
        outs = [m.update(s) for m in self.members]
        bad = [o for o in outs if o[0] != TrustState.TRUSTED]
        if bad:
            self.state = TrustState.DENIED
            return self.state, next((o[1] for o in bad if o[1] is not None), None)
        self.state = TrustState.TRUSTED
        return self.state, outs[0][1]


def make_baselines() -> dict:
    """Fresh instance of every baseline, keyed by the name used in docs/BASELINES.md."""
    return {
        "gate": GateBaseline(),
        "ekf2_gate": Ekf2Gate(use_reference=False),
        "ekf2_gate_ref": Ekf2Gate(use_reference=True),
        "window": WindowConsistency(),
        "signal": SignalMonitor(),
        "stack": AnyOf(Ekf2Gate(use_reference=True), WindowConsistency(), SignalMonitor()),
    }
