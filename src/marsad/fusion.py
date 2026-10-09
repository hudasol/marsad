"""Recursive multi-hypothesis fusion.

Each hypothesis h keeps a leaky log-likelihood-ratio accumulator against 'nominal':

    L_h <- L_h * exp(-dt / tau_h) + sum(evidence llr_h)       (clipped)

The posterior is a softmax over [0, L_h + prior_h]. The leak is a sticky Markov-prior
approximation: old evidence fades, but spoofing hypotheses keep a longer memory than
environmental ones. Quiet detectors contribute (near-)zero, so a missing sensor never
counts as evidence of attack.
"""
from __future__ import annotations
import math
from .config import EngineConfig
from .types import Evidence, Hypothesis as H

HYPS = [H.ENV, H.JAM, H.SPOOF_JUMP, H.SPOOF_DRIFT, H.REPLAY]


class Fusion:
    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.L = {h: 0.0 for h in HYPS}
        self.T = {h: 0.0 for h in HYPS}   # unclipped, slow-decaying evidence used only to LABEL the event type

    def reset(self) -> None:
        for h in HYPS:
            self.L[h] = 0.0
            self.T[h] = 0.0

    def dominant(self):
        h = max(HYPS, key=lambda k: self.T[k])
        return h if self.T[h] > 1.0 else None

    def step(self, dt: float, evidence: list[Evidence]) -> dict:
        lo, hi = self.cfg.llr_clip
        for h in HYPS:
            tau = self.cfg.tau[h.value]
            self.L[h] *= math.exp(-dt / tau) if dt > 0 else 1.0
            self.T[h] *= math.exp(-dt / 150.0) if dt > 0 else 1.0
        for e in evidence:
            for h, v in e.llr.items():
                if h in self.L:
                    self.L[h] += v
            prim = self._primary(e)
            if prim is not None:
                self.T[prim] = min(400.0, max(0.0, self.T[prim] + e.llr[prim]))
        for h in HYPS:
            self.L[h] = min(hi, max(lo, self.L[h]))
        return self.posterior()

    @staticmethod
    def _primary(e):
        """The single hypothesis an evidence item is *about* (largest |llr|; ties => none). Used only for labelling."""
        items = sorted(((abs(v), h) for h, v in e.llr.items() if h in HYPS), key=lambda x: -x[0])
        if not items or items[0][0] < 1e-9:
            return None
        if len(items) > 1 and items[0][0] - items[1][0] < 1e-9:
            return None
        return items[0][1]

    def posterior(self) -> dict:
        logits = {H.NOMINAL: 0.0}
        for h in HYPS:
            logits[h] = self.L[h] + self.cfg.prior_logit[h.value]
        m = max(logits.values())
        ex = {h: math.exp(v - m) for h, v in logits.items()}
        z = sum(ex.values())
        return {h.value: v / z for h, v in ex.items()}

    def attack_onset_evidence(self) -> float:
        """Largest accumulated evidence for any non-environmental hypothesis."""
        return max(self.L[H.JAM], self.L[H.SPOOF_JUMP], self.L[H.SPOOF_DRIFT], self.L[H.REPLAY])
