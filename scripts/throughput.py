"""Engine cost per sample, three repeats, on the nominal 600 s simulated run used by scripts/run_eval.py.

usage: python scripts/throughput.py   (PYTHONPATH=<other checkout>/src to time another engine version on the same machine)
Prints which weighting the engine uses so two versions can be told apart. Label: SIMULATED input.
"""

import time

from marsad import TrustEngine, preset
from marsad.detectors import Context
from marsad.sim import generate

run = generate("nominal", 1, "dev", duration=600)
out = []
for _ in range(3):
    eng = TrustEngine(preset("uav_multirotor"))
    t1 = time.perf_counter()
    for s in run.samples:
        eng.update(s)
    out.append(1e6 * (time.perf_counter() - t1) / len(run.samples))
print("fixed" if hasattr(Context(), "gnss_dt") else "v1.2.0", [round(x, 1) for x in out])
