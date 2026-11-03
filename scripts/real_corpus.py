"""Real flight corpus study (label REAL LOG). Design and predictions: docs/research/PREREGISTRATION_REAL_CORPUS.md.

    python scripts/real_corpus.py select  --dbinfo dbinfo.json --out candidates.json
    python scripts/real_corpus.py fetch   --candidates candidates.json --logs DIR --manifest MANIFEST.csv [--limit N]
    python scripts/real_corpus.py analyze --manifest MANIFEST.csv --logs DIR --out RESULTS.json
    python scripts/real_corpus.py report  --results RESULTS.json --manifest MANIFEST.csv --out DIR

Log files are read from DIR and are never committed. The manifest holds identifiers, hashes and metadata, no
coordinates. Flight Review logs are published under CC BY.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import subprocess
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Optional

SEED = 20261103
MULTIROTOR = ("Quadrotor", "Hexarotor", "Octorotor")
FIXEDWING = ("Fixed Wing", "VTOL Standard", "Tiltrotor VTOL")
MAX_BYTES = 200 * 1024 * 1024
MIN_GNSS_S = 120.0
MAX_PER_VEHICLE, MAX_PER_HW, MAX_PER_MINOR = 3, 12, 40
GNSS_TOPICS = ("sensor_gps", "vehicle_gps_position", "vehicle_gnss", "sensor_gnss")
REF_TOPICS = {
    "visual odometry": ("vehicle_visual_odometry",),
    "motion capture": ("vehicle_mocap_odometry",),
    "optical flow": ("optical_flow", "sensor_optical_flow", "vehicle_optical_flow", "vehicle_optical_flow_vel"),
    "wheel odometry": ("wheel_encoders",),
}
MANIFEST_FIELDS = [
    "log_id",
    "url",
    "sha256",
    "release",
    "hardware",
    "vehicle_type",
    "gnss_seconds",
    "independent_reference",
    "stratum",
    "design_subset",
    "bytes",
]


# --------------------------------------------------------------------------------------------- statistics
def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two sided binomial interval, by bisection on the binomial CDF (no scipy needed)."""
    if n == 0:
        return (0.0, 1.0)

    def cdf(x: int, p: float) -> float:  # P(X <= x)
        return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, x + 1))

    def solve(f, lo=0.0, hi=1.0):
        for _ in range(80):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p) >= alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p) <= alpha / 2, 0.0, 1.0)
    return lower, upper


