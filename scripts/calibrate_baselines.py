"""Calibrate the free parameters of the baselines on NOMINAL DEV scenarios only (never on held out seeds).

    python scripts/calibrate_baselines.py [--seeds 20]

Prints, per baseline, the fraction of nominal dev time spent not TRUSTED with the shipped defaults, and the
nominal distribution of the quantities the thresholds are compared with, so the defaults in
marsad/bench/baselines.py can be checked. Attack and benign-stress scenarios are not used here.
"""

import argparse

import numpy as np

from marsad.bench.baselines import make_baselines
from marsad.sim import generate
from marsad.types import TrustState


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    a = ap.parse_args()
    frac = {k: [] for k in make_baselines()}
    d_agc, d_cn0 = [], []
    for seed in range(a.seeds):
        run = generate("nominal", seed, "dev")
        bs = make_baselines()
        n_bad = {k: 0 for k in bs}
        m_agc = m_cn0 = None
        for s in run.samples:
            for k, b in bs.items():
                st, _ = b.update(s)
                n_bad[k] += st != TrustState.TRUSTED
            g = s.gnss
            if g is not None and g.agc is not None:
                m_agc = g.agc if m_agc is None else m_agc + (0.2 / 120.0) * (g.agc - m_agc)
                m_cn0 = g.cn0_mean if m_cn0 is None else m_cn0 + (0.2 / 120.0) * (g.cn0_mean - m_cn0)
                d_agc.append(abs(g.agc - m_agc))
                d_cn0.append(abs(g.cn0_mean - m_cn0))
        for k in frac:
            frac[k].append(n_bad[k] / len(run.samples))
    print(f"nominal dev, {a.seeds} seeds: time not TRUSTED with the shipped defaults")
    for k, v in frac.items():
        print(f"  {k:10s} mean {100 * np.mean(v):.2f}%   worst run {100 * np.max(v):.2f}%")
    print(
        f"  |AGC - running mean|  p99.9 {np.percentile(d_agc, 99.9):.3f}  max {max(d_agc):.3f}  (agc_step default 0.077)"
    )
    print(f"  |C/N0 - running mean| p99.9 {np.percentile(d_cn0, 99.9):.2f} dB (cn0_step default 3.5)")


if __name__ == "__main__":
    main()
