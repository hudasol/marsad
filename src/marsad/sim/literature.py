"""Second scenario family, specified from published attack descriptions (see docs/research/SCENARIOS_LITERATURE.md).

Label for results from it: SIMULATED (LITERATURE). The clean receiver, vehicle track and reference come from the same
generator as the first family (`generate("nominal", ...)`), so the world is shared and so is the author. What differs is
how the attack is specified: from parameter ranges in the cited papers, not from the engine's own design scenarios.
Every mapping from a published quantity to a measurement that the papers do not give is marked ASSUMED in the
document and in the comments below.

SCOPE: measurement edits on simulated fixes only. No RF, waveform or signal synthesis, and no way to affect a real
receiver.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from ..geo import LocalFrame
from .generator import DT, Run, generate

LIT_KINDS = ["lit_switch", "lit_takeover", "lit_time_push", "lit_equal_power", "lit_jam_chirp"]
LIT_TRUTH = {
    "lit_switch": "spoofing_jump",
    "lit_takeover": "spoofing_drift",
    "lit_time_push": "spoofing_drift",
    "lit_equal_power": "spoofing_drift",
    "lit_jam_chirp": "jamming",
}
LIT_BENIGN = ["nominal", "benign_obstruction", "benign_multipath"]


def _kid(kind: str) -> int:
    return sum((i + 1) * ord(c) for i, c in enumerate(kind)) % 100003


def _ramp(tau: np.ndarray, dur: float) -> np.ndarray:
    return np.clip(tau / max(dur, 1e-6), 0.0, 1.0)


def generate_literature(kind: str, seed: int, duration: float = 600.0, cadence: float = DT) -> Run:
    """One run of the literature family. Seeds are independent of the first family's seeds (extra key 77)."""
    if kind not in LIT_KINDS:
        raise KeyError(f"unknown literature scenario {kind!r}; choose from {LIT_KINDS}")
    base = generate("nominal", seed, "dev", duration=duration, cadence=cadence)
    rng = np.random.default_rng([_kid(kind), seed, 77])
    t = base.t
    n = len(t)
    t_a = float(rng.uniform(150.0, 260.0))
    tau = np.clip(t - t_a, 0.0, None)
    on = t >= t_a
    off_e = np.zeros(n)
    off_n = np.zeros(n)
    dvel_e = np.zeros(n)
    dvel_n = np.zeros(n)
    dcn0 = np.zeros(n)
    dagc = np.zeros(n)
    dnsat = np.zeros(n)
    dead = np.zeros(n, bool)  # fix lost
    extra = np.zeros((n, 2))
    ang = float(rng.uniform(0.0, 2.0 * math.pi))
    ux, uy = math.sin(ang), math.cos(ang)
    P: dict = {"t_a": t_a, "angle": ang}
    a_end = None

    def accel_offset(a: float, D: float, hold: float) -> tuple[np.ndarray, np.ndarray]:
        """Distance and speed of a carry off that holds for `hold` s, accelerates at a m/s^2, stops at D metres."""
        tt = np.clip(tau - hold, 0.0, None)
        t_stop = math.sqrt(2.0 * D / a)
        dist = np.where(tt < t_stop, 0.5 * a * tt * tt, D)
        speed = np.where(tt < t_stop, a * tt, 0.0)
        return dist, speed

    if kind == "lit_switch":
        # TEXBAT style switch: the receiver loses the authentic signal, relocks on the spoofer, offset 0 to 450 m
        # (Tippenhauer et al., location offset range). Power advantage 2 to 8 dB (same paper).
        gap = float(rng.uniform(2.0, 6.0))
        D = float(rng.uniform(100.0, 450.0))
        pa = float(rng.uniform(2.0, 8.0))
        P.update(gap=gap, offset_m=D, power_adv_db=pa)
        after = t >= t_a + gap
        dead = (t >= t_a) & ~after
        off_e, off_n = after * D * ux, after * D * uy
        dcn0 = after * (pa + rng.normal(0, 0.3, n))  # ASSUMED: reported C/N0 rises by the power advantage
    elif kind == "lit_takeover":
        # Accelerated takeover: 60 s tracking the spoofer at matched power, then 0.5 m/s^2 toward the target
        # (Tippenhauer et al., Sec. 5.1). Lower accelerations are added to span slower carry offs (ASSUMED).
        a = float(rng.choice([0.05, 0.1, 0.25, 0.5]))
        D = float(rng.uniform(150.0, 450.0))
        pa = float(rng.uniform(2.0, 6.0))
        velc = bool(rng.random() < 0.5)
        P.update(accel=a, offset_m=D, power_adv_db=pa, vel_consistent=velc)
        dist, speed = accel_offset(a, D, 60.0)
        off_e, off_n = dist * ux, dist * uy
        if velc:
            dvel_e, dvel_n = speed * ux, speed * uy
        dcn0 = on * (pa * _ramp(tau, 5.0) + rng.normal(0, 0.3, n))
    elif kind == "lit_time_push":
        # Time push (TEXBAT ds3, ds7 type). A receiver clock offset of up to 240 ns was tolerated (Tippenhauer et al.);
        # 240 ns is 72 m of range. ASSUMED: the position effect is an offset of 20 to 72 m, growing at 0.2 to 2 m/s.
        D = float(rng.uniform(20.0, 72.0))
        rate = float(rng.uniform(0.2, 2.0))
        pa = float(rng.uniform(0.0, 3.0))
        P.update(offset_m=D, rate=rate, power_adv_db=pa)
        dist = np.minimum(rate * tau, D)
        off_e, off_n = dist * ux, dist * uy
        dcn0 = on * (pa * _ramp(tau, 5.0) + rng.normal(0, 0.3, n))
    elif kind == "lit_equal_power":
        # Equal power takeover: at 0 dB the receiver sometimes returned to the true position after about 170 s
        # (Tippenhauer et al., Sec. 5.2). The offset is applied, then removed after 100 to 200 s.
        a = float(rng.choice([0.1, 0.25, 0.5]))
        D = float(rng.uniform(150.0, 450.0))
        back = float(rng.uniform(100.0, 200.0))
        P.update(accel=a, offset_m=D, revert_after_s=back)
        dist, speed = accel_offset(a, D, 60.0)
        gone = tau >= 60.0 + back
        dist = np.where(gone, 0.0, dist)
        off_e, off_n = dist * ux, dist * uy
        a_end = t_a + 60.0 + back
        dvel_e, dvel_n = np.where(gone, 0.0, speed) * ux, np.where(gone, 0.0, speed) * uy
    elif kind == "lit_jam_chirp":
        # Chirp type personal privacy jammer. Average C/N0 fell by about 15 dB at the highest jammer power and the
        # AGC changed strongly (Borio et al.). Drop 6 to 15 dB, rise over 20 to 60 s, hold 60 to 180 s.
        drop = float(rng.uniform(6.0, 15.0))
        rise = float(rng.uniform(20.0, 60.0))
        hold = float(rng.uniform(60.0, 180.0))
        fall = float(rng.uniform(10.0, 30.0))
        agc_rise = float(rng.uniform(0.05, 0.40))  # ASSUMED: the source gives no size for the AGC change
        P.update(cn0_drop_db=drop, rise_s=rise, hold_s=hold, fall_s=fall, agc_rise=agc_rise)
        a_end = t_a + rise + hold + fall
        s = _ramp(tau, rise) * (1.0 - _ramp(np.clip(t - (t_a + rise + hold), 0.0, None), fall))
        dcn0 = -drop * s
        dnsat = -np.round(0.6 * (drop / 15.0) * s * 12.0)  # ASSUMED: satellites fall with the C/N0 drop
        dagc = agc_rise * s
        extra = rng.normal(0, 1.0, (n, 2)) * ((s > 0) * (2.0 + 8.0 * s))[:, None]
        if drop > 12.0:
            dead = (s > 0.8) & (rng.random(n) < 0.5)  # ASSUMED loss of fix at the strongest levels
    else:  # pragma: no cover
        raise KeyError(kind)

    frame = base.frame if base.frame is not None else LocalFrame(*(24.4539, 54.3773))
    samples = []
    stride = max(1, int(round(cadence / DT)))
    obs_e, obs_n = base.obs_e.copy(), base.obs_n.copy()
    for i, s0 in enumerate(base.samples):
        g = s0.gnss
        if g is not None:
            if dead[i]:
                g = None
            else:
                g = replace(g)
                e, nn = frame.to_local(g.lat, g.lon)
                e += off_e[i] + extra[i, 0]
                nn += off_n[i] + extra[i, 1]
                g.lat, g.lon = frame.to_geo(e, nn)
                if g.ve is not None and g.vn is not None:
                    g.ve, g.vn = g.ve + dvel_e[i], g.vn + dvel_n[i]
                if g.cn0_mean is not None:
                    g.cn0_mean += dcn0[i]
                if g.n_sats is not None:
                    g.n_sats = int(max(g.n_sats + dnsat[i], 0))
                    g.fix_type = 3 if g.n_sats >= 4 else 1
                if g.agc is not None:
                    g.agc += dagc[i]
                obs_e[i], obs_n[i] = e, nn
        if dead[i]:
            obs_e[i] = obs_n[i] = np.nan
        samples.append(replace(s0, gnss=g))
    _ = stride
    return Run(
        kind=kind,
        seed=seed,
        split="literature",
        t=t,
        truth_e=base.truth_e,
        truth_n=base.truth_n,
        obs_e=obs_e,
        obs_n=obs_n,
        samples=samples,
        attack_start=t_a,
        attack_end=a_end,
        params=P,
        frame=frame,
    )