def mcnemar_exact(b: int, c: int) -> float:
    """Two sided exact McNemar p value from the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / 2**n
    return min(1.0, p)


# --------------------------------------------------------------------------------------------- episodes
def episodes(times: list, flags: list, merge_s: float = 5.0) -> list:
    """Maximal runs of true flags as [t_start, t_end]; runs closer than merge_s are merged."""
    out: list = []
    start = last = None
    for t, f in zip(times, flags):
        if f:
            if start is None:
                start = t
            last = t
        elif start is not None:
            out.append([start, last])
            start = None
    if start is not None:
        out.append([start, last])
    merged: list = []
    for a, b in out:
        if merged and a - merged[-1][1] <= merge_s:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return merged


def overlap(a: list, b: list, slack: float) -> int:
    """Number of episodes in a that come within slack seconds of any episode in b."""
    return sum(1 for x in a if any(x[0] - slack <= y[1] and y[0] - slack <= x[1] for y in b))


def design_subset(log_id: str) -> bool:
    return int(hashlib.sha256(log_id.encode()).hexdigest(), 16) % 5 == 0


def release_minor(release: str) -> str:
    v = (release or "").split()[0] if (release or "").split() else ""
    parts = v.lstrip("v").split(".")
    return "v" + ".".join(parts[:2]) if len(parts) >= 2 else ""


# --------------------------------------------------------------------------------------------- select
def _version_ok(release: str) -> bool:
    m = release_minor(release)
    if not m:
        return False
    try:
        major, minor = (int(x) for x in m.lstrip("v").split("."))
    except ValueError:
        return False
    return (major, minor) >= (1, 13) and (major, minor) <= (1, 18)


def select_candidates(entries: list, seed: int = SEED, n_main: int = 260, n_err: int = 40) -> list:
    """Fixed, seeded order of candidate logs; the fetch step walks it until enough pass the GNSS check."""

    def eligible(x: dict) -> bool:
        return (
            x.get("estimator") == "EKF2"
            and 240 <= (x.get("duration_s") or 0) <= 3600
            and x.get("mav_type") in MULTIROTOR + FIXEDWING
            and "SITL" not in (x.get("sys_hw") or "")
            and _version_ok(x.get("ver_sw_release") or "")
            and bool(x.get("vehicle_uuid"))
        )

    pool = [x for x in entries if eligible(x)]
    rng = random.Random(seed)

    def draw(items: list, n: int, stratum: str) -> list:
        groups: dict = defaultdict(list)
        for x in items:
            groups[(release_minor(x["ver_sw_release"]), x["sys_hw"])].append(x)
        for g in groups.values():
            rng.shuffle(g)
        keys = sorted(groups)
        rng.shuffle(keys)
        per_vehicle: dict = defaultdict(int)
        per_hw: dict = defaultdict(int)
        per_minor: dict = defaultdict(int)
        out: list = []
        progressed = True
        while len(out) < n and progressed:
            progressed = False
            for k in keys:
                g = groups[k]
                while g:
                    x = g.pop()
                    m = k[0]
                    if per_vehicle[x["vehicle_uuid"]] >= MAX_PER_VEHICLE or per_hw[k[1]] >= MAX_PER_HW:
                        continue
                    if per_minor[m] >= MAX_PER_MINOR:
                        continue
                    per_vehicle[x["vehicle_uuid"]] += 1
                    per_hw[k[1]] += 1
                    per_minor[m] += 1
                    out.append(
                        {
                            "log_id": x["log_id"],
                            "url": x["download_url"],
                            "release": x["ver_sw_release"],
                            "hardware": x["sys_hw"],
                            "vehicle_type": x["mav_type"],
                            "duration_s": x["duration_s"],
                            "stratum": stratum,
                        }
                    )
                    progressed = True
                    break
                if len(out) >= n:
                    break
        return out

    err = [x for x in pool if x.get("error_labels")]
    main = [x for x in pool if not x.get("error_labels")]
    return draw(main, n_main, "main") + draw(err, n_err, "error_labels")


# --------------------------------------------------------------------------------------------- log inspection
def _import_pyulog():
    from pyulog import ULog

    return ULog


def gnss_seconds(ulog) -> float:
    """Seconds spanned by fixes of type 3 or better in the busiest GNSS instance."""
    best = 0.0
    for d in ulog.data_list:
        if d.name not in GNSS_TOPICS:
            continue
        t = d.data["timestamp"] / 1e6
        ft = d.data.get("fix_type")
        if ft is None:
            span = float(t[-1] - t[0]) if len(t) > 1 else 0.0
        else:
            ok = t[ft >= 3]
            span = float(ok[-1] - ok[0]) if len(ok) > 1 else 0.0
        best = max(best, span)
    return best


def independent_references(ulog) -> list:
    names = {d.name for d in ulog.data_list if len(d.data.get("timestamp", [])) > 3}
    return [k for k, tops in REF_TOPICS.items() if any(t in names for t in tops)]


def ekf2_episodes(ulog) -> dict:
    """EKF2's own GNSS accept and reject decisions as episodes, from the aid source and status flag topics."""
    import numpy as np

    out: dict = {"pos_rejected": [], "vel_rejected": [], "fault": [], "topics": []}
    for d in ulog.data_list:
        if d.multi_id != 0:
            continue
        name, f = d.name, d.data
        t = f["timestamp"] / 1e6
        if name in ("estimator_aid_src_gnss_pos", "estimator_aid_src_gnss_vel"):
            if "innovation_rejected" in f:
                rej = np.asarray(f["innovation_rejected"]).astype(bool)
            elif "fused" in f:
                rej = ~np.asarray(f["fused"]).astype(bool)
            else:
                continue
            key = "pos_rejected" if name.endswith("pos") else "vel_rejected"
            out[key] = episodes(list(t), list(rej), merge_s=1.0)
            out["topics"].append(name)
        elif name == "estimator_status_flags":
            flag = np.zeros(len(t), dtype=bool)
            if "cs_gnss_fault" in f:
                flag |= np.asarray(f["cs_gnss_fault"]).astype(bool)
            if "cs_gnss_pos" in f and "cs_in_air" in f:
                flag |= np.asarray(f["cs_in_air"]).astype(bool) & ~np.asarray(f["cs_gnss_pos"]).astype(bool)
            out["fault"] = episodes(list(t), list(flag), merge_s=1.0)
            out["topics"].append(name)
    return out


