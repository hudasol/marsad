# Contributing

## Setup

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check src tests scripts && ruff format --check src tests scripts
python scripts/check_links.py
pytest                                              # several minutes: the benchmark and log tests are not small
```

Python 3.10 or newer. CI runs the suite on 3.10, 3.12 and 3.13, plus lint, a wheel build and install, the container,
a ROS 2 job and a check that the core imports with nothing installed.

## Rules

* The core (`src/marsad/{engine,fusion,detectors,types,config,geo}.py`) stays standard library only; CI enforces it.
* A detector or engine change needs a test that fails without it. Tune on the `dev` split only, write the predictions
  down in `docs/research/` before running the held out split, and record the outcome there whether or not the
  predictions hold (see `docs/research/README.md`).
* Every result carries exactly one label: SIMULATED, REAL LOG, SIH + INJECTED or SITL FAULT. Report failures next to
  successes.
* No RF, waveform, SDR or attack generation code. See SECURITY.md.
* Update CHANGELOG.md under Unreleased.
* Commit one logical change at a time with a message that says what changed and why.
