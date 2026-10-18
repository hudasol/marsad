# Data

The flight logs used in this repository are not stored in git (23 to 190 MB each, and `.ulg` is in `.gitignore`).
This page identifies each file by its SHA256 checksum, says how it was obtained, and explains how to download and
verify the two simulator logs.

## Files

| file | label | size (bytes) | SHA256 |
|---|---|---|---|
| `sitl1.ulg` | SIH (base log for SIH + INJECTED) | 23,109,655 | `20d61fff69f6fd2e54d75631214d3465244b39900219e24f1df31e1b9097c37e` |
| `sitl2.ulg` | SIH (base log for SIH + INJECTED) | 93,068,353 | `22128ec8a70461c6b9e28e2020a8e4a2031700860abd40d6e4b529db4c5ea645` |
| `flight1.ulg` | REAL LOG | 189,862,028 | `19c756071c2f1fc4676241cd9737b195ade97b74c16f5a00f94218b5eb16f1e9` |
| `flight2.ulg` | REAL LOG | 37,809,237 | `3cca05594bd7448c8e146d7bf563dfe3e1a2381ef536fcff63a52fb6d3b20c6d` |

Checksums were computed with `sha256sum` on 2026-10-18. Version and hardware fields below are read from each log's
own ULog header (`ver_sw_release`, `ver_sw`, `ver_hw`).

## How each file was obtained

**`sitl1.ulg`.** PX4 software in the loop with the SIH simulator (`make px4_sitl sihsim_quadx`) on WSL2 Ubuntu,
PX4 v1.18.0 beta build (header release word `0x01120080`, git `fe24ec2280b62f50fe6b8e206a41a5d1687786fe`), hardware
string `PX4_SITL`. Flown on 2026-10-10 with `python3 scripts/sitl_flight.py` as it was then (no flags; the
`--no-faults` option did not exist), after `param set SYS_FAILURE_EN 1` and `commander takeoff`. The script injects
timed GPS failures through PX4's failure injection; the log covers 0.6 s to 100.4 s of vehicle uptime and contains
the first of them, which dropped the fix type from 3 to 2 at about 78 s (SITL FAULT). Marsad's SIH + INJECTED runs
cut this log at 77 s, before that fault. The vehicle, receiver and reference are simulated; the PX4 software, its
timing and its GNSS message stream are real outputs. No personal data.

**`sitl2.ulg`.** Same PX4 build and simulator. Flown on 2026-10-16 with
`python3 scripts/sitl_flight.py --no-faults` (a 300 s square at 5 m/s and 10 m altitude, no failure injection),
started headless with `HEADLESS=1 make px4_sitl sihsim_quadx`, `commander takeoff` before the script and
`commander land` after it. The PX4 log was `build/px4_sitl_default/rootfs/fs/log/2026-10-16/01_21_34.ulg`. It covers
2.0 s to 402.9 s of uptime. Acceptance check before use: fix type 3 on all 3,212 fixes, GNSS error against simulator
truth at most 0.30 m, Marsad TRUSTED on all 51,615 samples (`docs/results/sitl2_timeline.txt`). No personal data.

**`flight1.ulg` and `flight2.ulg`.** Two public logs from the PX4 Flight Review database (review.px4.io), published
there under CC BY, as described in VALIDATION.md ("Real-log results"):

| file | PX4 version (header) | hardware (header) | GNSS duration replayed |
|---|---|---|---|
| `flight1.ulg` | v1.15.3 (`0x010f03ff`) | `PDW_STACK_FC_V2` multicopter | 911 s |
| `flight2.ulg` | v1.17.0 (`0x011100ff`), git `d6f12ad1c4f70ad3230afd7d86e971421e02fef4` | `CUBEPILOT_CUBEORANGEPLUS` multicopter | 334 s |

The Flight Review log identifiers were not recorded when the files were downloaded, so they cannot be given here; the
checksums above identify the exact files. Neither log contains an attack. They are not redistributed in this
repository or its releases; anyone reproducing the REAL LOG results needs their own copy of a public log, and the
numbers will differ for a different log.

## Download and verify the simulator logs

`sitl1.ulg`, `sitl2.ulg` and a `SHA256SUMS.txt` file are attached to the
[v1.3.0 GitHub Release](https://github.com/hudasol/marsad/releases/tag/v1.3.0). From the repository root:

```bash
gh release download v1.3.0 --repo hudasol/marsad --pattern "*.ulg" --pattern SHA256SUMS.txt
```

or without the GitHub CLI:

```bash
curl -LO https://github.com/hudasol/marsad/releases/download/v1.3.0/sitl1.ulg
curl -LO https://github.com/hudasol/marsad/releases/download/v1.3.0/sitl2.ulg
curl -LO https://github.com/hudasol/marsad/releases/download/v1.3.0/SHA256SUMS.txt
```

Then verify (Linux, WSL or Git Bash):

```bash
sha256sum -c SHA256SUMS.txt
```

On Windows PowerShell, `Get-FileHash sitl2.ulg -Algorithm SHA256` prints the checksum to compare with the table
above. With the files in place, every SIH + INJECTED command in README.md ("For reviewers") runs as written.
