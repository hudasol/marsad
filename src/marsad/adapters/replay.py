"""Replay a NavSample stream through the engine and summarise: state transitions with evidence, plus a
comparison against the receiver's/autopilot's own jamming/spoofing flags (PX4 ULog or MAVLink GNSS_INTEGRITY)."""
from __future__ import annotations
import bisect
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

from ..types import NavSample, TrustReport, TrustState
from ._common import SYNTHETIC_BANNER

_FLAG_NAME = {None: "n/a", 0: "unk", 1: "ok", 2: "WARN", 3: "ALARM"}


def flag_label(jam, spoof) -> str:
    return f"jam={_FLAG_NAME.get(jam, jam)} spoof={_FLAG_NAME.get(spoof, spoof)}"


@dataclass
class Transition:
    t: float
    state: str
    trust: float
    dominant: str
    summary: str
    evidence: list = field(default_factory=list)
    flags: str = "n/a"


@dataclass
class ReplayResult:
    n_samples: int = 0
    t_start: float = 0.0
    t_end: float = 0.0
    transitions: list = field(default_factory=list)
    seconds_in_state: dict = field(default_factory=dict)
    first_nontrusted_t: Optional[float] = None
    first_denied_t: Optional[float] = None
    px4_flags_available: bool = False
    first_px4_flag_t: Optional[float] = None
    px4_flagged_s: float = 0.0
    marsad_flagged_px4_silent_s: float = 0.0
    px4_flagged_marsad_trusted_s: float = 0.0
    reports: Optional[list] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("reports", None)
        return d


def replay_samples(samples: Iterable[NavSample], engine, flags: Optional[list] = None,
           keep_reports: bool = False) -> ReplayResult:
    """Run the engine over samples. flags: optional list of objects with t/jam_flag/spoof_flag/jamming_state/
    spoofing_state (Px4Flag), sorted by t."""
    flags = flags or []
    informative = any((f.jamming_state or 0) or (f.spoofing_state or 0) for f in flags)
    if not informative:          # all-zero/None states mean "receiver reports nothing": no comparison to make
        flags = []
    ft = [f.t for f in flags]
    res = ReplayResult(px4_flags_available=bool(flags), reports=[] if keep_reports else None)
    prev_state: Optional[TrustState] = None
    prev_t = None
    prev_nt = prev_fl = False
    first = True
    for s in samples:
        rep: TrustReport = engine.update(s)
        if first:
            res.t_start, first = s.t, False
        res.t_end = s.t
        res.n_samples += 1
        if keep_reports:
            res.reports.append(rep)
        fl = None
        if flags:
            i = bisect.bisect_right(ft, s.t) - 1
            fl = flags[i] if i >= 0 else None
        if prev_t is not None:
            dt = s.t - prev_t
            res.seconds_in_state[prev_state.value] = res.seconds_in_state.get(prev_state.value, 0.0) + dt
            if prev_fl:
                res.px4_flagged_s += dt
                if not prev_nt:
                    res.px4_flagged_marsad_trusted_s += dt
            elif prev_nt and flags:
                res.marsad_flagged_px4_silent_s += dt
        nt = rep.state != TrustState.TRUSTED
        flagged = bool(fl and (fl.jam_flag or fl.spoof_flag))
        if nt and res.first_nontrusted_t is None:
            res.first_nontrusted_t = s.t
        if rep.state == TrustState.DENIED and res.first_denied_t is None:
            res.first_denied_t = s.t
        if flagged and res.first_px4_flag_t is None:
            res.first_px4_flag_t = s.t
        if rep.state != prev_state:
            ev = sorted(rep.evidence, key=lambda e: e.weight, reverse=True)[:2]
            res.transitions.append(Transition(
                t=s.t, state=rep.state.value, trust=round(rep.trust, 3), dominant=rep.dominant,
                summary=rep.summary, evidence=[e.message for e in ev],
                flags=flag_label(fl.jamming_state, fl.spoofing_state) if fl else "n/a"))
            prev_state = rep.state
        prev_t, prev_nt, prev_fl = s.t, nt, flagged
    return res


def format_replay(res: ReplayResult, *, label: str = "", synthetic: bool = False, source: Optional[str] = None,
                  warnings: Iterable[str] = (), flag_source: str = "PX4 flags") -> str:
    out = []
    if label:
        out.append(label)
    if synthetic:
        out.append(f"*** {SYNTHETIC_BANNER}")
    if source is not None:
        out.append(f"reference velocity: {source or 'NONE'}")
    for w in warnings:
        out.append(f"WARNING: {w}")
    out.append(f"{res.n_samples} samples, {res.t_start:.1f}s .. {res.t_end:.1f}s")
    col = f"  [{flag_source}]" if res.px4_flags_available else ""
    for tr in res.transitions:
        line = f"t={tr.t:9.1f}s  {tr.state:9s} trust={tr.trust:.2f}  {tr.dominant}"
        if res.px4_flags_available:
            line += f"  | {flag_source}: {tr.flags}"
        out.append(line)
        for e in tr.evidence:
            out.append(f"{'':14s}- {e}")
    tot = sum(res.seconds_in_state.values()) or 1.0
    out.append("time in state: " + ", ".join(f"{k} {v:.0f}s ({100 * v / tot:.0f}%)"
                                              for k, v in sorted(res.seconds_in_state.items())))
    if not res.px4_flags_available:
        out.append(f"{flag_source}: none reported (field absent or unknown(0) throughout) -- no comparison column")
    if res.px4_flags_available:
        out.append(f"{flag_source}: first flag at "
                   f"{'never' if res.first_px4_flag_t is None else f'{res.first_px4_flag_t:.1f}s'}; "
                   f"Marsad first non-TRUSTED at "
                   f"{'never' if res.first_nontrusted_t is None else f'{res.first_nontrusted_t:.1f}s'}")
        out.append(f"  Marsad non-TRUSTED while {flag_source} silent: {res.marsad_flagged_px4_silent_s:.0f}s;"
                   f" {flag_source} flagged while Marsad TRUSTED: {res.px4_flagged_marsad_trusted_s:.0f}s")
    return "\n".join(out)
