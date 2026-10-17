# Contributing

* Python 3.10+. `pip install -e ".[dev]"` then `pytest` (about 9 minutes on a laptop).
* The core (`src/marsad/{engine,fusion,detectors,types,config,geo}.py`) must stay **standard-library only**; CI enforces it.
* Every detector change needs a scenario or test that would fail without it, and must be tuned on the `dev` split only;
  report `heldout` results once, after freezing.
* No RF, waveform, SDR or attack-generation code. See SECURITY.md.
* Label every result with exactly one of SIMULATED, REAL LOG, SIH + INJECTED or SITL FAULT, and report failures next to successes.
