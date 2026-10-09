"""Track-trust engine.

Streaming scorer for multi-source track feeds. Every report is checked for physical plausibility,
self-consistency, cross-source agreement, replay/flatline artefacts, forbidden zones and circle
signatures. Checks emit weighted evidence that is accumulated as leaky log-odds of "this position
is bad" per track (same idea as marsad.fusion, simplified to one binary hypothesis). A separate
source-level detector looks for a *common-mode displacement* between two sources over many tracks;
when found, the blamed source's health drops and every track it carries is penalised.

Stdlib only, deterministic, bounded memory.
"""
from __future__ import annotations
import math
from collections import OrderedDict, deque
from typing import Optional

from ..geo import LocalFrame, haversine
from .config import TrackConfig
from .geomfit import robust_circle_fit, wrap_deg, wrap_pi
from .types import CLASSES, TrackReport, TrackTrust, Zone


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class _Pt:
    __slots__ = ("t", "e", "n", "speed", "course", "acc", "cls", "tid", "lat", "lon")

    def __init__(self, t, e, n, speed, course, acc, cls, tid, lat, lon):
        self.t, self.e, self.n, self.speed, self.course = t, e, n, speed, course
        self.acc, self.cls, self.tid, self.lat, self.lon = acc, cls, tid, lat, lon


class _SrcState:
    """Per (track, source) memory. Bounded."""
    __slots__ = ("last", "prev", "win", "hist", "hist_set", "flat_run", "n", "t0", "rep_run")

    def __init__(self, win):
        self.last: Optional[_Pt] = None
        self.prev: Optional[_Pt] = None
        self.win = deque(maxlen=win)
        self.hist = deque(maxlen=64)
        self.hist_set: set = set()
        self.flat_run = 0
        self.n = 0
        self.t0 = math.inf
        self.rep_run = 0


class _Track:
    __slots__ = ("track_id", "L", "t_L", "state", "evid", "sources", "per_src", "last_t", "n",
                 "lat", "lon", "ekey")

    def __init__(self, track_id):
        self.track_id = track_id
        self.L = 0.0
        self.t_L = -math.inf
        self.state = "TRUSTED"
        self.evid: list = []          # (t, kind, message, weight)
        self.sources: list = []
        self.per_src: dict = {}
        self.last_t = -math.inf
        self.n = 0
        self.lat = 0.0
        self.lon = 0.0
        self.ekey = None


def _bearing_deg(de: float, dn: float) -> float:
    return math.degrees(math.atan2(de, dn)) % 360.0


