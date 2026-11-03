"""Figures for docs/EVIDENCE.md, drawn from committed result files only.

python scripts/make_evidence_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"
INK, MUTED, GRID = "#222222", "#777777", "#dddddd"
C_M, C_W, C_G = "#1f4e9c", "#c4631a", "#888888"
plt.rcParams.update(
    {"font.size": 9, "axes.edgecolor": MUTED, "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True}
)


def false_alarms() -> None:
    s = json.loads((ROOT / "docs/results/real_corpus/summary.json").read_text())
    n = s["R1_all_trusted"]["n"]
    vals = [
        ("fully TRUSTED", s["R1_all_trusted"]["k"]),
        ("some DENIED", s["R2_any_denied"]["k"]),
        ("plain gate: any alarm", s["R5_baselines_vs_marsad"]["gate"]["flights_with_alarm"]["k"]),
    ]
    fig, ax = plt.subplots(figsize=(5.6, 2.4))
    ax.barh([v[0] for v in vals][::-1], [100 * v[1] / n for v in vals][::-1], color=[C_G, C_M, C_M][::-1])
    for i, v in enumerate(vals[::-1]):
        ax.text(100 * v[1] / n + 1, i, f"{v[1]} of {n}", va="center", color=INK)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of 101 public flights with no attack, %")
    ax.set_title("REAL LOG: engine v1.4.0 on public PX4 flights", loc="left", fontsize=9.5, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "evidence-real-log.png", dpi=200)
    plt.close(fig)


def drift_latency() -> None:
    cases = json.loads((ROOT / "docs/results/real_injected/summary.json").read_text())["arms"]["ekf"]["cases"]
    rates = ["0.25", "0.5", "1.0", "2.0"]
    m = [cases[f"drift_{r}_velcons"]["marsad"]["median_latency_s"] for r in rates]
    w = [cases[f"drift_{r}_velcons"]["window"]["median_latency_s"] for r in rates]
    fig, ax = plt.subplots(figsize=(5.6, 2.8))
    x = range(len(rates))
    ax.bar([i - 0.2 for i in x], m, 0.4, label="Marsad", color=C_M)
    ax.bar([i + 0.2 for i in x], w, 0.4, label="window test", color=C_W)
    ax.set_xticks(list(x), [f"{r} m/s" for r in rates])
    ax.set_ylabel("median latency, s")
    ax.legend(frameon=False)
    ax.set_title("REAL LOG + INJECTED: velocity consistent drift, 52 flights", loc="left", fontsize=9.5, color=INK)
    fig.text(0.01, 0.01, "Logged EKF2 velocity as reference (optimistic bound).", color=MUTED, fontsize=7.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "evidence-drift-latency.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    false_alarms()
    drift_latency()
