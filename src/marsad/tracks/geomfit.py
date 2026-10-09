"""Small stdlib-only geometric helpers: robust circle fit and angle utilities."""
from __future__ import annotations
import math
from typing import Optional, Sequence


def wrap_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def wrap_deg(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def _kasa(xs: Sequence[float], ys: Sequence[float]):
    """Algebraic (Kasa) least-squares circle fit. Returns (cx, cy, r) or None if degenerate."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sxy = syy = sxz = syz = zbar = 0.0
    for x, y in zip(xs, ys):
        u, v = x - mx, y - my
        z = u * u + v * v
        sxx += u * u
        sxy += u * v
        syy += v * v
        sxz += u * z
        syz += v * z
        zbar += z
    zbar /= n
    det = sxx * syy - sxy * sxy
    if det <= 1e-9 * (sxx + syy) ** 2 or det <= 0.0:
        return None
    a = (sxz * syy - syz * sxy) / det / 2.0     # solves [sxx sxy; sxy syy][2a; 2b] = [sxz; syz]
    b = (syz * sxx - sxz * sxy) / det / 2.0
    r2 = zbar + a * a + b * b
    if r2 <= 0:
        return None
    return mx + a, my + b, math.sqrt(r2)


def robust_circle_fit(xs: Sequence[float], ys: Sequence[float], rounds: int = 2):
    """Kasa fit followed by MAD-based outlier trimming and refits.

    Returns dict(cx, cy, r, rms, kept) or None.
    """
    idx = list(range(len(xs)))
    fit = _kasa([xs[i] for i in idx], [ys[i] for i in idx])
    if fit is None:
        return None
    for _ in range(rounds):
        cx, cy, r = fit
        res = [math.hypot(xs[i] - cx, ys[i] - cy) - r for i in idx]
        med = sorted(abs(x) for x in res)[len(res) // 2]
        scale = max(1.4826 * med, 0.02 * r, 1e-6)
        keep = [i for i, e in zip(idx, res) if abs(e) <= 2.5 * scale]
        if len(keep) == len(idx) or len(keep) < max(6, int(0.7 * len(xs))):
            break
        nf = _kasa([xs[i] for i in keep], [ys[i] for i in keep])
        if nf is None:
            break
        idx, fit = keep, nf
    cx, cy, r = fit
    res = [math.hypot(xs[i] - cx, ys[i] - cy) - r for i in idx]
    rms = math.sqrt(sum(e * e for e in res) / len(res))
    return {"cx": cx, "cy": cy, "r": r, "rms": rms, "kept": len(idx)}