def longest_run(times: list, flags: list) -> float:
    best = 0.0
    start = None
    for t, f in zip(times, flags):
        if f and start is None:
            start = t
        if f and start is not None:
            best = max(best, t - start)
        if not f:
            start = None
    return best


# --------------------------------------------------------------------------------------------- analysis
def analyze_log(path: str, vehicle_type: str) -> dict:
    from marsad import TrustEngine
    from marsad.adapters.replay import replay_samples
    from marsad.adapters.ulog import load_ulog
    from marsad.bench.baselines import make_baselines
    from marsad.config import preset
    from marsad.types import TrustState

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = load_ulog(path, allow_contaminated=True, warn=False)
    info = data.info
    cfg = preset("uav_fixedwing" if vehicle_type in FIXEDWING else "uav_multirotor")
    eng = TrustEngine(cfg)
    res = replay_samples(data.samples, eng, data.px4_flags, keep_reports=True)
    # every method is scored from the first fix of type 3 or better: before it there is nothing to trust or distrust
    t1 = next((s.t for s in data.samples if s.gnss is not None and s.gnss.fix_type >= 3), None)
    scored = [r for r in res.reports if t1 is not None and r.t >= t1]
    times = [r.t for r in scored]
    bad = [r.state != TrustState.TRUSTED for r in scored]
    den = [r.state == TrustState.DENIED for r in scored]
    m_eps = episodes(times, bad)
    n = max(len(bad), 1)
    out: dict = {
        "n_samples": len(scored),
        "duration_s": (times[-1] - times[0]) if times else 0.0,
        "preset": "uav_fixedwing" if vehicle_type in FIXEDWING else "uav_multirotor",
        "reference_source": info.reference_source,
        "reference_contaminated": bool(info.reference_contaminated),
        "marsad": {
            "has_alarm": any(bad),
            "has_denial": any(den),
            "share_trusted": 1.0 - sum(bad) / n,
            "episodes": m_eps,
            "n_episodes": len(m_eps),
            "min_p_nominal": min((r.probs.get("nominal", 1.0) for r in res.reports), default=1.0),
            "n_rejected_inputs": eng.n_rejected,
        },
        "px4_flags": {
            "available": bool(res.px4_flags_available),
            "flagged_s": res.px4_flagged_s,
            "flagged_marsad_trusted_s": res.px4_flagged_marsad_trusted_s,
        },
    }
    flags = data.px4_flags or []
    if flags:
        ft = [f.t for f in flags]
        jam2 = [(f.jamming_state or 0) >= 2 or (f.spoofing_state or 0) >= 2 for f in flags]
        run = longest_run(ft, jam2)
        out["px4_flags"]["longest_state2_run_s"] = run
        out["px4_flags"]["state2_ge_30s"] = run >= 30.0
        if run >= 30.0:
            ep2 = episodes(ft, jam2, merge_s=1.0)
            out["px4_flags"]["marsad_alarm_within_flagged"] = overlap(m_eps, ep2, 0.0) > 0
    bl = make_baselines()
    counts = dict.fromkeys(bl, 0)
    for s in data.samples:
        for k, b in bl.items():
            st, _ = b.update(s)
            counts[k] += (st != TrustState.TRUSTED) and t1 is not None and s.t >= t1
    out["baselines"] = {k: {"has_alarm": v > 0, "samples_not_trusted": int(v)} for k, v in counts.items()}
    ULog = _import_pyulog()
    ul = ULog(
        path,
        message_name_filter_list=["estimator_aid_src_gnss_pos", "estimator_aid_src_gnss_vel", "estimator_status_flags"],
        disable_str_exceptions=True,
    )
    ek = ekf2_episodes(ul)
    ek_long = [e for e in ek["pos_rejected"] + ek["vel_rejected"] if e[1] - e[0] >= 1.0]
    out["ekf2"] = {
        "topics": ek["topics"],
        "n_pos_rejected": len(ek["pos_rejected"]),
        "n_vel_rejected": len(ek["vel_rejected"]),
        "n_fault": len(ek["fault"]),
        "n_rejected_ge_1s": len(ek_long),
        "marsad_alarm_near_rejection": overlap(ek_long, m_eps, 10.0),
        "marsad_episodes_near_ekf2": overlap(m_eps, ek["pos_rejected"] + ek["vel_rejected"] + ek["fault"], 10.0),
    }
    return out


