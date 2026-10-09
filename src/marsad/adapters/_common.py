"""Shared helpers for the adapters (no heavy imports)."""
from __future__ import annotations
import math
from typing import Optional, Sequence

SYNTHETIC_BANNER = "SYNTHETIC / SIMULATED data produced by the Marsad simulator -- not real flight data."
CONTAMINATED_WARNING = (
    "REFERENCE VELOCITY IS CONTAMINATED: it comes from an EKF/autopilot estimate that also fuses GNSS. "
    "A slow GNSS carry-off drags this estimate along, so the independent-reference check (the main defence "
    "against slow carry-off spoofing) is WEAKENED or BLIND. Use VIO / optical flow + range / wheel or DVL "
    "odometry as the reference for any real evaluation.")


class ContaminatedReferenceWarning(UserWarning):
    """The only velocity reference available is derived from a GNSS-fused estimate."""


def mean_std(values: Sequence[float]) -> tuple[Optional[float], Optional[float]]:
    v = [float(x) for x in values if x is not None and math.isfinite(x)]
    if not v:
        return None, None
    m = sum(v) / len(v)
    var = sum((x - m) ** 2 for x in v) / len(v)
    return m, math.sqrt(var)


def normalise_agc(values) -> tuple[list, str]:
    """Map a raw receiver AGC series to 0..1 (higher = more RF power at the front end).

    HEURISTIC, scale chosen from the series maximum because the raw unit differs between receivers:
      max <= 1.0001  -> already normalised, unchanged
      max <= 100     -> percent, /100
      max <= 255     -> 8-bit counter, /255
      max <= 8191    -> 13-bit counter (u-blox style agcCnt), /8191
      else           -> 16-bit counter, /65535
    Only the *rise relative to the in-flight baseline* matters to the engine, so a wrong absolute scale
    changes sensitivity (a 0.06 rise is the default jamming signature) but not the sign of the effect.
    """
    import numpy as np
    a = np.asarray(values, dtype=float)
    fin = a[np.isfinite(a)]
    if fin.size == 0:
        return [None] * len(a), "no finite AGC values"
    mx = float(fin.max())
    if mx <= 1.0001:
        scale, why = 1.0, "already 0..1"
    elif mx <= 100:
        scale, why = 100.0, "percent (max<=100)"
    elif mx <= 255:
        scale, why = 255.0, "8-bit (max<=255)"
    elif mx <= 8191:
        scale, why = 8191.0, "13-bit counter (max<=8191)"
    else:
        scale, why = 65535.0, "16-bit counter"
    out = [float(x) / scale if math.isfinite(x) else None for x in a]
    return out, f"raw max {mx:g} treated as {why}; divided by {scale:g}"
