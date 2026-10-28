"""Run the trust engine on a simulated carry off spoofing scenario and print every state change.

pip install -e ".[sim]"
python examples/quickstart.py
"""

from marsad import TrustEngine, preset
from marsad.sim import generate

run = generate("spoof_drift_stealth", seed=4, split="dev")  # SIMULATED, measurement level only
engine = TrustEngine(preset("uav_multirotor"))

previous = None
for sample in run.samples:
    report = engine.update(sample)
    if report.state != previous:
        print(f"t={sample.t:7.1f} s  {report.state.value:9s} trust={report.trust:.2f}  {report.summary}")
        previous = report.state

print(f"\nattack started at t={run.attack_start:.1f} s")