# --------------------------------------------------------------------------------------------- fetch
def _curl(args: list, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(["curl", "-sS", "-L", "--fail", *args], capture_output=True, text=True, timeout=timeout)


def remote_size(url: str) -> Optional[int]:
    r = _curl(["-I", "-m", "30", url], 60)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines()[::-1]:
        if line.lower().startswith("content-length:"):
            return int(line.split(":")[1].strip())
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_select(a) -> int:
    entries = json.load(open(a.dbinfo))
    cands = select_candidates(entries)
    json.dump(cands, open(a.out, "w"), indent=0)
    print(f"{len(cands)} candidates ({sum(c['stratum'] == 'main' for c in cands)} main)")
    return 0


def cmd_fetch(a) -> int:
    ULog = _import_pyulog()
    logs = Path(a.logs)
    logs.mkdir(parents=True, exist_ok=True)
    cands = json.load(open(a.candidates))
    mpath = Path(a.manifest)
    have = {}
    if mpath.exists():
        have = {r["log_id"]: r for r in csv.DictReader(open(mpath, encoding="utf-8"))}
    rejected_path = mpath.with_name("rejected.csv")
    rejected = {}
    if rejected_path.exists():
        rejected = {r["log_id"]: r for r in csv.DictReader(open(rejected_path, encoding="utf-8"))}
    total = sum(int(r["bytes"]) for r in have.values())
    accepted = {s: sum(1 for r in have.values() if r["stratum"] == s) for s in ("main", "error_labels")}
    targets = {"main": a.target_main, "error_labels": a.target_err}
    done = 0
    for c in cands:
        if a.limit is not None and done >= a.limit:
            break
        if c["log_id"] in have or c["log_id"] in rejected:
            continue
        if accepted[c["stratum"]] >= targets[c["stratum"]]:
            continue
        if total >= a.cap_bytes:
            print("byte cap reached")
            break
        size = remote_size(c["url"])
        if size is None or size > MAX_BYTES:
            rejected[c["log_id"]] = {"log_id": c["log_id"], "reason": f"size {size}"}
            continue
        dest = logs / f"{c['log_id']}.ulg"
        r = _curl(["-m", "900", "-o", str(dest), c["url"]], 1000)
        if r.returncode != 0 or not dest.exists():
            rejected[c["log_id"]] = {"log_id": c["log_id"], "reason": "download failed"}
            continue
        try:
            ul = ULog(str(dest), disable_str_exceptions=True)
            gs = gnss_seconds(ul)
            refs = independent_references(ul)
        except Exception as e:  # a corrupt log is a rejection, recorded with its error class
            gs, refs = 0.0, []
            rejected[c["log_id"]] = {"log_id": c["log_id"], "reason": f"unreadable: {type(e).__name__}"}
            dest.unlink(missing_ok=True)
            continue
        if gs < MIN_GNSS_S:
            rejected[c["log_id"]] = {"log_id": c["log_id"], "reason": f"gnss {gs:.0f} s"}
            dest.unlink(missing_ok=True)
            continue
        have[c["log_id"]] = {
            "log_id": c["log_id"],
            "url": c["url"],
            "sha256": sha256_file(dest),
            "release": c["release"],
            "hardware": c["hardware"],
            "vehicle_type": c["vehicle_type"],
            "gnss_seconds": f"{gs:.0f}",
            "independent_reference": "; ".join(refs) if refs else "none",
            "stratum": c["stratum"],
            "design_subset": str(design_subset(c["log_id"])).lower(),
            "bytes": str(size),
        }
        total += size
        accepted[c["stratum"]] += 1
        done += 1
        print(
            f"accepted {c['log_id']} {c['hardware']} {c['release']} {gs:.0f}s {size / 1e6:.1f} MB (total {total / 1e9:.2f} GB)"
        )
        _write_csv(mpath, MANIFEST_FIELDS, list(have.values()))
        _write_csv(rejected_path, ["log_id", "reason"], list(rejected.values()))
    _write_csv(mpath, MANIFEST_FIELDS, list(have.values()))
    _write_csv(rejected_path, ["log_id", "reason"], list(rejected.values()))
    print(f"manifest {len(have)} logs, {total / 1e9:.2f} GB; rejected {len(rejected)}")
    return 0


def _write_csv(path: Path, fields: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def cmd_analyze(a) -> int:
    rows = list(csv.DictReader(open(a.manifest, encoding="utf-8")))
    out_path = Path(a.out)
    results = json.load(open(out_path)) if out_path.exists() else {}
    for r in rows:
        if r["log_id"] in results:
            continue
        p = Path(a.logs) / f"{r['log_id']}.ulg"
        if not p.exists():
            continue
        try:
            results[r["log_id"]] = analyze_log(str(p), r["vehicle_type"])
        except Exception as e:  # record the failure class; the log stays in the manifest
            results[r["log_id"]] = {"error": f"{type(e).__name__}: {e}"}
        json.dump(results, open(out_path, "w"), indent=1, sort_keys=True)
        print(f"analysed {r['log_id']} ({len(results)}/{len(rows)})", flush=True)
    return 0


# --------------------------------------------------------------------------------------------- report
def _ci(k: int, n: int) -> dict:
    lo, hi = clopper_pearson(k, n)
    d = {"k": k, "n": n, "share": (k / n) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}
    if k == 0 and n:
        d["rule_of_three_upper"] = round(3.0 / n, 4)
    return d


def summarise(results: dict, manifest: list) -> dict:
    meta = {r["log_id"]: r for r in manifest}
    scored = {
        k: v
        for k, v in results.items()
        if "error" not in v and k in meta and meta[k]["design_subset"] == "false" and meta[k]["stratum"] == "main"
    }
    n = len(scored)
    alarm = sum(v["marsad"]["has_alarm"] for v in scored.values())
    denial = sum(v["marsad"]["has_denial"] for v in scored.values())
    trusted_all = n - alarm
    hours = sum(v["duration_s"] for v in scored.values()) / 3600.0
    episodes_total = sum(v["marsad"]["n_episodes"] for v in scored.values())
    s: dict = {
        "label": "REAL LOG",
        "n_scored": n,
        "n_design_subset": sum(1 for k, r in meta.items() if r["design_subset"] == "true" and k in results),
        "n_error_labelled": sum(1 for k, r in meta.items() if r["stratum"] == "error_labels" and k in results),
        "n_failed_to_analyse": sum(1 for v in results.values() if "error" in v),
        "flight_hours": round(hours, 2),
        "R1_all_trusted": _ci(trusted_all, n),
        "R2_any_denied": _ci(denial, n),
        "R3_episodes_per_flight_hour": round(episodes_total / hours, 4) if hours else None,
        "reference": {
            "ekf_fused_contaminated": sum(v["reference_contaminated"] for v in scored.values()),
            "independent": sum(
                (not v["reference_contaminated"]) and bool(v["reference_source"]) for v in scored.values()
            ),
            "none": sum(not v["reference_source"] for v in scored.values()),
        },
    }
    flagged = [v for v in scored.values() if v["px4_flags"].get("state2_ge_30s")]
    s["R4_receiver_state2_ge_30s"] = {
        "n_flights": len(flagged),
        "marsad_stays_trusted": _ci(sum(not v["marsad"]["has_alarm"] for v in flagged), len(flagged)),
    }
    base: dict = {}
    for name in sorted({k for v in scored.values() for k in v["baselines"]}):
        alarms = [v["baselines"][name]["has_alarm"] for v in scored.values()]
        b = sum(1 for m, x in zip((v["marsad"]["has_alarm"] for v in scored.values()), alarms) if x and not m)
        c = sum(1 for m, x in zip((v["marsad"]["has_alarm"] for v in scored.values()), alarms) if m and not x)
        base[name] = {
            "flights_with_alarm": _ci(sum(alarms), n),
            "baseline_only": b,
            "marsad_only": c,
            "mcnemar_exact_p": round(mcnemar_exact(b, c), 6),
        }
    s["R5_baselines_vs_marsad"] = base
    with_ekf = [v for v in scored.values() if v["ekf2"]["topics"]]
    ek_flights = [v for v in with_ekf if v["ekf2"]["n_rejected_ge_1s"] > 0]
    s["R6_ekf2"] = {
        "flights_with_ekf2_topics": len(with_ekf),
        "flights_with_rejection_ge_1s": _ci(len(ek_flights), len(with_ekf)),
        "of_those_with_marsad_alarm_within_10s": _ci(
            sum(v["ekf2"]["marsad_alarm_near_rejection"] > 0 for v in ek_flights), len(ek_flights)
        ),
        "marsad_episodes_total": episodes_total,
        "marsad_episodes_near_ekf2_episode": sum(v["ekf2"]["marsad_episodes_near_ekf2"] for v in scored.values()),
    }
    strata: dict = {}
    for keyname, keyfn in (("release", lambda r: release_minor(r["release"])), ("hardware", lambda r: r["hardware"])):
        groups: dict = defaultdict(list)
        for k, v in scored.items():
            groups[keyfn(meta[k])].append(v)
        strata[keyname] = {
            g: {
                "n": len(vs),
                "alarm": _ci(sum(x["marsad"]["has_alarm"] for x in vs), len(vs)),
                "denial": _ci(sum(x["marsad"]["has_denial"] for x in vs), len(vs)),
            }
            for g, vs in sorted(groups.items())
        }
    s["strata"] = strata
    s["R7_denial_upper_by_release"] = {g: d["denial"]["ci95"][1] for g, d in strata["release"].items() if d["n"] >= 10}
    s["alarmed_flights"] = sorted(k for k, v in scored.items() if v["marsad"]["has_alarm"])
    s["versions"] = sorted({release_minor(meta[k]["release"]) for k in scored})
    s["hardware_types"] = len({meta[k]["hardware"] for k in scored})
    return s


def cmd_report(a) -> int:
    results = json.load(open(a.results))
    manifest = list(csv.DictReader(open(a.manifest, encoding="utf-8")))
    s = summarise(results, manifest)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump(s, open(out / "summary.json", "w"), indent=1, sort_keys=True)
    lines = [
        "# Real flight corpus summary (REAL LOG)",
        "",
        f"Scored flights: {s['n_scored']}, flight hours: {s['flight_hours']}",
        "",
    ]
    r1, r2 = s["R1_all_trusted"], s["R2_any_denied"]
    lines += [
        "| quantity | k / n | share | 95% interval |",
        "|---|---|---|---|",
        f"| flights 100% TRUSTED | {r1['k']} / {r1['n']} | {r1['share']} | {r1['ci95']} |",
        f"| flights with any DENIED | {r2['k']} / {r2['n']} | {r2['share']} | {r2['ci95']} |",
        "",
        f"Alarm episodes per flight hour: {s['R3_episodes_per_flight_hour']}",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: s[k] for k in ("n_scored", "R1_all_trusted", "R2_any_denied", "R3_episodes_per_flight_hour")}))
    return 0


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--dbinfo", required=True)
    s.add_argument("--out", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--candidates", required=True)
    f.add_argument("--logs", required=True)
    f.add_argument("--manifest", required=True)
    f.add_argument("--limit", type=int)
    f.add_argument("--target-main", type=int, default=130)
    f.add_argument("--target-err", type=int, default=15)
    f.add_argument("--cap-bytes", type=int, default=6 * 10**9)
    an = sub.add_parser("analyze")
    an.add_argument("--manifest", required=True)
    an.add_argument("--logs", required=True)
    an.add_argument("--out", required=True)
    r = sub.add_parser("report")
    r.add_argument("--results", required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True)
    a = p.parse_args(argv)
    return {"select": cmd_select, "fetch": cmd_fetch, "analyze": cmd_analyze, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
