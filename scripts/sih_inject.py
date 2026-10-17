"""Measurement-level GNSS attack injected into a REAL PX4 SIH log, scored against simulator ground truth.

usage: python scripts/sih_inject.py sitl1.ulg [--end 77] [--t-attack 45] [--out docs/results/sih_inject.json]

What is real: the PX4 flight, its GNSS stream, timing and noise (vehicle_gnss from a PX4 v1.18 SIH run).
What is injected: a position offset added to the logged GNSS fixes after --t-attack (carry-off drift or step jump).
Reference: vehicle_local_position_groundtruth velocity (simulator truth, NOT EKF-fused), so the independent
reference check is genuinely independent. The log is cut at --end, before the real receiver fix-loss fault.
Results are labelled "SIH log + injected attack": not real spoofing, not pure simulation. No RF is generated.
"""
import argparse
import json
import math
import sys
import warnings
from copy import deepcopy

import numpy as np

from marsad import TrustEngine, preset
from marsad.adapters.ulog import load_ulog
from marsad.bench.baseline import GateBaseline
from marsad.geo import LocalFrame
from marsad.types import RefMotion, TrustState


def groundtruth_ref(path, samples, sigma=0.1):
    """Replace every sample's reference with simulator-truth velocity. Returns (samples, source) or raises."""
    from pyulog import ULog
    u = ULog(path, disable_str_exceptions=True)
    d = next((x for x in u.data_list if x.name == "vehicle_local_position_groundtruth"), None)
    if d is None:
        raise SystemExit("no vehicle_local_position_groundtruth topic: this is not an SIH log")
    f = d.data
    if "vx" not in f or "vy" not in f:
        raise SystemExit(f"groundtruth has no vx/vy; fields: {sorted(f)}")
    t = f["timestamp"] / 1e6
    vn, ve = np.asarray(f["vx"], float), np.asarray(f["vy"], float)       # NED: x=north, y=east
    out = []
    for s in samples:
        s = deepcopy(s)
        if s.ref is not None:
            s.ref = RefMotion(t=s.t, ve=float(np.interp(s.t, t, ve)), vn=float(np.interp(s.t, t, vn)),
                              sigma=sigma, source="sih_groundtruth", quality=1.0)
        out.append(s)
    return out, "vehicle_local_position_groundtruth (simulator truth)"


def _drift_dist(t, t_a, rate, ramp):
    tau = max(t - t_a, 0.0)
    return 0.5 * rate * tau * tau / ramp if tau < ramp else 0.5 * rate * ramp + rate * (tau - ramp)


def inject(samples, kind, t_a, *, rate=1.0, ramp=10.0, angle=0.0, mag=100.0, vel_consistent=True):
    """Return a copy of samples with a position attack on the GNSS stream from t_a. Pure measurement edit."""
    out = [deepcopy(s) for s in samples]
    fixes = [s.gnss for s in out if s.gnss is not None]
    fr = LocalFrame(fixes[0].lat, fixes[0].lon)
    ux, uy = math.sin(angle), math.cos(angle)
    for s in out:
        g = s.gnss
        if g is None or s.t < t_a:
            continue
        if kind == "drift":
            dist = _drift_dist(s.t, t_a, rate, ramp)
            if vel_consistent and g.ve is not None and g.vn is not None:
                r = rate * min((s.t - t_a) / ramp, 1.0)
                g.ve, g.vn = g.ve + r * ux, g.vn + r * uy
        elif kind == "jump":
            dist = mag
        else:
            raise ValueError(kind)
        e, n = fr.to_local(g.lat, g.lon)
        g.lat, g.lon = fr.to_geo(e + dist * ux, n + dist * uy)
    return out


def offset_at(kind, t, t_a, rate, ramp, mag):
    return mag if kind == "jump" else _drift_dist(t, t_a, rate, ramp)


def run(samples, cfg="uav_multirotor"):
    eng, base = TrustEngine(preset(cfg)), GateBaseline()
    m, b = [], []
    for s in samples:
        r = eng.update(s)
        m.append((s.t, r.state))
        bs, _ = base.update(s)
        b.append((s.t, bs))
    return m, b


def first_alarm(series, t_a):
    for t, st in series:
        if t >= t_a and st != TrustState.TRUSTED:
            return t
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--end", type=float, default=77.0, help="cut the log here (before the real fix-loss fault)")
    ap.add_argument("--t-attack", type=float, default=45.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = load_ulog(a.log, allow_contaminated=True, warn=False)
    samples = [s for s in d.samples if s.t <= a.end]
    samples, ref_src = groundtruth_ref(a.log, samples)
    t_a = a.t_attack
    print(f"{a.log}: {len(samples)} samples to {a.end:.0f}s, attack from {t_a:.0f}s ({a.end - t_a:.0f}s window)")
    print(f"reference: {ref_src}\n")

    m, b = run(samples)
    clean_m = sum(1 for _, st in m if st != TrustState.TRUSTED)
    clean_b = sum(1 for _, st in b if st != TrustState.TRUSTED)
    print(f"clean (no attack): Marsad non-TRUSTED samples {clean_m}, gate baseline {clean_b}\n")

    angles = [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]
    cases = ([("drift", dict(rate=r, vel_consistent=vc)) for r in (0.1, 0.25, 0.5, 1.0, 2.0) for vc in (True, False)]
             + [("jump", dict(mag=x)) for x in (50.0, 200.0, 1000.0)])
    rows = []
    print(f"{'attack':34s} {'Marsad':>14s} {'offset@alarm':>13s} {'baseline':>14s}")
    for kind, p in cases:
        det_m, det_b, off_m = [], [], []
        for ang in angles:
            att = inject(samples, kind, t_a, angle=ang, **p)
            mm, bb = run(att)
            tm, tb = first_alarm(mm, t_a), first_alarm(bb, t_a)
            det_m.append(tm), det_b.append(tb)
            if tm is not None:
                off_m.append(offset_at(kind, tm, t_a, p.get("rate", 0), 10.0, p.get("mag", 0)))
        lat = [x - t_a for x in det_m if x is not None]
        latb = [x - t_a for x in det_b if x is not None]
        name = kind + " " + ", ".join(f"{k}={v}" for k, v in p.items())
        fm = f"{len(lat)}/4 med {np.median(lat):.1f}s" if lat else "0/4"
        fb = f"{len(latb)}/4 med {np.median(latb):.1f}s" if latb else "0/4"
        fo = f"{np.median(off_m):.1f} m" if off_m else "-"
        print(f"{name:34s} {fm:>14s} {fo:>13s} {fb:>14s}")
        rows.append({"attack": name, "marsad_detected": len(lat), "marsad_median_s": float(np.median(lat)) if lat else None,
                     "offset_at_alarm_m": float(np.median(off_m)) if off_m else None,
                     "baseline_detected": len(latb), "baseline_median_s": float(np.median(latb)) if latb else None,
                     "n": len(angles)})
    print("\nLabel: SIH log + injected attack (4 headings per case). Window is short; slow drifts may not complete.")
    if a.out:
        json.dump({"log": a.log, "end_s": a.end, "t_attack_s": t_a, "reference": ref_src,
                   "clean_non_trusted": {"marsad": clean_m, "baseline": clean_b}, "rows": rows},
                  open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
