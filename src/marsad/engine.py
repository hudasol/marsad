"""TrustEngine: the vehicle-trust module. Streaming, O(log n) per sample, stdlib-only.

Feed NavSample objects in time order; get a TrustReport per sample.
"""
from __future__ import annotations
import bisect
import math
from typing import Optional

from .config import EngineConfig, preset
from .detectors import Context, SignalDetector, KinematicDetector, InertialDetector, TimingDetector
from .fusion import Fusion
from .geo import LocalFrame
from .types import (Evidence, Hypothesis as H, NavAction, NavSample, TrustReport, TrustState)

_ORDER = {TrustState.TRUSTED: 0, TrustState.DEGRADED: 1, TrustState.DENIED: 2}
_BY_ORDER = {v: k for k, v in _ORDER.items()}


class TrustEngine:
    def __init__(self, cfg: Optional[EngineConfig] = None, disable: Optional[set] = None):
        """disable: optional set of detector names ('signal','kinematic','inertial','timing') for ablations."""
        self.cfg = cfg or preset("uav_multirotor")
        self.signal = SignalDetector(self.cfg)
        self.kin = KinematicDetector(self.cfg)
        self.inertial = InertialDetector(self.cfg)
        self.timing = TimingDetector(self.cfg)
        self.detectors = [d for d in (self.signal, self.kin, self.inertial, self.timing)
                          if d.name not in (disable or set())]
        self.fusion = Fusion(self.cfg)
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.frame: Optional[LocalFrame] = None
        self.t0: Optional[float] = None
        self.t_last: Optional[float] = None
        self.state = TrustState.TRUSTED
        self.p_nom = 1.0
        self.probs = {H.NOMINAL.value: 1.0}
        # reference integration
        self.ref_t: Optional[float] = None
        self.ce = self.cn = 0.0
        self.ref_valid_since = -1e18
        # gnss bookkeeping
        self.fix_t: Optional[float] = None
        self.last_good = None      # (t, e, n) last position while TRUSTED
        # anchor: smoothed (p_gnss - c) while trusted, with history for rewind
        self.anchor = None         # (e, n) or None
        self.anchor_valid = False
        self._ah_t: list[float] = []
        self._ah: list[tuple] = []
        self.dr_t0 = 0.0
        self.last_clean_t = 0.0
        self.unverifiable = False
        # state machine timers
        self._entered_t = 0.0
        self._down_since: Optional[float] = None
        self._recent: list[tuple] = []
        self._spoof_hold_until = -1e18
        self._verified_since = None
        self._cut_done = False
        self.fusion.reset()
        self.inertial.reset()

    def acknowledge(self) -> None:
        """Operator override: accept current GNSS as trusted (e.g. after verifying by other means)."""
        self.state = TrustState.TRUSTED
        self.fusion.reset()
        self.anchor_valid = False
        self.unverifiable = False
        self._down_since = None

    # ------------------------------------------------------------- main step
    def update(self, s: NavSample) -> TrustReport:
        cfg, t = self.cfg, s.t
        if self.t0 is None:
            self.t0 = t
        dt = 0.0 if self.t_last is None else min(max(t - self.t_last, 0.0), 5.0)
        self.t_last = t

        g = s.gnss if (s.gnss is not None and s.gnss.fix_type >= 3) else None
        if g is not None and self.frame is None:
            self.frame = LocalFrame(g.lat, g.lon)
        pe = pn = 0.0
        if g is not None and self.frame is not None:
            pe, pn = self.frame.to_local(g.lat, g.lon)
            self.fix_t = t
        gap = 0.0 if (g is not None) else (t - self.fix_t if self.fix_t is not None else t - self.t0)

        # reference integration -------------------------------------------------
        if s.ref is not None:
            if self.ref_t is not None:
                dtr = t - self.ref_t
                if dtr > cfg.ref_timeout:
                    self.ref_valid_since = t
                    self.anchor_valid = False
                else:
                    self.ce += s.ref.ve * dtr
                    self.cn += s.ref.vn * dtr
            else:
                self.ref_valid_since = t
            self.ref_t = t
        ref_ok = self.ref_t is not None and (t - self.ref_t) <= cfg.ref_timeout
        if not ref_ok:
            self.anchor_valid = False

        warm = (t - self.t0) < cfg.warmup_s
        ctx = Context(t=t, dt=dt, gnss=g, ref=s.ref, pe=pe, pn=pn, ce=self.ce, cn=self.cn,
                      ref_ok=ref_ok, ref_valid_since=self.ref_valid_since, gnss_gap=gap,
                      state=self.state, p_nominal=self.p_nom, warmup=warm)

        ev: list[Evidence] = []
        for d in self.detectors:
            ev.extend(d.update(ctx))

        # persistent offset against dead-reckoned continuation (used while not trusted)
        offset_m = None
        dr = self._dead_reckon(t)
        if g is not None and dr is not None:
            offset_m = math.hypot(pe - dr[0], pn - dr[1])
        reacq_ok = self._reacquisition_ok(g, offset_m, t)
        if (self.state != TrustState.TRUSTED and offset_m is not None and not reacq_ok
                and not self.unverifiable):
            ev.append(Evidence("engine", "persistent_offset", {H.SPOOF_JUMP: 1.2 * dt, H.SPOOF_DRIFT: 0.6 * dt},
                               f"GNSS is {offset_m:.0f} m from the dead-reckoned continuation of the last trusted track",
                               offset_m, 1.2 * dt))

        verified = (self.state != TrustState.TRUSTED and g is not None and offset_m is not None and reacq_ok)
        if verified:
            if self._verified_since is None:
                self._verified_since = t
            elif t - self._verified_since >= 10.0 and not self._cut_done:
                self.inertial.reset()      # drop windows that straddle the (now resolved) event
                self._cut_done = True
        else:
            self._verified_since = None
            self._cut_done = False
        if verified and self.inertial.last_z_short < 1.0:
            r = -2.0 * dt   # independent proof of continuity with the dead-reckoned track
            ev.append(Evidence("engine", "verified_continuity",
                               {H.JAM: r, H.ENV: r, H.SPOOF_JUMP: r, H.SPOOF_DRIFT: r, H.REPLAY: r},
                               "GNSS agrees with the dead-reckoned continuation of the last trusted track",
                               offset_m, 0.0))
        self.probs = self.fusion.step(dt, ev)
        self.p_nom = self.probs[H.NOMINAL.value]

        prev_state = self.state
        self._advance_state(t, gap, reacq_ok)

        # learning / anchoring only from clean, trusted data ------------------
        if self.state == TrustState.TRUSTED and prev_state == TrustState.TRUSTED and self.p_nom > 0.9:
            for d in self.detectors:
                d.learn(ctx)
            if g is not None:
                self.last_good = (t, pe, pn)
                if ref_ok:
                    self._update_anchor(t, dt, pe - self.ce, pn - self.cn)
        if self.fusion.attack_onset_evidence() < 0.5 and self.state == TrustState.TRUSTED:
            self.last_clean_t = t
        if prev_state == TrustState.TRUSTED and self.state != TrustState.TRUSTED:
            self._freeze_anchor(t)

        return self._report(t, g, pe, pn, ev, offset_m, ref_ok, warm)

    # ----------------------------------------------------------------- helpers
    def _update_anchor(self, t, dt, oe, on):
        if self.anchor is None or not self.anchor_valid:
            self.anchor = (oe, on)
            self.anchor_valid = True
        else:
            a = min(1.0, dt / 10.0) if dt > 0 else 0.0
            self.anchor = (self.anchor[0] + a * (oe - self.anchor[0]),
                           self.anchor[1] + a * (on - self.anchor[1]))
        self._ah_t.append(t)
        self._ah.append(self.anchor)
        if len(self._ah_t) > 3000:
            del self._ah_t[:1000]; del self._ah[:1000]

    def _freeze_anchor(self, t):
        if not self.anchor_valid or not self._ah_t:
            self.dr_t0 = t
            return
        tr = self.last_clean_t - self.cfg.rewind_margin_s
        k = bisect.bisect_right(self._ah_t, tr) - 1
        k = max(0, k)
        self.anchor = self._ah[k]
        self.dr_t0 = self._ah_t[k]
        # stale history beyond the rewind point is contaminated; drop it
        del self._ah_t[k + 1:]; del self._ah[k + 1:]

    def _dead_reckon(self, t):
        if self.state == TrustState.TRUSTED and not self.anchor_valid:
            return None
        if not (self.anchor_valid and self.anchor is not None and self.ref_t is not None
                and t - self.ref_t <= self.cfg.ref_timeout):
            return None
        return (self.ce + self.anchor[0], self.cn + self.anchor[1])

    def _reacquisition_ok(self, g, offset_m, t) -> bool:
        cfg = self.cfg
        if g is None:
            return False
        if offset_m is None:
            self.unverifiable = False
            return True   # no reference: rely on signal + kinematic evidence decaying
        if self.state == TrustState.TRUSTED:
            return True
        dtt = max(t - self.dr_t0, 0.0)
        allowed = 3.0 * cfg.sigma_pos + 1.25 * cfg.ref_bias_bound * dtt
        if allowed > cfg.reacq_cap_m:
            self.unverifiable = True
            return False
        self.unverifiable = False
        return offset_m <= allowed

    def _advance_state(self, t, gap, reacq_ok):
        cfg, p = self.cfg, self.probs
        p_spoof = p[H.SPOOF_JUMP.value] + p[H.SPOOF_DRIFT.value] + p[H.REPLAY.value]
        lost = gap > cfg.gnss_gap_timeout
        if p_spoof >= cfg.deny_spoof_above or p[H.JAM.value] >= cfg.deny_jam_above or lost:
            target = TrustState.DENIED
        elif self.p_nom < cfg.degrade_below:
            target = TrustState.DEGRADED
        elif self.state != TrustState.TRUSTED and self.p_nom < cfg.trust_resume_above:
            target = TrustState.DEGRADED
        else:
            target = TrustState.TRUSTED
        if p_spoof > 0.2:
            self._spoof_hold_until = t + cfg.spoof_hold_s
        cur = self.state
        if (_ORDER[target] < _ORDER[cur] and target == TrustState.TRUSTED
                and t < self._spoof_hold_until):
            target = TrustState.DEGRADED
        if _ORDER[target] > _ORDER[cur]:
            self.state = target
            self._entered_t = t
            self._down_since = None
            return
        if _ORDER[target] < _ORDER[cur]:
            if not reacq_ok:
                self._down_since = None
                return
            if self._down_since is None:
                self._down_since = t
            hold = cfg.hold_to_degraded_s if cur == TrustState.DENIED else cfg.hold_to_trusted_s
            if (t - self._down_since) >= hold and (t - self._entered_t) >= cfg.min_denied_s:
                self.state = _BY_ORDER[_ORDER[cur] - 1]
                self._entered_t = t
                self._down_since = None
        else:
            self._down_since = None

    def _report(self, t, g, pe, pn, ev, offset_m, ref_ok, warm) -> TrustReport:
        cfg = self.cfg
        probs = self.probs
        non_nom = {k: v for k, v in probs.items() if k != H.NOMINAL.value}
        dominant = max(non_nom, key=non_nom.get) if self.p_nom < 0.95 else "none"
        dr = self._dead_reckon(t)
        gnss_ok_now = g is not None
        if self.state == TrustState.TRUSTED:
            action = NavAction.USE_GNSS
            pos = (pe, pn) if gnss_ok_now else (dr or (self.last_good[1:] if self.last_good else (None, None)))
        elif dr is not None:
            action = NavAction.FALLBACK_REFERENCE
            pos = dr
        elif self.state == TrustState.DEGRADED and gnss_ok_now:
            action = NavAction.USE_GNSS_WITH_CAUTION
            pos = (pe, pn)
        else:
            action = NavAction.HOLD_AND_ALERT
            pos = self.last_good[1:] if self.last_good else (None, None)
        trust = self.p_nom
        if self.state == TrustState.DEGRADED:
            trust = min(trust, 0.49)
        elif self.state == TrustState.DENIED:
            trust = min(trust, 0.14)
        # recent, de-duplicated evidence for explanation
        for e in ev:
            if e.weight > 0.02 and e.llr and max(e.llr.values()) > 0:
                self._recent.append((t, e))
        self._recent = [(tt, e) for tt, e in self._recent if t - tt <= 15.0][-200:]
        best: dict = {}
        for tt, e in self._recent:
            k = (e.detector, e.kind)
            if k not in best or e.weight > best[k].weight:
                best[k] = e
        top = sorted(best.values(), key=lambda e: -e.weight)[:4]
        lat = lon = None
        if pos[0] is not None and self.frame is not None:
            lat, lon = self.frame.to_geo(pos[0], pos[1])
        report = TrustReport(t=t, state=self.state, trust=trust, probs=dict(probs), dominant=dominant,
                             action=action, evidence=top, nav_e=pos[0], nav_n=pos[1], nav_lat=lat,
                             nav_lon=lon, gnss_offset_m=offset_m, ref_ok=ref_ok, warmup=warm)
        report.summary = self._summary(report)
        return report

    def _summary(self, r: TrustReport) -> str:
        if r.state == TrustState.TRUSTED:
            return "GNSS position consistent with all checks." + (" (warming up baselines)" if r.warmup else "")
        label = {"environmental_degradation": "environmental degradation (obstruction/multipath)",
                 "jamming": "jamming-like signal loss", "spoofing_jump": "position-takeover spoofing",
                 "spoofing_drift": "gradual carry-off spoofing", "replay_meaconing": "replay/meaconing",
                 "none": "unexplained anomaly"}.get(r.dominant, r.dominant)
        why = r.evidence[0].message if r.evidence else "see evidence"
        extra = " Re-acquisition cannot be verified against the reference." if self.unverifiable else ""
        return f"{r.state.value}: most likely {label}. {why}.{extra} Action: {r.action.value}."
