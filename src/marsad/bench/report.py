"""Markdown report for benchmark summaries."""
from __future__ import annotations


def _f(x, nd=1, pct=False):
    if x is None:
        return "–"
    return f"{100*x:.0f}%" if pct else f"{x:.{nd}f}"


def markdown(summary: dict, title: str, meta: str = "") -> str:
    attack = {k: v for k, v in summary.items() if "alarm_rate_marsad" in v}
    benign = {k: v for k, v in summary.items() if "alarm_rate_marsad" not in v}
    L = [f"### {title}", "", meta, "", "**Attack and interference scenarios** (SIMULATED)", "",
         "| scenario | n | detected (Marsad) | detected (gate baseline) | latency med / p90 (s), Marsad | latency med (s), baseline | max nav error med (m): Marsad / baseline / raw GNSS | class acc. at first alarm / settled (fine) | no-fallback time |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, v in attack.items():
        L.append(f"| `{k}` | {v['n']} | {_f(v['alarm_rate_marsad'],pct=True)} | {_f(v['alarm_rate_base'],pct=True)} | "
                 f"{_f(v['lat_alarm_med_marsad'])} / {_f(v['lat_alarm_p90_marsad'])} | {_f(v['lat_alarm_med_base'])} | "
                 f"{_f(v['err_max_med_marsad'],0)} / {_f(v['err_max_med_base'],0)} / {_f(v['err_max_med_raw'],0)} | "
                 f"{_f(v['label_acc_coarse'],pct=True)} (coarse) / {_f(v.get('label_settled_acc'),pct=True)} | {_f(v['hold_frac_marsad'],pct=True)} |")
    L += ["", "**Benign conditions** (false-alarm behaviour, SIMULATED)", "",
          "| scenario | n | time not-TRUSTED, Marsad | runs reaching DENIED, Marsad | time DENIED, baseline | runs reaching DENIED, baseline |",
          "|---|---|---|---|---|---|"]
    for k, v in benign.items():
        L.append(f"| `{k}` | {v['n']} | {_f(v['alarm_frac_marsad'],pct=True)} | {_f(v['runs_with_deny_marsad'],pct=True)} | "
                 f"{_f(v['deny_frac_base'],pct=True)} | {_f(v['runs_with_deny_base'],pct=True)} |")
    return "\n".join(L) + "\n"
