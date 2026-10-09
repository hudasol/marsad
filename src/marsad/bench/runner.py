"""Benchmark harness: run scenarios through Marsad and the gate baseline; compute metrics.

All numbers it produces are SIMULATED (measurement-level scenarios from marsad.sim).
"""
from __future__ import annotations
import json
import math
import statistics as st
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

import numpy as np

from ..config import EngineConfig, preset
from ..engine import TrustEngine
from ..sim import generate, KINDS, ATTACK_KINDS
from ..sim.generator import TRUTH_CLASS
from ..types import TrustState
from .baseline import GateBaseline


def _nav_err(nav_e, nav_n, te, tn):
    if nav_e is None or nav_n is None:
        return float("nan")
    return math.hypot(nav_e - te, nav_n - tn)


def evaluate_run(kind: str, seed: int, split: str, cfg: Optional[EngineConfig] = None,
                 disable: Optional[set] = None, duration: float = 600.0, ref_bias: Optional[float] = None,
                 overrides: Optional[dict] = None) -> dict:
    run = generate(kind, seed, split, duration=duration, ref_bias=ref_bias, overrides=overrides)
    eng = TrustEngine(cfg or preset("uav_multirotor"), disable=disable)
    base = GateBaseline()
    t_a, t_b = run.attack_start, run.attack_end
    ts = run.t
    n = len(run.samples)
    m_state = np.zeros(n, np.int8); b_state = np.zeros(n, np.int8)
    m_err = np.full(n, np.nan); b_err = np.full(n, np.nan); raw_err = np.full(n, np.nan)
    dom = [""] * n
    hold = np.zeros(n, bool)
    order = {TrustState.TRUSTED: 0, TrustState.DEGRADED: 1, TrustState.DENIED: 2}
    for i, s in enumerate(run.samples):
        rep = eng.update(s)
        m_state[i] = order[rep.state]
        m_err[i] = (float('nan') if rep.action.value == 'HOLD_AND_ALERT'
                    else _nav_err(rep.nav_e, rep.nav_n, run.truth_e[i], run.truth_n[i]))
        hold[i] = rep.action.value == 'HOLD_AND_ALERT'
        dom[i] = rep.dominant
        bs, bpos = base.update(s)
        b_state[i] = order[bs]
        b_err[i] = _nav_err(*(bpos or (None, None)), run.truth_e[i], run.truth_n[i])
        if not math.isnan(run.obs_e[i]):
            raw_err[i] = math.hypot(run.obs_e[i] - run.truth_e[i], run.obs_n[i] - run.truth_n[i])

    out = {"kind": kind, "seed": seed, "split": split, "attack": kind in ATTACK_KINDS}
    pre = ts < (t_a if t_a is not None else 1e18)
    out["pre_alarm_frac_marsad"] = float((m_state[pre] > 0).mean()) if pre.any() else 0.0
    out["pre_alarm_frac_base"] = float((b_state[pre] > 0).mean()) if pre.any() else 0.0
    if t_a is None:   # nominal
        out["alarm_frac_marsad"] = float((m_state > 0).mean())
        out["deny_frac_marsad"] = float((m_state == 2).mean())
        out["alarm_frac_base"] = float((b_state > 0).mean())
        out["deny_frac_base"] = float((b_state == 2).mean())
        out["err_p95_marsad"] = float(np.nanpercentile(m_err, 95))
        out["err_max_marsad"] = float(np.nanmax(m_err))
        return out
    end = t_b if t_b is not None else ts[-1] + 1
    act = (ts >= t_a) & (ts < end)
    post = ts >= t_a

    def first(mask_state, thr):
        idx = np.where(post & (mask_state >= thr))[0]
        return float(ts[idx[0]] - t_a) if len(idx) else None

    out["lat_alarm_marsad"] = first(m_state, 1)
    out["lat_deny_marsad"] = first(m_state, 2)
    out["lat_alarm_base"] = first(b_state, 1)
    out["lat_deny_base"] = first(b_state, 2)
    out["alarm_frac_marsad"] = float((m_state[act] > 0).mean())
    out["deny_frac_marsad"] = float((m_state[act] == 2).mean())
    out["alarm_frac_base"] = float((b_state[act] > 0).mean())
    out["deny_frac_base"] = float((b_state[act] == 2).mean())
    # navigation error after onset (what the vehicle would actually fly on)
    sel = post & ~np.isnan(m_err)
    out["err_max_marsad"] = float(np.nanmax(m_err[sel])) if sel.any() else None
    out["err_p95_marsad"] = float(np.nanpercentile(m_err[sel], 95)) if sel.any() else None
    selb = post & ~np.isnan(b_err)
    out["err_max_base"] = float(np.nanmax(b_err[selb])) if selb.any() else None
    out["err_p95_base"] = float(np.nanpercentile(b_err[selb], 95)) if selb.any() else None
    selr = post & ~np.isnan(raw_err)
    out["err_max_raw"] = float(np.nanmax(raw_err[selr])) if selr.any() else None
    # classification at first denial (or alarm)
    i_first = None
    for thr in (2, 1):
        idx = np.where(post & (m_state >= thr))[0]
        if len(idx):
            i_first = idx[min(len(idx) - 1, 5)]   # allow 5 samples for the label to settle
            break
    out["label"] = dom[i_first] if i_first is not None else None
    out["hold_frac_marsad"] = float(hold[post].mean())
    # settled label: dominant hypothesis 60 s after the first alarm (or just before attack end), while still alarmed
    la = out.get('lat_alarm_marsad')
    j = int(min(np.searchsorted(ts, t_a + (la or 0.0) + 60.0), (np.searchsorted(ts, t_b - 2.0) if t_b is not None else n) - 1, n - 1))
    out["label_settled"] = dom[j] if m_state[j] > 0 and dom[j] not in ("", "none") else None
    out["truth_class"] = TRUTH_CLASS.get(kind)
    out["final_state_marsad"] = int(m_state[-1])
    if t_b is not None and t_b < ts[-1]:
        idx = np.where((ts >= t_b) & (m_state == 0))[0]
        out["recover_s_marsad"] = float(ts[idx[0]] - t_b) if len(idx) else None
    return out