class TrackTrustEngine:
    def __init__(self, config: Optional[TrackConfig] = None, zones: Optional[list] = None):
        self.cfg = config or TrackConfig()
        self.zones: list[Zone] = list(zones or [])
        self._frame: Optional[LocalFrame] = None
        self._clock = -math.inf
        self._tracks: dict[str, _Track] = {}
        self._latest: dict = {}                 # entity key -> {source: _Pt}
        self._alias: dict = {}                  # (source, track_id) -> entity key
        self._ident_entity: dict = {}           # ident -> entity key
        self._noassoc: dict = {}                # (source, track_id) -> retry time
        self._pairs: dict = {}                  # (a, b) -> OrderedDict[track_id -> (t, de, dn, sigma)]
        self._pair_eval_t: dict = {}
        self._pair_info: dict = {}              # (a, b) -> dict(median_m, flag_t, vec, n, nfresh, frac)
        self._blame: dict = {}                  # source -> dict(factor, vec, n, frac, partners, t)
        self._src_seen: dict = {}               # source -> last report time
        self._n_ingest = 0

    # ------------------------------------------------------------------ public API
    def ingest(self, report: TrackReport) -> TrackTrust:
        cfg, r = self.cfg, report
        self._n_ingest += 1
        tr = self._tracks.get(r.track_id)
        if tr is None:
            tr = self._tracks[r.track_id] = _Track(r.track_id)
        tr.n += 1
        if r.source not in tr.sources:
            tr.sources.append(r.source)

        ev: list = []        # (kind, message, weight)
        if not (math.isfinite(r.t) and math.isfinite(r.lat) and math.isfinite(r.lon)
                and -90.0 <= r.lat <= 90.0 and -180.0 <= r.lon <= 180.0):
            ev.append(("invalid_report", "report has a non-finite or out-of-range time/position", 4.0))
            self._apply(tr, max(tr.last_t, 0.0) if math.isfinite(tr.last_t) else 0.0, ev)
            return self._view(tr, self._clock if math.isfinite(self._clock) else 0.0, store_state=True)

        if self._frame is None:
            self._frame = LocalFrame(r.lat, r.lon)
        cls = r.cls if r.cls in CLASSES else "unknown"
        acc = max(cfg.min_accuracy_m, r.accuracy_m if r.accuracy_m is not None else cfg.default_accuracy_m)
        e, n = self._frame.to_local(r.lat, r.lon)
        pt = _Pt(r.t, e, n, r.speed if (r.speed is not None and math.isfinite(r.speed)) else None,
                 r.course if (r.course is not None and math.isfinite(r.course)) else None,
                 acc, cls, r.track_id, r.lat, r.lon)

        ps = tr.per_src.get(r.source)
        if ps is None:
            ps = tr.per_src[r.source] = _SrcState(cfg.circle_window)
        ps.n += 1
        ps.t0 = min(ps.t0, r.t)
        prev = ps.last
        out_of_order = prev is not None and r.t < prev.t - 1e-6
        duplicate = prev is not None and abs(r.t - prev.t) <= 1e-6 and r.lat == prev.lat and r.lon == prev.lon
        clock_before = self._clock
        if r.t > self._clock:
            self._clock = r.t
        self._src_seen[r.source] = max(self._src_seen.get(r.source, -math.inf), r.t)

        accepted = not out_of_order and not duplicate
        if out_of_order:
            ev.append(("timestamp_regression",
                       f"timestamp went backwards by {prev.t - r.t:.0f} s for source {r.source} (replay or clock fault)", 2.5))
        elif not duplicate and math.isfinite(clock_before) and r.t < clock_before - cfg.stale_s:
            ev.append(("stale_timestamp",
                       f"report is {clock_before - r.t:.0f} s older than the feed clock (stale / replayed)", 1.5))

        if accepted:
            self._check_kinematics(r, pt, prev, ps, cls, ev)
            self._check_repeats(r, pt, prev, ps, ev)
            self._check_circle(r, pt, ps, ev)
            agreed = self._check_cross(r, pt, tr, ps, ev)
            self._check_zones(r, pt, cls, acc, agreed, ev)
            ps.prev, ps.last = prev, pt
            ps.win.append(pt)
            while ps.win and r.t - ps.win[0].t > cfg.circle_horizon_s:
                ps.win.popleft()
            tr.lat, tr.lon = r.lat, r.lon

        t_ref = max(r.t, tr.last_t) if math.isfinite(tr.last_t) else r.t
        tr.last_t = t_ref
        self._apply(tr, r.t, ev)
        if self._n_ingest % 256 == 0:
            self._prune()
        return self._view(tr, r.t, store_state=True)

    def get(self, track_id: str, t: Optional[float] = None) -> Optional[TrackTrust]:
        tr = self._tracks.get(track_id)
        if tr is None:
            return None
        now = self._now(t)
        return self._view(tr, now, store_state=False)

    def snapshot(self, t: Optional[float] = None) -> list:
        now = self._now(t)
        out = []
        for tr in self._tracks.values():
            if now - tr.last_t > self.cfg.track_ttl_s:
                continue
            out.append(self._view(tr, now, store_state=False))
        out.sort(key=lambda x: (x.trust, x.track_id))
        return out

    def source_health(self, t: Optional[float] = None) -> dict:
        now = self._now(t)
        res = {}
        counts: dict = {}
        for tr in self._tracks.values():
            if now - tr.last_t > self.cfg.track_ttl_s:
                continue
            for s, ps in tr.per_src.items():
                if ps.last is not None:
                    counts[s] = counts.get(s, 0) + 1
        for s in sorted(set(self._src_seen) | set(counts)):
            b = self._blame_active(s, now)
            pen = self.cfg.source_penalty * b["factor"] if b else 0.0
            if b:
                off = math.hypot(*b["vec"])
            else:
                offs = [info["median_m"] for pr, info in self._pair_info.items()
                        if s in pr and not self._pair_active(pr, now) and "median_m" in info]
                off = max(offs) if offs else 0.0
            res[s] = {"trust": round(1.0 - _sigmoid(self.cfg.prior_logit + pen), 4),
                      "n_tracks": counts.get(s, 0),
                      "common_mode_offset_m": round(off, 1),
                      "flagged": bool(b)}
            if b:
                res[s]["bearing_deg"] = round(_bearing_deg(*b["vec"]), 1)
                res[s]["attribution"] = "sole" if b["factor"] >= 1.0 else "shared"
        return res

    def reset(self) -> None:
        self.__init__(self.cfg, self.zones)

    # ------------------------------------------------------------------ internals
    def _now(self, t):
        if t is not None:
            return t
        return self._clock if math.isfinite(self._clock) else 0.0

    def _class_of(self, source: str) -> str:
        c = self.cfg.source_classes.get(source)
        if c:
            return c
        low = source.lower()
        return "independent" if any(h in low for h in self.cfg.independent_hints) else "cooperative"

    # --- evidence accumulation -------------------------------------------------------
    def _apply(self, tr: _Track, t: float, ev: list) -> None:
        cfg = self.cfg
        if t > tr.t_L:
            if math.isfinite(tr.t_L):
                tr.L *= math.exp(-(t - tr.t_L) / cfg.tau_s)
            tr.t_L = t
        pos = sum(w for _, _, w in ev if w > 0)
        neg = sum(w for _, _, w in ev if w < 0)
        pos = min(pos, cfg.per_report_cap)
        tr.L = min(cfg.l_cap, max(cfg.l_floor, tr.L + pos + neg))
        for kind, msg, w in ev:
            if w > 0:
                tr.evid.append((t, kind, msg, w))
        if len(tr.evid) > cfg.reasons_kept:
            del tr.evid[: len(tr.evid) - cfg.reasons_kept]

    def _add_mirror(self, tid: str, t: float, kind: str, msg: str, w: float) -> None:
        other = self._tracks.get(tid)
        if other is not None:
            self._apply(other, t, [(kind, msg, w)])

    # --- (a),(b) kinematics -----------------------------------------------------------------
    def _check_kinematics(self, r, pt, prev, ps, cls, ev) -> None:
        cfg = self.cfg
        vmax, amax = cfg.v_max[cls], cfg.a_max[cls]
        if prev is not None:
            dt = pt.t - prev.t
            if 1e-6 < dt <= cfg.gap_reset_s:
                d = math.hypot(pt.e - prev.e, pt.n - prev.n)
                sig = math.sqrt(prev.acc ** 2 + pt.acc ** 2)
                noise = 3.5 * sig
                allowed = vmax * dt + noise
                teleport = False
                if d > allowed:
                    teleport = True
                    w = min(5.0, 2.0 + 1.2 * math.log2(d / allowed) + 1.0)
                    ev.append(("teleport", f"jumped {d:.0f} m in {dt:.0f} s (implied {d / dt:.0f} m/s, "
                                           f"{cls} envelope {vmax:.0f} m/s)", w))
                sp = [s for s in (prev.speed, pt.speed) if s is not None]
                if sp and not teleport:
                    exp_max = (max(sp) * 1.3 + 1.0) * dt + noise
                    if d > exp_max:
                        w = min(4.0, 1.2 + math.log2(d / exp_max) * 1.2)
                        ev.append(("speed_displacement_mismatch",
                                   f"moved {d:.0f} m in {dt:.0f} s but reported speed is only {max(sp):.1f} m/s", w))
                p2 = ps.prev
                if p2 is not None and not teleport:
                    dt1 = prev.t - p2.t
                    if dt1 >= 1.0 and dt >= 1.0 and dt <= cfg.gap_reset_s and dt1 <= cfg.gap_reset_s:
                        v1e, v1n = (prev.e - p2.e) / dt1, (prev.n - p2.n) / dt1
                        v2e, v2n = (pt.e - prev.e) / dt, (pt.n - prev.n) / dt
                        a = math.hypot(v2e - v1e, v2n - v1n) / (0.5 * (dt + dt1))
                        s0 = math.sqrt(p2.acc ** 2 + prev.acc ** 2 + pt.acc ** 2)
                        sig_a = s0 * math.sqrt(1 / dt1 ** 2 + 1 / dt ** 2) * 1.5 / (0.5 * (dt + dt1))
                        if a > amax + 4.0 * sig_a:
                            w = min(3.0, 1.0 + (a - amax - 4.0 * sig_a) / max(amax, 1.0))
                            ev.append(("acceleration", f"acceleration {a:.1f} m/s^2 exceeds {cls} limit {amax:.1f}", w))
        # displacement-vs-reported-speed/course over a longer baseline
        if pt.speed is not None and ps.win:
            base = None
            for p in reversed(ps.win):
                if pt.t - p.t >= cfg.baseline_s:
                    base = p
                    break
            if base is not None and pt.t - base.t <= 4 * cfg.baseline_s and base.speed is not None:
                dtb = pt.t - base.t
                d = math.hypot(pt.e - base.e, pt.n - base.n)
                expected = 0.5 * (pt.speed + base.speed) * dtb
                sd = math.sqrt(base.acc ** 2 + pt.acc ** 2)
                tol = 3.5 * sd + cfg.speed_tol_frac * expected + 1.0
                miss = abs(d - expected)
                if miss > tol:
                    w = min(2.5, 0.8 + 1.5 * (miss - tol) / tol)
                    rel = "less" if d < expected else "more"
                    ev.append(("speed_displacement_mismatch",
                               f"moved {d:.0f} m over {dtb:.0f} s, {rel} than reported speed implies ({expected:.0f} m)", w))
                elif pt.course is not None and base.course is not None and d > 6.0 * sd and expected > 6.0 * sd:
                    mc = math.degrees(math.atan2(math.sin(math.radians(pt.course)) + math.sin(math.radians(base.course)),
                                                 math.cos(math.radians(pt.course)) + math.cos(math.radians(base.course)))) % 360
                    diff = abs(wrap_deg(_bearing_deg(pt.e - base.e, pt.n - base.n) - mc))
                    if diff > cfg.course_tol_deg:
                        ev.append(("course_displacement_mismatch",
                                   f"track moves toward {_bearing_deg(pt.e - base.e, pt.n - base.n):.0f} deg "
                                   f"but reports course {mc:.0f} deg", 1.5))

    # --- (d) repeats / flatline ----------------------------------------------------------------
    def _check_repeats(self, r, pt, prev, ps, ev) -> None:
        cfg = self.cfg
        key = (round(r.lat, 6), round(r.lon, 6))
        moving = pt.speed is not None and pt.speed >= cfg.flatline_min_speed
        if prev is not None:
            d = math.hypot(pt.e - prev.e, pt.n - prev.n)
            if d < 0.5 and moving:
                ps.flat_run += 1
            else:
                ps.flat_run = 0
            if ps.flat_run >= cfg.flatline_n - 1:
                ev.append(("flatline", f"position unchanged for {ps.flat_run + 1} reports while reporting "
                                       f"{pt.speed:.1f} m/s", 1.5))
            last_key = (round(prev.lat, 6), round(prev.lon, 6))
            if moving and key != last_key and key in ps.hist_set:
                ps.rep_run += 1
            else:
                ps.rep_run = 0
            if ps.rep_run >= 2:
                ev.append(("position_replay", f"{ps.rep_run} consecutive reports repeat earlier coordinates exactly "
                                              "(noisy real tracks do not)", 3.0))
        if len(ps.hist) == ps.hist.maxlen:
            ps.hist_set.discard(ps.hist[0])
        ps.hist.append(key)
        ps.hist_set.add(key)

    # --- (f) circle signature ----------------------------------------------------------------------
    def _check_circle(self, r, pt, ps, ev) -> None:
        cfg = self.cfg
        win = list(ps.win) + [pt]
        if len(win) < cfg.circle_min_pts or ps.n % 2:
            return
        if pt.t - win[0].t < cfg.circle_min_span_s:
            return
        xs, ys = [p.e for p in win], [p.n for p in win]
        fit = robust_circle_fit(xs, ys)
        if fit is None:
            return
        rad = fit["r"]
        sig = sorted(p.acc for p in win)[len(win) // 2]
        if not (cfg.circle_r_min_m <= rad <= cfg.circle_r_max_m) or rad < 5.0 * sig:
            return
        if fit["rms"] > 0.15 * rad + 1.0 * sig:
            return
        cx, cy = fit["cx"], fit["cy"]
        ang = [math.atan2(y - cy, x - cx) for x, y in zip(xs, ys)]
        steps = [wrap_pi(ang[i + 1] - ang[i]) for i in range(len(ang) - 1)]
        net = sum(steps)
        tot = sum(abs(s) for s in steps)
        if abs(net) < math.radians(cfg.circle_min_arc_deg) or tot > 1.6 * abs(net) + 0.5:
            return
        span = win[-1].t - win[0].t
        omega = net / span
        v_c = rad * abs(omega)
        speeds = [p.speed for p in win if p.speed is not None]
        reasons = []
        w = 0.0
        if speeds:
            v_r = sum(speeds) / len(speeds)
            ratio = max(v_r, v_c) / max(min(v_r, v_c), 0.5)
            if ratio > cfg.circle_speed_ratio and abs(v_r - v_c) > 1.0:
                reasons.append(f"circle speed {v_c:.1f} m/s vs reported {v_r:.1f} m/s")
                w += 3.0
        # reported course vs tangent of the fitted circle
        mism = []
        sgn = 1.0 if omega > 0 else -1.0
        for p, a in zip(win, ang):
            if p.course is not None:
                tang = (90.0 - math.degrees(a + sgn * math.pi / 2)) % 360.0
                mism.append(abs(wrap_deg(p.course - tang)))
        if len(mism) >= cfg.circle_min_pts // 2:
            mm = sum(mism) / len(mism)
            if mm > 60.0:
                reasons.append(f"reported course ignores circular motion (mean {mm:.0f} deg off tangent)")
                w += 1.5
        if not speeds and not mism:
            w = 0.8
            reasons.append("no speed/course to cross-check")
        if w > 0:
            ev.append(("circle_pattern", f"positions on a {rad:.0f} m-radius circle (arc {abs(math.degrees(net)):.0f} deg, "
                                         f"fit rms {fit['rms']:.0f} m): " + "; ".join(reasons), min(4.5, w + 0.5)))

    # --- (c) cross-source comparison ---------------------------------------------------------------------
    def _entity_key(self, r: TrackReport, pt: _Pt, ps: _SrcState):
        cfg = self.cfg
        al = self._alias.get((r.source, r.track_id))
        if al is not None:
            return al
        base = ("t", r.track_id)
        if r.ident:
            base = self._ident_entity.setdefault(r.ident, base)
        if cfg.proximity_assoc and r.t - ps.t0 >= cfg.assoc_min_age_s and self._noassoc.get((r.source, r.track_id), -math.inf) <= r.t:
            ent = self._latest.get(base)
            has_partner = ent is not None and any(s != r.source for s in ent)
            if not has_partner:
                best, second = None, math.inf
                bd = math.inf
                for k2, ent2 in self._latest.items():
                    if k2 == base or r.source in ent2:
                        continue
                    for s2, p2 in ent2.items():
                        if abs(p2.t - r.t) > cfg.max_age_s or (p2.cls != pt.cls and "unknown" not in (p2.cls, pt.cls)):
                            continue
                        dt = r.t - p2.t
                        ee, nn = p2.e, p2.n
                        if p2.speed is not None and p2.course is not None:
                            ee += p2.speed * math.sin(math.radians(p2.course)) * dt
                            nn += p2.speed * math.cos(math.radians(p2.course)) * dt
                        d = math.hypot(pt.e - ee, pt.n - nn)
                        if d < bd:
                            second, bd, best = bd, d, k2
                        elif d < second:
                            second = d
                if best is not None and bd <= cfg.assoc_gate_m and second > 2.0 * bd:
                    self._alias[(r.source, r.track_id)] = best
                    return best
                self._noassoc[(r.source, r.track_id)] = r.t + 30.0
        return base

    def _check_cross(self, r, pt, tr, ps, ev) -> bool:
        cfg = self.cfg
        ekey = self._entity_key(r, pt, ps)
        tr.ekey = ekey
        ent = self._latest.setdefault(ekey, {})
        agreed = False
        for s2, p2 in list(ent.items()):
            if s2 == r.source:
                continue
            dt = pt.t - p2.t
            if abs(dt) > cfg.max_age_s:
                continue
            ee, nn = p2.e, p2.n
            if p2.speed is not None and p2.course is not None:
                ee += p2.speed * math.sin(math.radians(p2.course)) * dt
                nn += p2.speed * math.cos(math.radians(p2.course)) * dt
                unc = abs(dt) * 1.0
            else:
                unc = abs(dt) * 0.3 * min(cfg.v_max[p2.cls], 60.0)
            de, dn = pt.e - ee, pt.n - nn
            d = math.hypot(de, dn)
            sig = math.sqrt(pt.acc ** 2 + p2.acc ** 2 + unc ** 2)
            z = d / sig
            if z > cfg.z_start:
                w = min(3.5, 0.3 + 0.5 * (z - cfg.z_start))
                msg = (f"{r.source} and {s2} disagree by {d:.0f} m ({z:.1f} sigma of combined accuracy)")
                ev.append(("cross_source_disagreement", msg, w))
                if p2.tid != r.track_id:
                    self._add_mirror(p2.tid, pt.t, "cross_source_disagreement", msg, w)
            elif z < cfg.agree_z:
                ev.append(("cross_source_agreement", "", -0.3))
                agreed = True
            else:
                agreed = agreed or z < cfg.z_start
            # record offset (first - second, sorted by source name) for the common-mode detector
            a, b = (r.source, s2) if r.source < s2 else (s2, r.source)
            sgn = 1.0 if r.source == a else -1.0
            tab = self._pairs.setdefault((a, b), OrderedDict())
            tab[r.track_id] = (pt.t, sgn * de, sgn * dn, sig)
            tab.move_to_end(r.track_id)
            if len(tab) > cfg.pair_table_max:
                tab.popitem(last=False)
            if pt.t - self._pair_eval_t.get((a, b), -math.inf) >= cfg.cm_eval_every_s:
                self._pair_eval_t[(a, b)] = pt.t
                self._eval_pair((a, b), pt.t)
        ent[r.source] = pt
        return agreed

    # --- (g) common-mode ---------------------------------------------------------------------------------------
    def _eval_pair(self, pair, now: float) -> None:
        cfg = self.cfg
        tab = self._pairs[pair]
        fresh = [v for v in tab.values() if now - v[0] <= cfg.cm_fresh_s]
        n = len(fresh)
        info = self._pair_info.setdefault(pair, {})
        if n == 0:
            return
        des = sorted(v[1] for v in fresh)
        dns = sorted(v[2] for v in fresh)
        info["median_m"] = math.hypot(des[n // 2], dns[n // 2])
        info["nfresh"] = n
        S = [v for v in fresh if math.hypot(v[1], v[2]) > cfg.cm_min_offset_m]
        k = len(S)
        if k >= cfg.cm_min_tracks and k / n >= cfg.cm_min_frac:
            # robust centre (component median) so individually faulted tracks do not drag the estimate
            ce = sorted(v[1] for v in S)[k // 2]
            cn = sorted(v[2] for v in S)[k // 2]
            cm = math.hypot(ce, cn)
            ms = sum(v[3] for v in S) / k
            tol = max(cfg.cm_coherence * cm, 3.0 * ms)
            inl = [v for v in S if math.hypot(v[1] - ce, v[2] - cn) <= tol]
            ki = len(inl)
            if cm >= cfg.cm_min_offset_m and ki >= cfg.cm_min_tracks and ki / n >= cfg.cm_min_frac and ki >= 0.5 * k:
                mde = sum(v[1] for v in inl) / ki
                mdn = sum(v[2] for v in inl) / ki
                info.update(flag_t=now, vec=(mde, mdn), n=ki, frac=ki / n)
        self._recompute_blame(now)

    def _pair_active(self, pair, now: float) -> bool:
        info = self._pair_info.get(pair)
        return bool(info and "flag_t" in info and now - info["flag_t"] <= self.cfg.cm_clear_after_s)

    def _recompute_blame(self, now: float) -> None:
        cfg = self.cfg
        blame: dict = {}
        sources = sorted(self._src_seen)
        for pair, info in self._pair_info.items():
            if not self._pair_active(pair, now):
                continue
            a, b = pair
            vec = info["vec"]                      # a - b
            ca, cb = self._class_of(a), self._class_of(b)
            who = None
            if ca != cb:
                who = [(a if ca == "cooperative" else b, 1.0, "independent source disagrees")]
            else:
                for c in sources:
                    if c in pair:
                        continue
                    pa = tuple(sorted((a, c)))
                    pb = tuple(sorted((b, c)))
                    na = self._pair_info.get(pa, {}).get("nfresh", 0)
                    nb = self._pair_info.get(pb, {}).get("nfresh", 0)
                    if na < cfg.cm_min_tracks or nb < cfg.cm_min_tracks:
                        continue
                    fa, fb = self._pair_active(pa, now), self._pair_active(pb, now)
                    if fa and not fb:
                        who = [(a, 1.0, f"third source {c} agrees with {b}")]
                    elif fb and not fa:
                        who = [(b, 1.0, f"third source {c} agrees with {a}")]
                    if who:
                        break
                if not who:
                    who = [(a, 0.5, "cannot attribute between two comparable sources"),
                           (b, 0.5, "cannot attribute between two comparable sources")]
            for s, f, why in who:
                v = vec if s == a else (-vec[0], -vec[1])
                other = b if s == a else a
                cur = blame.get(s)
                if cur is None or f > cur["factor"]:
                    blame[s] = {"factor": f, "vec": v, "n": info["n"], "frac": info["frac"],
                                "partners": [other], "why": why, "t": info["flag_t"]}
                elif other not in cur["partners"]:
                    cur["partners"].append(other)
        self._blame = blame

    def _blame_active(self, source: str, now: float):
        b = self._blame.get(source)
        if b and now - b["t"] <= self.cfg.cm_clear_after_s:
            return b
        return None

    def _verified(self, tid: str, source: str, now: float) -> bool:
        cfg = self.cfg
        for pair, tab in self._pairs.items():
            if source in pair:
                v = tab.get(tid)
                if v is not None and now - v[0] <= cfg.cm_fresh_s and math.hypot(v[1], v[2]) < 0.4 * cfg.cm_min_offset_m:
                    return True
        return False

    # --- (e) zones -------------------------------------------------------------------------------------------------
    def _check_zones(self, r, pt, cls, acc, agreed, ev) -> None:
        for z in self.zones:
            if cls not in z.forbidden_classes:
                continue
            d = haversine(r.lat, r.lon, z.lat, z.lon)
            depth = z.radius_m - d
            if depth > 0:
                w = 4.0 if depth > 2.0 * acc else 2.0
                note = ""
                if agreed:
                    w *= 0.3
                    note = " (a second source places it there too; zone may be mis-specified)"
                ev.append(("forbidden_zone", f"{cls} track {d:.0f} m from centre of zone '{z.name}' "
                                             f"(radius {z.radius_m:.0f} m) where {cls} is implausible{note}", w))

    # --- output -----------------------------------------------------------------------------------------------------------
    def _penalty(self, tr: _Track, now: float):
        """Source-level penalty applying to this track: (log-odds, message or None)."""
        cfg = self.cfg
        best, msg = 0.0, None
        for s, ps in tr.per_src.items():
            if ps.last is None or now - ps.last.t > 120.0:
                continue
            b = self._blame_active(s, now)
            if not b:
                continue
            pen = cfg.source_penalty * b["factor"]
            if self._verified(tr.track_id, s, now):
                pen *= cfg.verified_factor
                vtxt = "track verified by another source, penalty reduced"
            else:
                pen *= 0.55 + 0.45 * min(1.0, b["frac"] / 0.6)
                vtxt = "track not independently verified"
            if pen > best:
                best = pen
                dist = math.hypot(*b["vec"])
                dist_txt = f"{dist / 1000:.1f} km" if dist >= 1000 else f"{dist:.0f} m"
                msg = (f"source '{s}' flagged for a common displacement of {dist_txt} toward "
                       f"{_bearing_deg(*b['vec']):.0f} deg over {b['n']} tracks versus {', '.join(b['partners'])} "
                       f"({b['why']}); {vtxt}")
        return best, msg

    def _state_for(self, trust: float, prev: str) -> str:
        c = self.cfg
        if prev == "DISTRUSTED":
            if trust < c.distrust_exit:
                return "DISTRUSTED"
            return "TRUSTED" if trust >= c.trusted_enter else "SUSPECT"
        if prev == "TRUSTED":
            if trust >= c.trusted_exit:
                return "TRUSTED"
            return "DISTRUSTED" if trust < c.distrust_enter else "SUSPECT"
        if trust < c.distrust_enter:
            return "DISTRUSTED"
        return "TRUSTED" if trust >= c.trusted_enter else "SUSPECT"

    def _view(self, tr: _Track, now: float, store_state: bool) -> TrackTrust:
        cfg = self.cfg
        L = tr.L
        if math.isfinite(tr.t_L) and now > tr.t_L:
            L *= math.exp(-(now - tr.t_L) / cfg.tau_s)
        pen, pmsg = self._penalty(tr, now)
        trust = 1.0 - _sigmoid(cfg.prior_logit + L + pen)
        state = self._state_for(trust, tr.state)
        if store_state:
            tr.state = state
        # reasons: decayed, merged by kind, strongest first
        best: dict = {}
        for (t, kind, msg, w) in tr.evid:
            dw = w * math.exp(-max(0.0, now - t) / cfg.tau_s)
            if dw >= 0.3:
                cur = best.get(kind)
                if cur is None or dw > cur["weight"]:
                    best[kind] = {"kind": kind, "message": msg, "weight": round(dw, 2), "t": t}
        reasons = sorted(best.values(), key=lambda x: -x["weight"])[: cfg.reasons_shown]
        if pmsg:
            reasons.insert(0, {"kind": "source_common_mode", "message": pmsg, "weight": round(pen, 2), "t": now})
        return TrackTrust(track_id=tr.track_id, trust=trust, state=state, reasons=reasons,
                          sources=list(tr.sources), last_t=tr.last_t if math.isfinite(tr.last_t) else 0.0,
                          n_reports=tr.n, lat=tr.lat, lon=tr.lon)

    def _prune(self) -> None:
        cfg = self.cfg
        cutoff = self._clock - cfg.track_ttl_s
        dead = [k for k, tr in self._tracks.items() if tr.last_t < cutoff]
        if len(self._tracks) - len(dead) > cfg.max_tracks:
            alive = sorted((tr.last_t, k) for k, tr in self._tracks.items() if k not in set(dead))
            dead += [k for _, k in alive[: len(self._tracks) - len(dead) - cfg.max_tracks]]
        for k in dead:
            self._tracks.pop(k, None)
        for ek in [k for k, ent in self._latest.items() if all(p.t < cutoff for p in ent.values())]:
            del self._latest[ek]
        live = set(self._latest)
        for key in [k for k, v in self._ident_entity.items() if v not in live]:
            del self._ident_entity[key]
        for key in [k for k, v in self._alias.items() if v not in live]:
            del self._alias[key]
        for key in [k for k, v in self._noassoc.items() if v < cutoff]:
            del self._noassoc[key]
        for tab in self._pairs.values():
            for tid in [k for k, v in tab.items() if v[0] < cutoff]:
                del tab[tid]
