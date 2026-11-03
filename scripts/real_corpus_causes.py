"""Exploratory: what drove the first non TRUSTED sample on each REAL LOG flight (not preregistered, engine unchanged).

  python scripts/real_corpus_causes.py --manifest M.csv --logs DIR --results results.json --out causes.json

For every flight with a Marsad alarm: the dominant hypothesis and the strongest evidence items at the first alarm
sample, the receiver cadence (median and maximum gap between fixes), the reference source, and the state at the end of
the first episode. Descriptive only. Design subset and scoring set are both listed, with the subset marked.
"""

import argparse
import csv
import json
import statistics
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_corpus import FIXEDWING  # noqa: E402

from marsad import TrustEngine, preset  # noqa: E402
from marsad.adapters.ulog import load_ulog  # noqa: E402
from marsad.types import TrustState  # noqa: E402


def one(path: str, vehicle: str) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = load_ulog(path, allow_contaminated=True, warn=False)
    fixes = [s for s in data.samples if s.gnss is not None]
    ts = [s.t for s in fixes]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    t1 = next((s.t for s in fixes if s.gnss.fix_type >= 3), None)
    eng = TrustEngine(preset("uav_fixedwing" if vehicle in FIXEDWING else "uav_multirotor"))
    first = None
    n_bad = n_den = n = 0
    for s in data.samples:
        r = eng.update(s)
        if t1 is None or s.t < t1:
            continue
        n += 1
        n_bad += r.state != TrustState.TRUSTED
        n_den += r.state == TrustState.DENIED
        if first is None and r.state != TrustState.TRUSTED:
            ev = sorted(r.evidence, key=lambda e: -e.weight)
            first = {
                "t_rel": s.t - t1,
                "state": r.state.value,
                "dominant": r.dominant,
                "summary": r.summary,
                "evidence": [(e.detector, e.kind, e.message[:80]) for e in ev[:4]],
                "fix_type": s.gnss.fix_type if s.gnss else None,
                "n_sats": s.gnss.n_sats if s.gnss else None,
                "gap_s": None,
            }
    return {
        "median_gap_s": statistics.median(gaps) if gaps else None,
        "max_gap_s": max(gaps) if gaps else None,
        "n_gaps_over_1p5s": sum(1 for g in gaps if g > 1.5),
        "reference_source": data.info.reference_source,
        "first_alarm": first,
        "share_not_trusted": n_bad / max(n, 1),
        "share_denied": n_den / max(n, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--logs", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = json.load(open(a.results))
    out = {}
    for r in csv.DictReader(open(a.manifest, encoding="utf-8")):
        m = res.get(r["log_id"], {}).get("marsad")
        if not m or not m["has_alarm"]:
            continue
        row = one(str(Path(a.logs) / f"{r['log_id']}.ulg"), r["vehicle_type"])
        row.update(
            hardware=r["hardware"], release=r["release"], vehicle=r["vehicle_type"], design=r["design_subset"] == "true"
        )
        out[r["log_id"]] = row
        fa = row["first_alarm"]
        print(
            r["log_id"][:8],
            r["hardware"][:18],
            f"gap med {row['median_gap_s']:.2f} max {row['max_gap_s']:.1f}",
            fa and fa["dominant"],
            fa and fa["evidence"][:2],
            flush=True,
        )
    json.dump(out, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