def _job(args):
    kind, seed, split, disable, ref_bias, overrides = args
    return evaluate_run(kind, seed, split, disable=set(disable) if disable else None, ref_bias=ref_bias,
                        overrides=dict(overrides) if overrides else None)


def run_benchmark(split="heldout", seeds=range(30), kinds=None, disable=None, ref_bias=None, workers=0, overrides=None):
    kinds = list(kinds or KINDS)
    jobs = [(k, s, split, tuple(disable or ()), ref_bias, tuple((overrides or {}).items())) for k in kinds for s in seeds]
    if workers and workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            res = list(ex.map(_job, jobs, chunksize=4))
    else:
        res = [_job(j) for j in jobs]
    return res


def _coarse(c):
    if c in ("spoofing_jump", "spoofing_drift", "replay_meaconing", "spoofing_unclassified"):
        return "spoofing"
    return c


def _med(x):
    x = [v for v in x if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return float(np.median(x)) if x else None


def _p90(x):
    x = [v for v in x if v is not None]
    return float(np.percentile(x, 90)) if x else None


def summarize(results: list) -> dict:
    by = {}
    for r in results:
        by.setdefault(r["kind"], []).append(r)
    rows = {}
    for kind, rs in by.items():
        n = len(rs)
        row = {"n": n}
        if rs[0]["attack"]:
            row["alarm_rate_marsad"] = sum(r["lat_alarm_marsad"] is not None for r in rs) / n
            row["deny_rate_marsad"] = sum(r["lat_deny_marsad"] is not None for r in rs) / n
            row["alarm_rate_base"] = sum(r["lat_alarm_base"] is not None for r in rs) / n
            row["lat_alarm_med_marsad"] = _med([r["lat_alarm_marsad"] for r in rs])
            row["lat_alarm_p90_marsad"] = _p90([r["lat_alarm_marsad"] for r in rs])
            row["lat_alarm_med_base"] = _med([r["lat_alarm_base"] for r in rs])
            row["err_max_med_marsad"] = _med([r["err_max_marsad"] for r in rs])
            row["err_max_med_base"] = _med([r["err_max_base"] for r in rs])
            row["err_max_med_raw"] = _med([r["err_max_raw"] for r in rs])
            lab = [r for r in rs if r["label"] is not None]
            row["label_acc"] = (sum(r["label"] == r["truth_class"] for r in lab) / len(lab)) if lab else None
            lab2 = [r for r in rs if r.get("label_settled") is not None]
            row["label_settled_acc"] = (sum(r["label_settled"] == r["truth_class"] for r in lab2) / len(lab2)) if lab2 else None
            row["label_settled_coarse"] = (sum(_coarse(r["label_settled"]) == _coarse(r["truth_class"]) for r in lab2) / len(lab2)) if lab2 else None
            row["label_acc_coarse"] = (sum(_coarse(r["label"]) == _coarse(r["truth_class"]) for r in lab) / len(lab)) if lab else None
            row["hold_frac_marsad"] = float(np.mean([r["hold_frac_marsad"] for r in rs]))
            row["pre_alarm_frac_marsad"] = float(np.mean([r["pre_alarm_frac_marsad"] for r in rs]))
            row["recover_med_marsad"] = _med([r.get("recover_s_marsad") for r in rs])
        else:
            row["alarm_frac_marsad"] = float(np.mean([r["alarm_frac_marsad"] for r in rs]))
            row["deny_frac_marsad"] = float(np.mean([r["deny_frac_marsad"] for r in rs]))
            row["alarm_frac_base"] = float(np.mean([r["alarm_frac_base"] for r in rs]))
            row["deny_frac_base"] = float(np.mean([r["deny_frac_base"] for r in rs]))
            row["runs_with_deny_marsad"] = sum(r["deny_frac_marsad"] > 0 for r in rs) / n
            row["runs_with_deny_base"] = sum(r["deny_frac_base"] > 0 for r in rs) / n
            row["err_p95_med_marsad"] = _med([r["err_p95_marsad"] for r in rs])
        rows[kind] = row
    return rows
