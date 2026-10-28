"""Run the baselines over a real PX4 ULog and report how long each stays TRUSTED (REAL LOG, false alarm side).

    python scripts/replay_baselines.py flight1.ulg [flight2.ulg ...]

The reference velocity is whatever the ULog adapter selects (see `marsad inspect`). In ordinary flight logs this is
the EKF fused velocity, which follows GNSS, so the consistency tests are close to blind there; the result is a
statement about false alarms only, like the Marsad replay in docs/VALIDATION.md.
"""

import sys
import warnings

from marsad.adapters.ulog import load_ulog
from marsad.bench.baselines import make_baselines
from marsad.types import TrustState


def main(paths):
    for path in paths:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            d = load_ulog(path, allow_contaminated=True, warn=False)
        bs = make_baselines()
        bad = dict.fromkeys(bs, 0)
        n = 0
        for s in d.samples:
            n += 1
            for k, b in bs.items():
                st, _ = b.update(s)
                bad[k] += st != TrustState.TRUSTED
        print(f"{path}: {n} samples, reference {d.info.reference_source or 'none'}")
        for k, v in bad.items():
            print(f"  {k:14s} not TRUSTED in {v} samples ({100 * v / max(n, 1):.2f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1:])
