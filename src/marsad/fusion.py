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

    def reset(self) -> None:
        for h in HYPS:
            self.L[h] = 0.0

    def step(self, dt: float, evidence: list[Evidence]) -> dict:
        lo, hi = self.cfg.llr_clip
        for h in HYPS:
            tau = self.cfg.tau[h.value]
            self.L[h] *= math.exp(-dt / tau) if dt > 0 else 1.0
        for e in evidence:
            for h, v in e.llr.items():
                if h in self.L:
                    self.L[h] += v
        for h in HYPS:
            self.L[h] = min(hi, max(lo, self.L[h]))
        return self.posterior()

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
