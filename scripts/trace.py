"""Debug helper: print per-detector evidence totals for a scenario run."""
import sys, collections
from marsad import TrustEngine, preset
from marsad.sim import generate
from marsad.detectors import Context

kind = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
split = sys.argv[3] if len(sys.argv) > 3 else "dev"
r = generate(kind, seed, split)
eng = TrustEngine(preset("uav_multirotor"))
tot = collections.defaultdict(float); first = {}
orig = eng.fusion.step
def step(dt, ev):
    for e in ev:
        for h, v in e.llr.items():
            tot[(e.detector, e.kind, h.value)] += v
            if v > 0.3: first.setdefault((e.detector, e.kind), eng.t_last)
    return orig(dt, ev)
eng.fusion.step = step
states = []
for s in r.samples:
    rep = eng.update(s); states.append((s.t, rep.state.value))
print("attack_start", r.attack_start, "params", {k: round(v, 2) if isinstance(v, float) else v for k, v in r.params.items()})
for k, v in sorted(tot.items(), key=lambda kv: -abs(kv[1]))[:14]:
    print(f"{k[0]:10s} {k[1]:24s} {k[2]:26s} {v:9.2f}  first>0.3 @ {first.get((k[0], k[1]))}")
prev = None
for t, st in states:
    if st != prev: print(f"  t={t:6.1f} -> {st}"); prev = st
