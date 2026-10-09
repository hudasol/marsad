"""Figures for docs (SIMULATED data)."""
import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from marsad import TrustEngine, preset, TrustState
from marsad.sim import generate

BG, FG, GRID = "#0d1117", "#c9d1d9", "#30363d"
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "axes.edgecolor": GRID, "axes.labelcolor": FG,
                     "xtick.color": FG, "ytick.color": FG, "text.color": FG, "axes.grid": True, "grid.color": GRID,
                     "font.size": 9})

def case(kind, seed, split, fname, title):
    r = generate(kind, seed, split)
    eng = TrustEngine(preset("uav_multirotor"))
    t, raw, nav, st, tr = [], [], [], [], []
    for i, s in enumerate(r.samples):
        rep = eng.update(s)
        t.append(s.t); st.append(rep.state.value); tr.append(rep.trust)
        raw.append(math.nan if math.isnan(r.obs_e[i]) else math.hypot(r.obs_e[i]-r.truth_e[i], r.obs_n[i]-r.truth_n[i]))
        nav.append(math.nan if rep.nav_e is None or rep.action.value == "HOLD_AND_ALERT" else math.hypot(rep.nav_e-r.truth_e[i], rep.nav_n-r.truth_n[i]))
    t = np.array(t)
    fig, ax = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True, gridspec_kw={"height_ratios": [3, 1.2]})
    ax[0].plot(t, raw, color="#d2a8ff", lw=1.2, label="raw GNSS error (what the vehicle would fly)")
    ax[0].plot(t, nav, color="#58a6ff", lw=1.6, label="Marsad-advised position error")
    ax[0].axvline(r.attack_start, color="#f0883e", ls=":", lw=1.2); ax[0].text(r.attack_start+4, ax[0].get_ylim()[1]*0.45, "attack onset", color="#f0883e")
    ax[0].set_ylabel("error vs truth (m)"); ax[0].legend(loc="upper left", frameon=False); ax[0].set_title(title + "  [SIMULATED]")
    col = {"TRUSTED": "#3fb950", "DEGRADED": "#d29922", "DENIED": "#f85149"}
    for i in range(len(t)-1):
        ax[1].axvspan(t[i], t[i+1], color=col[st[i]], alpha=0.85, lw=0)
    ax[1].set_yticks([]); ax[1].set_xlabel("time (s)"); ax[1].grid(False)
    for k, c in col.items(): ax[1].plot([], [], color=c, lw=6, label=k)
    ax[1].legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.55), frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=150); plt.close(fig)

case("spoof_drift_stealth", 4, "dev", "docs/img/case-carry-off.png", "Stealth carry-off: GNSS drifts away at ~0.5 m/s")
case("jam_hard", 3, "dev", "docs/img/case-jamming.png", "Hard jamming and recovery")
case("spoof_jump_transient", 2, "dev", "docs/img/case-jump.png", "Position takeover (transient), no silent re-trust")

sw = json.load(open("docs/results/detectability.json"))
rates = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0]; biases = [0.0, 0.04, 0.08]
M = np.array([[100*sw[f"{b}|{r}"]["detect"] for r in rates] for b in biases])
fig, ax = plt.subplots(figsize=(6.4, 2.8))
im = ax.imshow(M, cmap="viridis", vmin=0, vmax=100, aspect="auto")
ax.set_xticks(range(len(rates))); ax.set_xticklabels([str(r) for r in rates]); ax.set_yticks(range(len(biases))); ax.set_yticklabels([str(b) for b in biases])
ax.set_xlabel("carry-off drift rate (m/s)"); ax.set_ylabel("reference bias (m/s)"); ax.grid(False)
for i in range(len(biases)):
    for j in range(len(rates)):
        ax.text(j, i, f"{M[i,j]:.0f}%", ha="center", va="center", color="white" if M[i,j] < 60 else "black", fontsize=8)
ax.set_title("Stealth carry-off detection rate vs drift and reference quality [SIMULATED]")
fig.tight_layout(); fig.savefig("docs/img/detectability.png", dpi=150)
print("ok")
