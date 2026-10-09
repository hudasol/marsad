"""SIMULATED multi-source track scenarios with injected faults, plus evaluation.

Everything produced here is synthetic. Positions are generated in a local frame around an
arbitrary origin; zones are fictional ("SIM-*"). Faults are modelled at the measurement level only
(what a feed would report). No RF, no attribution.

Sources:
  'ais-like'   cooperative, GNSS-derived, sigma ~6 m, can be spoofed/offset
  'radar-like' independent of GNSS, sigma ~35 m, not affected by the injected faults
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..geo import LocalFrame
from .config import TrackConfig
from .engine import TrackTrustEngine
from .types import TrackReport, Zone

ORIGIN = (25.30, 54.80)          # arbitrary simulation origin
KINDS = ("ais_common_offset", "teleport", "replay", "flatline", "circle_spoof", "forbidden_zone")
AIS, RADAR = "ais-like", "radar-like"
_FRAME = LocalFrame(*ORIGIN)


def demo_zones() -> list:
    """Fictional zones used by the simulator (SIMULATED)."""
    out = []
    for name, (e, n), rad in (("SIM-AIRFIELD", (-25000.0, 8000.0), 2500.0),
                              ("SIM-INLAND", (-42000.0, -15000.0), 9000.0)):
        lat, lon = _FRAME.to_geo(e, n)
        out.append(Zone(name, lat, lon, rad, {"surface"}))
    return out


@dataclass
class Scenario:
    seed: int
    reports: list                       # TrackReport in arrival order
    zones: list
    labels: dict
    meta: dict = field(default_factory=dict)

    def __iter__(self):
        return iter(self.reports)

    def __len__(self):
        return len(self.reports)


# ------------------------------------------------------------------ truth generation
def _truth(rng: random.Random, cls: str, duration: float) -> list:
    n = int(duration) + 2
    if cls == "air":
        v0, turn_cap, dturn = rng.uniform(100, 220), 0.004, 2e-5
        e, nn = rng.uniform(-2000, 22000), rng.uniform(-20000, 20000)
    else:
        v0, turn_cap, dturn = rng.uniform(2.5, 12.0), 0.008, 8e-5
        e, nn = rng.uniform(-2000, 22000), rng.uniform(-20000, 20000)
    hdg = rng.uniform(0, 2 * math.pi)
    om = 0.0
    ph = rng.uniform(0, 6.28)
    out = []
    for i in range(n):
        v = v0 * (1.0 + 0.08 * math.sin(i / 120.0 + ph))
        om = max(-turn_cap, min(turn_cap, om + rng.gauss(0, dturn)))
        hdg += om
        out.append((e, nn, v, math.degrees(hdg) % 360.0 if False else (90.0 - math.degrees(hdg)) % 360.0))
        # motion: hdg is math angle (east=0, CCW); course is compass bearing
        e += v * math.cos(hdg)
        nn += v * math.sin(hdg)
    return out


def _at(truth: list, t: float):
    i = min(max(int(t), 0), len(truth) - 2)
    f = min(max(t - i, 0.0), 1.0)
    a, b = truth[i], truth[i + 1]
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3])


def _norm_faults(faults) -> dict:
    if not faults:
        return {}
    if isinstance(faults, str):
        faults = [faults]
    if isinstance(faults, dict):
        out = {k: dict(v or {}) for k, v in faults.items()}
    else:
        out = {k: {} for k in faults}
    bad = [k for k in out if k not in KINDS]
    if bad:
        raise ValueError(f"unknown fault kinds {bad}; choose from {KINDS}")
    return out


def make_scenario(seed: int, n_tracks: int = 20, duration: float = 900.0, faults=None,
                  allow_stale_ts: bool = True, loiter: bool = False, radar_coverage: float = 0.7,
                  radar_sigma: float = 35.0) -> Scenario:
    """Deterministic SIMULATED two-source scenario.

    faults: None | list of kinds | {kind: params}. Params (all optional):
      common: n (tracks, default 3), t_on (s)
      ais_common_offset: magnitude_m (3000..15000), bearing_deg, fraction (1.0), ramp_s (0)
      teleport: magnitude_m;  replay: mode 'loop'|'stale_ts', length_s;  flatline/circle_spoof: length_s
    loiter=True adds a legitimate tight circling track (hard negative for the circle check).
    """
    faults = _norm_faults(faults)
    master = random.Random(f"scn-{seed}")
    zones = demo_zones()
    zl = {z.name: _FRAME.to_local(z.lat, z.lon) for z in zones}
    tracks = []
    for i in range(n_tracks):
        rng = random.Random(f"trk-{seed}-{i}")
        cls = "air" if i % 4 == 3 else "surface"
        truth = _truth(rng, cls, duration)
        covered = rng.random() < radar_coverage
        radar_cls = cls if rng.random() < 0.8 else "unknown"
        dt_a = 5.0 if cls == "air" else 10.0
        ais, t = [], rng.uniform(0, dt_a)
        while t <= duration:
            e, n, v, c = _at(truth, t)
            ais.append({"ta": t, "t": t, "e": e + rng.gauss(0, 6), "n": n + rng.gauss(0, 6),
                        "speed": max(0.0, v + rng.gauss(0, 0.3 if cls == "surface" else 1.0)),
                        "course": (c + rng.gauss(0, 2.0)) % 360.0, "truth": (e, n)})
            t += dt_a + rng.uniform(-0.3, 0.3)
        radar = []
        if covered:
            t = rng.uniform(0, 6.0)
            while t <= duration:
                e, n, v, c = _at(truth, t)
                radar.append({"ta": t, "t": t, "e": e + rng.gauss(0, radar_sigma), "n": n + rng.gauss(0, radar_sigma),
                              "speed": max(0.0, v + rng.gauss(0, 1.5)),
                              "course": (c + rng.gauss(0, 5.0)) % 360.0})
                t += 6.0 + rng.uniform(-0.3, 0.3)
        tracks.append({"id": f"T{i:03d}", "cls": cls, "radar_cls": radar_cls, "truth": truth,
                       "covered": covered, "ais": ais, "radar": radar, "ident": f"SIM{700000 + i}"})

    if loiter:
        # legitimate tight loiter: speed/course consistent with the circle (hard negative)
        i = n_tracks
        rng = random.Random(f"loiter-{seed}")
        r, v = rng.uniform(120, 200), rng.uniform(3.0, 5.0)
        w, ph = v / r, rng.uniform(0, 6.28)
        cx, cy = rng.uniform(0, 15000), rng.uniform(-10000, 10000)
        ais, radar = [], []
        t = rng.uniform(0, 10)
        while t <= duration:
            a = ph + w * t
            ais.append({"ta": t, "t": t, "e": cx + r * math.cos(a) + rng.gauss(0, 6), "n": cy + r * math.sin(a) + rng.gauss(0, 6),
                        "speed": v + rng.gauss(0, 0.3), "course": (90.0 - math.degrees(a + math.pi / 2)) % 360.0 + rng.gauss(0, 2),
                        "truth": (cx + r * math.cos(a), cy + r * math.sin(a))})
            t += 10.0 + rng.uniform(-0.3, 0.3)
        tracks.append({"id": f"T{i:03d}", "cls": "surface", "radar_cls": "surface", "truth": None,
                       "covered": False, "ais": ais, "radar": radar, "ident": f"SIM{700000 + i}", "loiter": True})

    labels = {"label": "SIMULATED", "seed": seed, "faulted_tracks": {}, "compromised_sources": {},
              "tainted_tracks": [], "radar_covered": {t["id"]: t["covered"] for t in tracks},
              "loiter_tracks": [t["id"] for t in tracks if t.get("loiter")], "faults": faults}

    # ---- fault injection (order fixed; track faults first, source-level last) ----
    used: set = set()

    def pick(kind, need_surface):
        p = faults[kind]
        k = int(p.get("n", 3))
        pool = [t for t in tracks if t["id"] not in used and not t.get("loiter")
                and (t["cls"] == "surface" or not need_surface)]
        k = min(k, len(pool))
        chosen = master.sample(pool, k) if k else []
        chosen.sort(key=lambda t: t["id"])
        used.update(t["id"] for t in chosen)
        return chosen

    def mark(tr, kind, t_on, t_off, **extra):
        d = labels["faulted_tracks"].setdefault(tr["id"], {"kinds": [], "t_on": t_on, "t_off": t_off,
                                                           "source": AIS, "radar_covered": tr["covered"]})
        d["kinds"].append(kind)
        d["t_on"] = min(d["t_on"], t_on)
        d["t_off"] = max(d["t_off"], t_off)
        d.update(extra)

    for kind in KINDS[1:]:
        if kind not in faults:
            continue
        p = faults[kind]
        for tr in pick(kind, need_surface=kind in ("circle_spoof", "forbidden_zone")):
            a = tr["ais"]
            lo, hi = {"teleport": (0.3, 0.7), "replay": (0.4, 0.55), "flatline": (0.3, 0.6),
                      "circle_spoof": (0.25, 0.45), "forbidden_zone": (0.3, 0.6)}[kind]
            t_on = float(p.get("t_on", master.uniform(lo, hi) * duration))
            if kind == "teleport":
                mag, brg = p.get("magnitude_m", master.uniform(4000, 20000)), master.uniform(0, 2 * math.pi)
                for r in a:
                    if r["t"] >= t_on:
                        r["e"] += mag * math.sin(brg)
                        r["n"] += mag * math.cos(brg)
                mark(tr, kind, t_on, duration, magnitude_m=round(mag))
            elif kind == "replay":
                L = float(p.get("length_s", master.uniform(150, 240)))
                mode = p.get("mode") or (master.choice(["loop", "stale_ts"]) if allow_stale_ts else "loop")
                seg = [dict(r) for r in a if t_on - L <= r["t"] < t_on]
                win = [r for r in a if t_on <= r["t"] < t_on + L]
                if len(seg) >= 3:
                    for k, r in enumerate(win):
                        s = seg[k % len(seg)]
                        r["e"], r["n"], r["speed"], r["course"] = s["e"], s["n"], s["speed"], s["course"]
                        if mode == "stale_ts":
                            r["t"] = s["t"]
                mark(tr, kind, t_on, t_on + L, mode=mode)
            elif kind == "flatline":
                L = float(p.get("length_s", master.uniform(120, 240)))
                pre = [r for r in a if r["t"] < t_on]
                if pre:
                    fe, fn = pre[-1]["e"], pre[-1]["n"]
                    for r in a:
                        if t_on <= r["t"] < t_on + L:
                            r["e"], r["n"] = fe, fn
                mark(tr, kind, t_on, t_on + L)
            elif kind == "circle_spoof":
                L = float(p.get("length_s", 420.0))
                rad, vc = master.uniform(80, 200), master.uniform(3.5, 7.0)
                w, ph = vc / rad * master.choice([-1, 1]), master.uniform(0, 2 * math.pi)
                anchor = next((r for r in a if r["t"] >= t_on), None)
                if anchor is not None:
                    cx = anchor["truth"][0] - rad * math.cos(ph)
                    cy = anchor["truth"][1] - rad * math.sin(ph)
                    for r in a:
                        if t_on <= r["t"] < t_on + L:
                            ang = ph + w * (r["t"] - anchor["t"])
                            r["e"] = cx + rad * math.cos(ang) + master.gauss(0, 6)
                            r["n"] = cy + rad * math.sin(ang) + master.gauss(0, 6)
                mark(tr, kind, t_on, t_on + L, radius_m=round(rad))
            elif kind == "forbidden_zone":
                ze, zn = zl["SIM-AIRFIELD"]
                rr, aa = 0.5 * 2500.0 * math.sqrt(master.random()), master.uniform(0, 2 * math.pi)
                anchor = next((r for r in a if r["t"] >= t_on), None)
                if anchor is not None:
                    oe = ze + rr * math.cos(aa) - anchor["truth"][0]
                    on = zn + rr * math.sin(aa) - anchor["truth"][1]
                    for r in a:
                        if r["t"] >= t_on:
                            r["e"] += oe
                            r["n"] += on
                mark(tr, kind, t_on, duration, zone="SIM-AIRFIELD")

    if "ais_common_offset" in faults:
        p = faults["ais_common_offset"]
        frac = float(p.get("fraction", 1.0))
        mag = float(p.get("magnitude_m", master.uniform(3000, 15000)))
        brg = math.radians(float(p.get("bearing_deg", master.uniform(0, 360))))
        t_on = float(p.get("t_on", master.uniform(0.25, 0.45) * duration))
        ramp = float(p.get("ramp_s", 0.0))
        if frac >= 1.0:
            chosen = list(tracks)
        else:
            chosen = sorted(master.sample(tracks, max(1, int(round(frac * len(tracks))))), key=lambda t: t["id"])
        for tr in chosen:
            for r in tr["ais"]:
                if r["t"] >= t_on:
                    k = min(1.0, (r["t"] - t_on) / ramp) if ramp > 0 else 1.0
                    r["e"] += k * mag * math.sin(brg)
                    r["n"] += k * mag * math.cos(brg)
            mark(tr, "ais_common_offset", t_on, duration)
        labels["compromised_sources"][AIS] = {"type": "common_offset", "magnitude_m": round(mag),
                                              "bearing_deg": round(math.degrees(brg) % 360, 1),
                                              "t_on": t_on, "fraction": frac, "ramp_s": ramp}
        labels["tainted_tracks"] = sorted(t["id"] for t in tracks)

    # ---- assemble in arrival order ----
    entries = []
    for tr in tracks:
        for r in tr["ais"]:
            lat, lon = _FRAME.to_geo(r["e"], r["n"])
            entries.append((r["ta"], 0, tr["id"], TrackReport(
                tr["id"], AIS, round(r["t"], 3), round(lat, 6), round(lon, 6), round(r["speed"], 2),
                round(r["course"], 1), tr["cls"], 6.0, tr["ident"])))
        for r in tr["radar"]:
            lat, lon = _FRAME.to_geo(r["e"], r["n"])
            entries.append((r["ta"], 1, tr["id"], TrackReport(
                tr["id"], RADAR, round(r["t"], 3), round(lat, 6), round(lon, 6), round(r["speed"], 2),
                round(r["course"], 1), tr["radar_cls"], radar_sigma, None)))
    entries.sort(key=lambda x: (x[0], x[1], x[2]))
    meta = {"label": "SIMULATED", "n_tracks": len(tracks), "duration": duration, "sources": [AIS, RADAR],
            "origin": ORIGIN, "n_reports": len(entries)}
    return Scenario(seed, [e[3] for e in entries], zones, labels, meta)


def make_demo_scenario(seed: int = 7) -> Scenario:
    """SIMULATED demo: one of each track fault plus a partial source offset late in the run."""
    f = {"circle_spoof": {"n": 1, "t_on": 200.0}, "flatline": {"n": 1, "t_on": 320.0},
         "teleport": {"n": 1, "t_on": 420.0}, "forbidden_zone": {"n": 1, "t_on": 520.0},
         "ais_common_offset": {"fraction": 0.6, "t_on": 620.0, "magnitude_m": 6000.0}}
    sc = make_scenario(seed, n_tracks=24, duration=900.0, faults=f)
    sc.reports.sort(key=lambda r: (r.t, r.source, r.track_id))
    return sc


def make_demo_stream(seed: int = 7) -> list:
    """Time-ordered list of TrackReport (SIMULATED) for live replay. Zones: demo_zones()."""
    return make_demo_scenario(seed).reports


# ------------------------------------------------------------------ evaluation
def run_scenario(sc: Scenario, config: Optional[TrackConfig] = None) -> dict:
    """Run the engine over a scenario and collect flag statistics."""
    eng = TrackTrustEngine(config, sc.zones)
    lab = sc.labels
    ft = lab["faulted_tracks"]
    first_flag: dict = {}
    ever_flag: dict = {}
    reasons: dict = {}
    n_flag = 0
    src_first: dict = {}
    clock = -math.inf                      # arrival-time proxy (stale-timestamp replays carry old stamps)
    for i, r in enumerate(sc.reports):
        clock = max(clock, r.t)
        res = eng.ingest(r)
        if res.state != "TRUSTED":
            n_flag += 1
            ever_flag.setdefault(r.track_id, clock)
            reasons.setdefault(r.track_id, [x["kind"] for x in res.reasons[:3]])
            f = ft.get(r.track_id)
            if f and clock >= f["t_on"]:
                first_flag.setdefault(r.track_id, clock)
        if i % 20 == 0:
            for s, h in eng.source_health().items():
                if h["flagged"]:
                    src_first.setdefault(s, clock)
    for s, h in eng.source_health().items():
        if h["flagged"]:
            src_first.setdefault(s, sc.reports[-1].t)
    return {"first_flag": first_flag, "ever_flag": ever_flag, "reasons": reasons,
            "flag_fraction": n_flag / max(1, len(sc.reports)), "source_flags": src_first,
            "blame": {s: h for s, h in eng.source_health().items()}, "engine": eng}


def evaluate(seed_range: Iterable[int] = range(0, 20), n_tracks: int = 20, duration: float = 900.0,
             config: Optional[TrackConfig] = None, kinds: Iterable[str] = KINDS) -> dict:
    """SIMULATED evaluation. For each seed: one clean scenario (with one legitimate loiter track
    every other seed) and one single-fault scenario per kind. Metrics:

    * track level: faulted tracks (labelled) flagged (SUSPECT/DISTRUSTED) at/after onset = TP;
      clean tracks flagged at any time = FP. Unmodified tracks carried by a compromised source are
      *tainted* and excluded from FP counting (flagging them is the intended source-level effect).
    * clean false-flag rate: share of clean-scenario tracks ever flagged.
    * source level: detection / correct attribution of the compromised source; false source flags.
    """
    seeds = list(seed_range)
    kinds = list(kinds)
    tp = fn = fp = 0
    by_kind: dict = {k: {"n": 0, "detected": 0, "latencies": [], "covered_n": 0, "covered_det": 0,
                         "ais_only_n": 0, "ais_only_det": 0} for k in kinds}
    clean_tracks = clean_flagged = clean_scn = 0
    clean_flag_time = 0.0
    clean_src_false = 0
    fa_tracks_fault_scn = fa_tracks_fault_scn_flagged = 0
    src_n = src_det = src_attr = 0
    src_lat = []
    failures: list = []
    n_scn = 0
    for seed in seeds:
        scenarios = [(None, make_scenario(seed, n_tracks, duration, None, loiter=(seed % 2 == 0)))]
        scenarios += [(k, make_scenario(seed, n_tracks, duration, [k], loiter=(seed % 2 == 0))) for k in kinds]
        for kind, sc in scenarios:
            n_scn += 1
            res = run_scenario(sc, config)
            lab = sc.labels
            ft, tainted = lab["faulted_tracks"], set(lab["tainted_tracks"])
            tracks = {r.track_id for r in sc.reports}
            for tid in sorted(tracks):
                if tid in ft:
                    d = by_kind[kind]
                    d["n"] += 1
                    cov = ft[tid]["radar_covered"]
                    d["covered_n" if cov else "ais_only_n"] += 1
                    if tid in res["first_flag"]:
                        tp += 1
                        d["detected"] += 1
                        d["covered_det" if cov else "ais_only_det"] += 1
                        d["latencies"].append(res["first_flag"][tid] - ft[tid]["t_on"])
                    else:
                        fn += 1
                        failures.append({"seed": seed, "kind": kind, "track": tid, "radar_covered": cov,
                                         "note": "faulted track never flagged"})
                elif tid in tainted:
                    continue
                else:
                    if kind is None:
                        clean_tracks += 1
                    else:
                        fa_tracks_fault_scn += 1
                    if tid in res["ever_flag"]:
                        fp += 1
                        if kind is None:
                            clean_flagged += 1
                        else:
                            fa_tracks_fault_scn_flagged += 1
                        failures.append({"seed": seed, "kind": kind or "clean", "track": tid,
                                         "note": "false flag", "top_reasons": res["reasons"].get(tid)})
            if kind is None:
                clean_scn += 1
                clean_flag_time += res["flag_fraction"]
                if res["source_flags"]:
                    clean_src_false += 1
                    failures.append({"seed": seed, "kind": "clean", "note": "false source flag",
                                     "sources": sorted(res["source_flags"])})
            elif kind == "ais_common_offset":
                src_n += 1
                if AIS in res["source_flags"]:
                    src_det += 1
                    src_lat.append(res["source_flags"][AIS] - lab["compromised_sources"][AIS]["t_on"])
                    if RADAR not in res["source_flags"]:
                        src_attr += 1
                    else:
                        failures.append({"seed": seed, "kind": kind, "note": "radar-like wrongly flagged too"})
                else:
                    failures.append({"seed": seed, "kind": kind, "note": "compromised source not flagged"})
            elif res["source_flags"]:
                failures.append({"seed": seed, "kind": kind, "note": "source flagged in track-fault scenario",
                                 "sources": sorted(res["source_flags"])})

    def med(x):
        x = sorted(x)
        return None if not x else round(x[len(x) // 2], 1)

    def rate(a, b):
        return None if b == 0 else round(a / b, 4)

    prec = rate(tp, tp + fp)
    rec = rate(tp, tp + fn)
    f1 = None if not prec or not rec else round(2 * prec * rec / (prec + rec), 4)
    return {
        "label": "SIMULATED",
        "seeds": [seeds[0], seeds[-1]] if seeds else [],
        "n_seeds": len(seeds), "n_scenarios": n_scn, "n_tracks_per_scenario": n_tracks, "duration_s": duration,
        "track_level": {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn},
        "by_fault": {k: {"n": v["n"], "detected": v["detected"], "recall": rate(v["detected"], v["n"]),
                         "median_latency_s": med(v["latencies"]),
                         "recall_radar_covered": rate(v["covered_det"], v["covered_n"]),
                         "recall_ais_only": rate(v["ais_only_det"], v["ais_only_n"])}
                     for k, v in by_kind.items()},
        "clean": {"scenarios": clean_scn, "tracks": clean_tracks, "tracks_flagged": clean_flagged,
                  "false_flag_rate": rate(clean_flagged, clean_tracks),
                  "mean_flagged_report_fraction": round(clean_flag_time / max(1, clean_scn), 5),
                  "scenarios_with_false_source_flag": clean_src_false},
        "clean_tracks_in_fault_scenarios": {"tracks": fa_tracks_fault_scn, "flagged": fa_tracks_fault_scn_flagged,
                                            "false_flag_rate": rate(fa_tracks_fault_scn_flagged, fa_tracks_fault_scn)},
        "source_level": {"scenarios": src_n, "detected": src_det, "correctly_attributed": src_attr,
                         "median_latency_s": med(src_lat)},
        "failures": failures[:60], "n_failures": len(failures),
    }


STRESS_CASES = {
    "offset_300m_all": ({"ais_common_offset": {"magnitude_m": 300.0}}, {}),
    "offset_800m_all": ({"ais_common_offset": {"magnitude_m": 800.0}}, {}),
    "offset_1500m_all": ({"ais_common_offset": {"magnitude_m": 1500.0}}, {}),
    "offset_6km_ramp_800s": ({"ais_common_offset": {"magnitude_m": 6000.0, "ramp_s": 800.0, "t_on": 50.0}}, {}),
    "offset_6km_30pct_of_tracks": ({"ais_common_offset": {"magnitude_m": 6000.0, "fraction": 0.3}}, {}),
    "offset_6km_15pct_of_tracks": ({"ais_common_offset": {"magnitude_m": 6000.0, "fraction": 0.15}}, {}),
    "offset_6km_radar_coverage_20pct": ({"ais_common_offset": {"magnitude_m": 6000.0}}, {"radar_coverage": 0.2}),
    "offset_6km_no_radar": ({"ais_common_offset": {"magnitude_m": 6000.0}}, {"radar_coverage": 0.0}),
    "offset_6km_radar_sigma_150m": ({"ais_common_offset": {"magnitude_m": 6000.0}}, {"radar_sigma": 150.0}),
    "offset_6km_ramp_800s_no_radar": ({"ais_common_offset": {"magnitude_m": 6000.0, "ramp_s": 800.0, "t_on": 50.0}},
                                      {"radar_coverage": 0.0}),
    "offset_1500m_ramp_800s_no_radar": ({"ais_common_offset": {"magnitude_m": 1500.0, "ramp_s": 800.0, "t_on": 50.0}},
                                        {"radar_coverage": 0.0}),
    "mixed_all_faults_n2_offset_50pct": (
        {"teleport": {"n": 2}, "replay": {"n": 2}, "flatline": {"n": 2}, "circle_spoof": {"n": 2},
         "forbidden_zone": {"n": 2}, "ais_common_offset": {"fraction": 0.5, "magnitude_m": 8000.0}}, {}),
    "teleport_no_radar": (["teleport"], {"radar_coverage": 0.0}),
    "replay_no_radar": (["replay"], {"radar_coverage": 0.0}),
    "circle_no_radar": (["circle_spoof"], {"radar_coverage": 0.0}),
    "forbidden_zone_no_radar": (["forbidden_zone"], {"radar_coverage": 0.0}),
    "clean_radar_sigma_150m": (None, {"radar_sigma": 150.0}),
    "clean_no_radar": (None, {"radar_coverage": 0.0}),
}


def stress(seed_range: Iterable[int] = range(1000, 1020), config: Optional[TrackConfig] = None) -> dict:
    """SIMULATED sensitivity / limit cases (parameters outside the tuned envelope). Per case:
    share of faulted tracks flagged, share of seeds in which the compromised source was flagged
    (and blamed alone), and clean-track false flags."""
    out = {}
    seeds = list(seed_range)
    for name, (faults, kw) in STRESS_CASES.items():
        nf = nd = ncl = nclf = sd = sa = 0
        for seed in seeds:
            sc = make_scenario(seed, faults=faults, **kw)
            res = run_scenario(sc, config)
            lab = sc.labels
            ft, tainted = lab["faulted_tracks"], set(lab["tainted_tracks"])
            for tid in {r.track_id for r in sc.reports}:
                if tid in ft:
                    nf += 1
                    nd += tid in res["first_flag"]
                elif tid not in tainted:
                    ncl += 1
                    nclf += tid in res["ever_flag"]
            if lab["compromised_sources"]:
                if AIS in res["source_flags"]:
                    sd += 1
                    sa += RADAR not in res["source_flags"]
        d = {"seeds": len(seeds), "faulted_tracks": nf, "faulted_flagged": nd,
             "track_recall": None if nf == 0 else round(nd / nf, 3),
             "clean_tracks": ncl, "clean_flagged": nclf}
        if faults and "ais_common_offset" in (faults if isinstance(faults, dict) else {}):
            d["source_flagged_seeds"] = sd
            d["source_blamed_alone_seeds"] = sa
        out[name] = d
    return {"label": "SIMULATED", "cases": out}
