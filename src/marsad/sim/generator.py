"""Measurement-level GNSS scenario simulator.

SCOPE: this module generates *measurements* (positions, velocities, C/N0, AGC, clocks) as a receiver
would report them under a modelled condition. It contains no RF, waveform, signal-synthesis or SDR
code and cannot be used to interfere with a real receiver. All results from it are labelled
"simulated" throughout the project.

Parameter splits: 'dev' ranges are used while tuning detectors; 'heldout' ranges are disjoint or
more adversarial and are only used for the reported benchmark.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..geo import LocalFrame
from ..types import GnssFix, NavSample, RefMotion

ORIGIN = (24.4539, 54.3773)   # arbitrary open-area origin for simulation
DT = 0.2

KINDS = [
    "nominal", "benign_obstruction", "benign_multipath",
    "jam_hard", "jam_soft",
    "spoof_jump", "spoof_jump_transient", "spoof_drift", "spoof_drift_stealth", "replay",
    "spoof_drift_noref", "spoof_drift_ref_outage",
]
SPLITS = ("dev", "heldout")
ATTACK_KINDS = {"jam_hard", "jam_soft", "spoof_jump", "spoof_jump_transient", "spoof_drift",
                "spoof_drift_stealth", "replay", "spoof_drift_noref", "spoof_drift_ref_outage"}
TRUTH_CLASS = {
    "jam_hard": "jamming", "jam_soft": "jamming", "spoof_jump": "spoofing_jump",
    "spoof_jump_transient": "spoofing_jump", "spoof_drift": "spoofing_drift",
    "spoof_drift_stealth": "spoofing_drift", "replay": "replay_meaconing",
    "spoof_drift_noref": "spoofing_drift", "spoof_drift_ref_outage": "spoofing_drift",
    "benign_obstruction": "environmental_degradation", "benign_multipath": "environmental_degradation",
}


@dataclass
class Run:
    kind: str
    seed: int
    split: str
    t: np.ndarray
    truth_e: np.ndarray
    truth_n: np.ndarray
    obs_e: np.ndarray            # raw GNSS-reported position (local frame), NaN if no fix
    obs_n: np.ndarray
    samples: list
    attack_start: Optional[float]
    attack_end: Optional[float]
    params: dict = field(default_factory=dict)
    frame: Optional[LocalFrame] = None

    @property
    def is_attack(self) -> bool:
        return self.kind in ATTACK_KINDS

    @property
    def truth_class(self) -> Optional[str]:
        return TRUTH_CLASS.get(self.kind)


def _trajectory(rng, n):
    speed0 = rng.uniform(8.0, 16.0)
    h = rng.uniform(0, 2 * np.pi)
    e = n_ = 0.0
    out = np.zeros((n, 4))
    target = h
    next_turn = rng.uniform(40, 90)
    for i in range(n):
        t = i * DT
        if t > next_turn:
            target = h + rng.choice([-1, 1]) * rng.choice([np.pi / 2, np.pi, np.pi / 3])
            next_turn = t + rng.uniform(50, 110)
        dh = (target - h + np.pi) % (2 * np.pi) - np.pi
        h += np.clip(dh, -0.35 * DT, 0.35 * DT)
        s = speed0 + 1.5 * np.sin(2 * np.pi * t / 47.0)
        ve, vn = s * np.sin(h), s * np.cos(h)
        e += ve * DT; n_ += vn * DT
        out[i] = (e, n_, ve, vn)
    return out


def _ar1(rng, n, sigma, tau):
    a = np.exp(-DT / tau)
    x = np.zeros((n, 2))
    x[0] = rng.normal(0, sigma, 2)
    w = rng.normal(0, sigma * np.sqrt(1 - a * a), (n, 2))
    for i in range(1, n):
        x[i] = a * x[i - 1] + w[i]
    return x


def _ramp(t, t0, dur):
    return np.clip((t - t0) / max(dur, 1e-6), 0.0, 1.0)


def _draw(kind, rng, split, duration):
    H = split == "heldout"
    p = {}
    p["t_a"] = float(rng.uniform(150, 260)) if duration >= 400 else float(duration * 0.4)
    if kind in ("jam_hard", "jam_soft"):
        p["len"] = float(rng.uniform(40, 100)) if not H else float(rng.uniform(25, 160))
        p["agc_rise"] = float(rng.uniform(0.15, 0.45)) if not H else float(rng.uniform(0.10, 0.5))
    if kind == "jam_soft":
        p["cn0_drop"] = float(rng.uniform(9, 15)) if not H else float(rng.uniform(7, 18))
    if kind in ("spoof_jump", "spoof_jump_transient"):
        p["mag"] = float(rng.uniform(80, 400)) if not H else float(rng.choice([rng.uniform(30, 80), rng.uniform(400, 1500)]))
        p["power_db"] = float(rng.uniform(3, 6)) if not H else float(rng.uniform(1.5, 3.5))
        p["clock_step"] = float(rng.choice([0.0, 0.0, 0.6]))
        p["len"] = float(rng.uniform(60, 120))
    if kind in ("spoof_drift", "spoof_drift_noref", "spoof_drift_ref_outage"):
        p["rate"] = float(rng.uniform(0.3, 1.0)) if not H else float(rng.choice([rng.uniform(0.2, 0.3), rng.uniform(1.0, 2.0)]))
        p["power_db"] = float(rng.uniform(2, 4)) if not H else float(rng.uniform(0.0, 1.5))
        p["vel_consistent"] = bool(rng.random() < 0.5)
    if kind == "spoof_drift_stealth":
        p["rate"] = float(rng.uniform(0.4, 0.8)) if not H else float(rng.uniform(0.25, 0.5))
        p["power_db"] = 0.0
        p["vel_consistent"] = True
    if kind in ("spoof_drift", "spoof_drift_stealth", "spoof_drift_noref", "spoof_drift_ref_outage"):
        p["angle"] = float(rng.uniform(0, 2 * np.pi))
        p["ramp"] = float(rng.uniform(15, 30))
    if kind == "spoof_drift_ref_outage":
        p["outage_start"] = p["t_a"] + float(rng.uniform(-10, 10))
        p["outage_len"] = float(rng.uniform(30, 60))
    if kind == "replay":
        p["delay"] = float(rng.uniform(20, 90)) if not H else float(rng.choice([rng.uniform(8, 20), rng.uniform(90, 200)]))
        p["power_db"] = float(rng.uniform(2, 5)) if not H else float(rng.uniform(0.5, 3))
        p["smart_clock"] = bool(rng.random() < (0.3 if not H else 0.6))
    if kind == "benign_obstruction":
        p["len"] = float(rng.uniform(20, 60))
        p["sat_frac"] = float(rng.uniform(0.35, 0.6))
        p["cn0_drop"] = float(rng.uniform(4, 9))
    if kind == "benign_multipath":
        p["len"] = float(rng.uniform(30, 80))
        p["spike_m"] = float(rng.uniform(5, 12))
    return p


def generate(kind: str, seed: int, split: str = "dev", duration: float = 600.0,
             ref_bias: Optional[float] = None, cadence: float = DT) -> Run:
    if kind not in KINDS:
        raise KeyError(f"unknown scenario {kind!r}; choose from {KINDS}")
    if split not in SPLITS:
        raise KeyError(split)
    rng = np.random.default_rng([abs(hash(kind)) % (2 ** 31) if False else _kind_id(kind), seed, 0 if split == "dev" else 1])
    n = int(duration / DT)
    t = np.arange(n) * DT
    tr = _trajectory(rng, n)
    te, tn, tve, tvn = tr.T
    P = _draw(kind, rng, split, duration)
    t_a = P["t_a"]

    # ---- clean receiver model ----------------------------------------------------------
    err = _ar1(rng, n, 1.2, 30.0) + rng.normal(0, 0.4, (n, 2))
    ve = tve + rng.normal(0, 0.10, n)
    vn = tvn + rng.normal(0, 0.10, n)
    cn0_base = rng.uniform(38.0, 46.0)
    cn0 = cn0_base + rng.normal(0, 0.4, n) + 0.8 * np.sin(2 * np.pi * t / rng.uniform(80, 200))
    cn0sd = np.clip(rng.normal(3.0, 0.3, n), 1.5, None)
    nsat_base = int(rng.integers(10, 17))
    nsat = np.clip(nsat_base + np.round(rng.normal(0, 0.7, n)), 4, None)
    agc_base = rng.uniform(0.25, 0.4)
    agc = agc_base + rng.normal(0, 0.012, n)
    clk_off = rng.uniform(0.5, 5.0)
    tg = t - clk_off + rng.normal(0, 0.002, n)
    valid = np.ones(n, bool)

    # ---- reference (VIO / flow / odometry-like) ----------------------------------------
    bmax = 0.06 if ref_bias is None else ref_bias
    if split == "heldout" and ref_bias is None:
        bmax = 0.08
    b0 = rng.normal(0, 1, 2); b0 = b0 / max(np.linalg.norm(b0), 1e-9) * rng.uniform(0, bmax)
    bias = b0 + np.cumsum(rng.normal(0, 0.0004, (n, 2)), axis=0)
    bias = np.clip(bias, -1.2 * bmax, 1.2 * bmax) if bmax > 0 else bias * 0
    rve = tve + bias[:, 0] + rng.normal(0, 0.15, n)
    rvn = tvn + bias[:, 1] + rng.normal(0, 0.15, n)
    ref_avail = np.ones(n, bool)

    oe = te + err[:, 0]
    on = tn + err[:, 1]
    clean = (oe.copy(), on.copy(), ve.copy(), vn.copy(), cn0.copy(), cn0sd.copy(), nsat.copy(), agc.copy())

    a_end = None
    ia = int(t_a / DT)

    def win(start, length):
        return (t >= start) & (t < start + length)

    if kind == "benign_obstruction":
        w = win(t_a, P["len"]); a_end = t_a + P["len"]
        s = _ramp(t, t_a, 3.0) * (1 - _ramp(t, a_end - 3, 3.0))
        nsat = np.clip(np.round(nsat * (1 - (1 - P["sat_frac"]) * s)), 3, None)
        cn0 = cn0 - P["cn0_drop"] * s
        extra = rng.normal(0, 3.0, (n, 2)) * s[:, None]
        oe, on = oe + extra[:, 0], on + extra[:, 1]
        valid &= ~(w & (nsat < 4))
    elif kind == "benign_multipath":
        w = win(t_a, P["len"]); a_end = t_a + P["len"]
        flick = (rng.random(n) < 0.25) & w
        cn0 = cn0 - np.where(w, rng.uniform(2, 6, n), 0.0) * flick
        nsat = np.where(flick, np.clip(nsat - 3, 4, None), nsat)
        spike = (rng.random(n) < 0.15) & w
        ang = rng.uniform(0, 2 * np.pi, n)
        oe = oe + spike * P["spike_m"] * np.cos(ang) * rng.uniform(0.4, 1.0, n)
        on = on + spike * P["spike_m"] * np.sin(ang) * rng.uniform(0.4, 1.0, n)
    elif kind == "jam_hard":
        a_end = t_a + P["len"]
        s = _ramp(t, t_a, 4.0) * (1 - _ramp(t, a_end, 4.0))
        cn0 = cn0 - 22 * s
        nsat = np.clip(np.round(nsat * (1 - 0.8 * s)), 0, None)
        agc = agc + P["agc_rise"] * s + rng.normal(0, 0.01, n) * s
        valid &= ~(win(t_a + 3.0, P["len"] - 3.0 + 3.0) & (s > 0.6))
    elif kind == "jam_soft":
        a_end = t_a + P["len"]
        s = _ramp(t, t_a, 6.0) * (1 - _ramp(t, a_end, 6.0))
        cn0 = cn0 - P["cn0_drop"] * s
        nsat = np.clip(np.round(nsat * (1 - 0.55 * s)), 4, None)
        agc = agc + 0.6 * P["agc_rise"] * s
        extra = rng.normal(0, 6.0, (n, 2)) * s[:, None]
        oe, on = oe + extra[:, 0], on + extra[:, 1]
        valid &= ~((rng.random(n) < 0.3) & (s > 0.3))
    elif kind in ("spoof_jump", "spoof_jump_transient"):
        ang = rng.uniform(0, 2 * np.pi)
        a_end = (t_a + P["len"]) if kind == "spoof_jump_transient" else None
        on_mask = (t >= t_a) if a_end is None else win(t_a, P["len"])
        oe = oe + on_mask * P["mag"] * np.sin(ang)
        on = on + on_mask * P["mag"] * np.cos(ang)
        cn0 = cn0 + on_mask * (P["power_db"] + rng.normal(0, 0.3, n))
        cn0sd = np.where(on_mask, cn0sd * 0.35, cn0sd)
        tg = tg + on_mask * P["clock_step"]
    elif kind in ("spoof_drift", "spoof_drift_stealth", "spoof_drift_noref", "spoof_drift_ref_outage"):
        dist = np.clip(t - t_a, 0, None) * P["rate"] * _ramp_rate(t, t_a, P["ramp"])
        dist = _drift_dist(t, t_a, P["rate"], P["ramp"])
        ux, uy = np.sin(P["angle"]), np.cos(P["angle"])
        oe = oe + dist * ux
        on = on + dist * uy
        if P["vel_consistent"]:
            rate_t = np.where(t >= t_a, P["rate"] * _ramp(t, t_a, P["ramp"]), 0.0)
            ve = ve + rate_t * ux
            vn = vn + rate_t * uy
        s = _ramp(t, t_a, P["ramp"])
        cn0 = cn0 + P["power_db"] * s
        cn0sd = cn0sd * (1 - 0.6 * s * (P["power_db"] > 0.5))
        if kind == "spoof_drift_noref":
            ref_avail[:] = False
        if kind == "spoof_drift_ref_outage":
            ref_avail &= ~win(P["outage_start"], P["outage_len"])
    elif kind == "replay":
        D = int(P["delay"] / DT)
        on_mask = t >= t_a
        idx = np.clip(np.arange(n) - D, 0, n - 1)
        ce, cnn, cve, cvn, ccn0, ccsd, cns, cagc = clean
        oe = np.where(on_mask, ce[idx], oe)
        on = np.where(on_mask, cnn[idx], on)
        ve = np.where(on_mask, cve[idx], ve)
        vn = np.where(on_mask, cvn[idx], vn)
        cn0 = np.where(on_mask, ccn0[idx] + P["power_db"], cn0)
        cn0sd = np.where(on_mask, ccsd[idx] * 0.6, cn0sd)
        if not P["smart_clock"]:
            tg = np.where(on_mask, tg[idx], tg)

    if kind not in ATTACK_KINDS or a_end is None:
        pass

    # ---- assemble samples -------------------------------------------------------------
    frame = LocalFrame(*ORIGIN)
    samples = []
    obs_e = np.where(valid, oe, np.nan)
    obs_n = np.where(valid, on, np.nan)
    stride = max(1, int(round(cadence / DT)))
    for i in range(n):
        ti = float(t[i])
        gnss = None
        if valid[i] and i % stride == 0:
            lat, lon = frame.to_geo(float(oe[i]), float(on[i]))
            gnss = GnssFix(t=ti, lat=lat, lon=lon, alt=50.0, ve=float(ve[i]), vn=float(vn[i]),
                           cn0_mean=float(cn0[i]), cn0_std=float(cn0sd[i]), n_sats=int(nsat[i]),
                           agc=float(agc[i]), hdop=0.9, fix_type=3 if nsat[i] >= 4 else 1,
                           t_gnss=float(tg[i]))
        ref = RefMotion(t=ti, ve=float(rve[i]), vn=float(rvn[i]), sigma=0.15, source="sim_vio") if ref_avail[i] else None
        samples.append(NavSample(t=ti, gnss=gnss, ref=ref))

    return Run(kind=kind, seed=seed, split=split, t=t, truth_e=te, truth_n=tn, obs_e=obs_e, obs_n=obs_n,
               samples=samples, attack_start=t_a if kind in ATTACK_KINDS else (t_a if kind.startswith("benign") else None),
               attack_end=a_end, params=P, frame=frame)


def _kind_id(kind: str) -> int:
    return sum((i + 1) * ord(c) for i, c in enumerate(kind)) % 100003


def _ramp_rate(t, t0, dur):
    return 1.0


def _drift_dist(t, t_a, rate, ramp):
    """Cumulative displacement for a carry-off whose rate ramps linearly 0->rate over `ramp` seconds."""
    tau = np.clip(t - t_a, 0, None)
    return np.where(tau < ramp, 0.5 * rate * tau * tau / ramp, 0.5 * rate * ramp + rate * (tau - ramp))
