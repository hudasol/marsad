"""Score the runs of scripts/sitl_ekf2_spoof.py (label: SITL EKF2).

  python scripts/sitl_ekf2_score.py --runs DIR --out docs/results/sitl_ekf2

For each run: Marsad and the baselines replay the ULog with two reference arms (EKF fused velocity, simulator truth
velocity). The onset is read from the log itself (the time SIM_SPF_ON changed to 1). EKF2's own response is read from
estimator_aid_src_gnss_pos / _vel (rejections), estimator_status_flags (GNSS fault) and the distance between the EKF2
position estimate and the simulator truth.
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_corpus import episodes  # noqa: E402
from sih_inject import groundtruth_ref  # noqa: E402

from marsad import TrustEngine, preset  # noqa: E402
from marsad.adapters.ulog import load_ulog  # noqa: E402
from marsad.bench.baselines import make_baselines  # noqa: E402
from marsad.types import TrustState  # noqa: E402

METHODS = ("marsad", "gate", "ekf2_gate_ref", "window", "stack")


def onset_time(ulog) -> float | None:
    for ts, key, val in ulog.changed_parameters:
        if key == "SIM_SPF_ON" and int(val) == 1:
            return ts / 1e6
    return None


def score_samples(samples, t_on):
    eng, bl = TrustEngine(preset("uav_multirotor")), make_baselines()
    first = dict.fromkeys(METHODS)
    pre = dict.fromkeys(METHODS, False)
    t1 = next((s.t for s in samples if s.gnss is not None and s.gnss.fix_type >= 3), None)
    denied = None
    for s in samples:
        r = eng.update(s)
        st = {"marsad": r.state}
        for k in ("gate", "ekf2_gate_ref", "window", "stack"):
            st[k], _ = bl[k].update(s)
        if t1 is None or s.t < t1:
            continue
        for m, v in st.items():
            if v == TrustState.TRUSTED:
                continue
            if t_on is None or s.t < t_on:
                pre[m] = True
            elif first[m] is None:
                first[m] = s.t
                if m == "marsad":
                    denied = v == TrustState.DENIED
    return first, pre, denied


def ekf2_response(ulog, t_on):
    d = {x.name: x.data for x in ulog.data_list}
    out = {}
    for topic in ("estimator_aid_src_gnss_pos", "estimator_aid_src_gnss_vel"):
        if topic in d and "innovation_rejected" in d[topic]:
            t = d[topic]["timestamp"] / 1e6
            rej = np.asarray(d[topic]["innovation_rejected"], bool) | ~np.asarray(
                d[topic].get("fused", np.ones(len(t))), bool
            )
            mask = t >= (t_on if t_on is not None else 0)
            eps = [e for e in episodes(list(t[mask]), list(rej[mask]), merge_s=1.0)]
            out[topic] = {"n_episodes": len(eps), "longest_s": max((b - a for a, b in eps), default=0.0)}
    if "estimator_status_flags" in d and "cs_gnss_fault" in d["estimator_status_flags"]:
        t = d["estimator_status_flags"]["timestamp"] / 1e6
        f = np.asarray(d["estimator_status_flags"]["cs_gnss_fault"], bool)
        out["cs_gnss_fault_after_onset"] = bool((f & (t >= (t_on or 0))).any())
    lp, gt = d.get("vehicle_local_position"), d.get("vehicle_local_position_groundtruth")
    if lp is not None and gt is not None and t_on is not None:
        tl, tg = lp["timestamp"] / 1e6, gt["timestamp"] / 1e6
        ex = np.interp(tl, tg, gt["x"])
        ey = np.interp(tl, tg, gt["y"])
        err = np.hypot(lp["x"] - ex, lp["y"] - ey)
        for dt in (10, 30, 60, 120):
            i = int(np.searchsorted(tl, t_on + dt))
            if i < len(tl):
                out[f"ekf_pos_err_m_at_{dt}s"] = float(err[i])
        out["ekf_pos_err_m_max_after"] = float(err[tl >= t_on].max()) if (tl >= t_on).any() else None
        out["ekf_pos_err_m_before"] = float(err[tl < t_on].max()) if (tl < t_on).any() else None
    return out


def summarise(rows: list) -> str:
    """Markdown table: per case, detections out of runs for each method and arm, and what EKF2 itself did."""
    from real_corpus import clopper_pearson

    cells: dict = {}
    for r in rows:
        key = r["case"] + (
            ""
            if r["case"] == "clean" or r["case"].startswith("jump")
            else (" velocity consistent" if r["velcons"] else " position only")
        )
        cells.setdefault(key, []).append(r)
    lines = [
        "# PX4 EKF2 in the loop (SITL EKF2)",
        "",
        "n is 4 runs per case (four headings). Detection counts are runs in which the method left TRUSTED after the onset.",
        "Arm ekf: reference is EKF2 fused velocity. Arm truth: reference is simulator truth velocity.",
        "",
        "| case | Marsad ekf arm | 95% CI | median latency s | Marsad truth arm | gate | window | stack | EKF2 rejection of 1 s or longer | EKF2 position error at 60 s, m |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, v in sorted(cells.items()):
        n = len(v)
        k = sum(1 for x in v if x["ekf"]["latency_s"]["marsad"] is not None)
        lo, hi = clopper_pearson(k, n)
        lat = sorted(x["ekf"]["latency_s"]["marsad"] for x in v if x["ekf"]["latency_s"]["marsad"] is not None)
        med = f"{lat[len(lat) // 2]:.1f}" if lat else "n/a"
        kt = sum(1 for x in v if x["truth"]["latency_s"]["marsad"] is not None)

        cnt = {m: sum(1 for x in v if x["ekf"]["latency_s"][m] is not None) for m in METHODS}

        rej = sum(
            1
            for x in v
            if max(
                x["ekf2"].get("estimator_aid_src_gnss_pos", {}).get("longest_s", 0.0),
                x["ekf2"].get("estimator_aid_src_gnss_vel", {}).get("longest_s", 0.0),
            )
            >= 1.0
        )
        errs = sorted(round(x["ekf2"]["ekf_pos_err_m_at_60s"]) for x in v if "ekf_pos_err_m_at_60s" in x["ekf2"])
        err_txt = f"{errs[0]} to {errs[-1]}" if errs else "n/a"
        lines.append(
            f"| {key} | {k}/{n} | {lo:.2f} to {hi:.2f} | {med} | {kt}/{n} | {cnt['gate']}/{n} | {cnt['window']}/{n} | {cnt['stack']}/{n} | {rej}/{n} | {err_txt} |"
        )
    lines += [
        "",
        f"Runs with a Marsad or baseline alarm before the onset: {sum(1 for r in rows for a in ('ekf', 'truth') if any(r[a]['pre_alarm'].values()))}",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-only", action="store_true", help="rebuild summary.md from an existing runs.json")
    a = ap.parse_args(argv)
    if a.summary_only:
        rows = json.load(open(Path(a.out) / "runs.json"))["runs"]
        (Path(a.out) / "summary.md").write_text(summarise(rows))
        return 0
    from pyulog import ULog

    rows = []
    for meta_path in sorted(Path(a.runs).glob("*.json")):
        meta = json.load(open(meta_path))
        if not meta.get("ulog"):
            continue
        ulg = Path(a.runs) / f"{meta['name']}.ulg"
        ul = ULog(str(ulg), disable_str_exceptions=True)
        t_on = onset_time(ul)
        row = {
            "name": meta["name"],
            "case": meta["case"],
            "heading": meta["heading"],
            "velcons": meta["velcons"],
            "onset_log_s": t_on,
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = load_ulog(str(ulg), allow_contaminated=True, warn=False)
        row["reference_source"] = data.info.reference_source
        arms = {"ekf": data.samples}
        try:
            arms["truth"], _ = groundtruth_ref(str(ulg), data.samples)
        except SystemExit as e:
            row["truth_arm_error"] = str(e)
        for arm, smp in arms.items():
            first, pre, den = score_samples(smp, t_on)
            row[arm] = {
                "latency_s": {m: (None if first[m] is None or t_on is None else first[m] - t_on) for m in METHODS},
                "pre_alarm": pre,
                "marsad_denied_at_first": den,
            }
        row["ekf2"] = ekf2_response(ul, t_on)
        if t_on is not None and "drift" in meta["case"]:
            row["case_rate"] = float(meta["case"].split(":")[1])
        rows.append(row)
        print(meta["name"], row["ekf"]["latency_s"]["marsad"], flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump({"runs": rows}, open(out / "runs.json", "w"), indent=1)
    (out / "summary.md").write_text(summarise(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
