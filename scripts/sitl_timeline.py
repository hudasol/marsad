"""Per-second timeline of a PX4 SITL/SIH log: Marsad state vs GNSS error against simulator ground truth.

usage: python scripts/sitl_timeline.py sitl1.ulg [step_seconds]

Prints, every `step` seconds of log time: Marsad state/trust, GNSS horizontal error versus the
*_groundtruth topic (SIH only), PX4 nav_state and whether the vehicle is landed. This is how a SITL
fault window is matched to the detector's reaction. Measurement-level only; nothing is injected here.
"""

import math
import sys
import warnings

import numpy as np
from pyulog import ULog

from marsad import TrustEngine, preset
from marsad.adapters.ulog import load_ulog


def pick(f, names):
    for n in names:
        if n in f:
            return f[n]
    return None


def topic(u, name):
    for d in u.data_list:
        if d.name == name:
            return d.data
    return None


def main():
    path = sys.argv[1]
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = load_ulog(path, allow_contaminated=True, warn=False)
    eng = TrustEngine(preset("uav_multirotor"))
    reports = [eng.update(s) for s in d.samples]
    u = ULog(path)

    # GNSS fixes (as the adapter read them) and ground truth
    fixes = [(s.t, s.gnss.lat, s.gnss.lon) for s in d.samples if s.gnss is not None]
    gt = topic(u, "vehicle_global_position_groundtruth")
    gt_t = gt_lat = gt_lon = None
    if gt is not None:
        la = pick(gt, ("lat", "latitude", "latitude_deg"))
        lo = pick(gt, ("lon", "longitude", "longitude_deg"))
        if la is not None and lo is not None:
            gt_t, gt_lat, gt_lon = gt["timestamp"] / 1e6, np.asarray(la, float), np.asarray(lo, float)
    vs = topic(u, "vehicle_status")
    ld = topic(u, "vehicle_land_detected")
    t0 = d.samples[0].t

    def err(t):
        if gt_t is None or not fixes:
            return None
        i = min(range(len(fixes)), key=lambda k: abs(fixes[k][0] - t))
        j = int(np.argmin(np.abs(gt_t - fixes[i][0])))
        dn = (fixes[i][1] - gt_lat[j]) * 111_320.0
        de = (fixes[i][2] - gt_lon[j]) * 111_320.0 * math.cos(math.radians(gt_lat[j]))
        return math.hypot(dn, de)

    def at(tab, key, t):
        if tab is None or key not in tab:
            return None
        ts = tab["timestamp"] / 1e6
        k = int(np.searchsorted(ts, t, side="right")) - 1
        return None if k < 0 else tab[key][k]

    print(
        f"{path}: {len(reports)} reports; time axis = vehicle uptime (s). groundtruth: {'yes' if gt_t is not None else 'NO'}"
    )
    print(f"{'t(s)':>7} {'marsad':8} {'trust':>5} {'gnss_err_m':>10} {'nav_state':>9} {'landed':>6}  dominant")
    nxt = t0
    for r in reports:
        if r.t < nxt:
            continue
        nxt = r.t + step
        e = err(r.t)
        ns = at(vs, "nav_state", r.t)
        ln = at(ld, "landed", r.t)
        print(
            f"{r.t:7.1f} {r.state.value:8} {r.trust:5.2f} "
            f"{'' if e is None else f'{e:10.1f}':>10} {'' if ns is None else int(ns):>9} "
            f"{'' if ln is None else int(ln):>6}  {r.dominant}"
        )


if __name__ == "__main__":
    main()
