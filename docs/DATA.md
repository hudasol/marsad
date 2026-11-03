# Data

The flight logs used in this repository are not stored in git (about 23 to 190 MB each, and `.ulg` is in `.gitignore`).
This page identifies each file by its SHA256 checksum, says how it was obtained, and explains how to download and
verify the two simulator logs.

## Files

| file | label | size (bytes) | SHA256 |
|---|---|---|---|
| `sitl1.ulg` | SIH + INJECTED (base log, zero offset) | 23,109,655 | `20d61fff69f6fd2e54d75631214d3465244b39900219e24f1df31e1b9097c37e` |
| `sitl2.ulg` | SIH + INJECTED (base log, zero offset) | 93,068,353 | `22128ec8a70461c6b9e28e2020a8e4a2031700860abd40d6e4b529db4c5ea645` |
| `flight1.ulg` | REAL LOG | 189,862,028 | `19c756071c2f1fc4676241cd9737b195ade97b74c16f5a00f94218b5eb16f1e9` |
| `flight2.ulg` | REAL LOG | 37,809,237 | `3cca05594bd7448c8e146d7bf563dfe3e1a2381ef536fcff63a52fb6d3b20c6d` |

Checksums were computed with `sha256sum` on 2026-10-18. Version and hardware fields below are read from each log's
own ULog header (`ver_sw_release`, `ver_sw`, `ver_hw`).

## The real flight corpus (v1.5.0, REAL LOG)

139 public PX4 logs from the Flight Review database (review.px4.io), published there under CC BY. They are listed in
[results/real_corpus/manifest.csv](results/real_corpus/manifest.csv) with the log identifier, the download address, the
SHA256 of the file, PX4 release, hardware name, vehicle type, seconds of usable GNSS and the independent reference types
found in the log. The manifest holds no coordinates. 33 candidates were rejected before analysis
([rejected.csv](results/real_corpus/rejected.csv); 32 had no usable GNSS and 1 was above the size limit).

| item | value |
|---|---|
| logs analysed | 139 (101 scoring, 30 design subset, 9 with error labels reported separately; one flight is in both of the last two groups) |
| hardware names | 113 distinct names in the manifest |
| vehicle types | 97 quadrotor, 18 fixed wing, 7 VTOL, 7 octorotor, 6 hexarotor, and others |
| total download | about 6.0 GB |
| selection | seeded draw, preregistered in [research/PREREGISTRATION_REAL_CORPUS.md](research/PREREGISTRATION_REAL_CORPUS.md) |

Attribution. The logs are the work of their uploaders and are made available by the PX4 Flight Review service under
the Creative Commons Attribution licence. Marsad does not redistribute them: no `.ulg` file from Flight Review is in
this repository or in any release. To reproduce, download each file from the address in the manifest, check the SHA256
with `sha256sum`, and run `python scripts/real_corpus.py analyze --manifest ... --logs DIR`. A log that was later removed or changed upstream will fail the check
and be reported, not replaced silently.

## Own simulator logs added in v1.5.0

The PX4 software in the loop logs flown for the EKF2 in the loop study (SITL EKF2) and for the imperfect reference study
(SIH + INJECTED) are made by `scripts/sitl_ekf2_spoof.py` and `scripts/sih_realistic_ref.py` on the PX4 build described in
[results/ENVIRONMENT.md](results/ENVIRONMENT.md). The 48 SITL EKF2 logs are 3.3 GB in total and are not attached to the
release; the scored summary is in [results/sitl_ekf2/](results/sitl_ekf2/) and re-running the batch script regenerates
them. The patch that adds the offset parameters to the PX4 GPS simulator is `scripts/px4_sensor_gps_sim_offset.patch`.

Four of these runs are attached to the v1.5.0 GitHub Release as the clean base logs of the SIH + INJECTED studies of
v1.5.0 (no attack, no failure injection, flown with `scripts/sitl_ekf2_spoof.py --case clean`). Their checksums, also in
`SHA256SUMS.txt` on the release:

| file | size (bytes) | SHA256 |
|---|---|---|
| `clean_h0.ulg` | 70,967,591 | `95324f3ec075da6261383fa7218cc9e2b220034462d323227f52e2adf7231d91` |
| `clean_h90.ulg` | 72,769,927 | `9d97e5d019b791838f2cb0cb1a29343d89dcb1843a5eac253a3cb7aa07ede9a3` |
| `clean_h180.ulg` | 72,351,070 | `a0d0dca53bead486170fb621f38c4705b0a9fa8c914691020a5fc6bdc02fa618` |
| `clean_h270.ulg` | 73,051,127 | `7d1e9eed426ddaeffcc885e8d7d1f07e9595ad61fdfdc62e5f693f31e7cc7971` |

`sitl1.ulg` and `sitl2.ulg` stay attached to the v1.3.0 release as before.

## How each file was obtained

**`sitl1.ulg`.** PX4 software in the loop with the SIH simulator (`make px4_sitl sihsim_quadx`) on WSL2 Ubuntu,
PX4 v1.18.0 beta build (header release word `0x01120080`, git `fe24ec2280b62f50fe6b8e206a41a5d1687786fe`), hardware
string `PX4_SITL`. Flown on 2026-10-10 with `python3 scripts/sitl_flight.py` as it was then (no flags; the
`--no-faults` option did not exist), after `param set SYS_FAILURE_EN 1` and `commander takeoff`. The script injects
timed GPS failures through PX4's failure injection; the log's first and last timestamps are 0.6 s and 100.4 s of vehicle uptime (read with pyulog) and contains
the first of them, which dropped the fix type from 3 to 2 at about 78 s (SITL FAULT). Marsad's SIH + INJECTED runs
cut this log at 77 s, before that fault. The vehicle, receiver and reference are simulated; the PX4 software, its
timing and its GNSS message stream are real outputs. No personal data.

**`sitl2.ulg`.** Same PX4 build and simulator. Flown on 2026-10-16 with
`python3 scripts/sitl_flight.py --no-faults` (a 300 s square at 5 m/s and about 10 m altitude in simulator truth, no failure injection),
started headless with `HEADLESS=1 make px4_sitl sihsim_quadx`, `commander takeoff` before the script and
`commander land` after it. The PX4 log was `build/px4_sitl_default/rootfs/fs/log/2026-10-16/01_21_34.ulg`. Its first and last
timestamps are 2.0 s and 402.9 s of uptime (read with pyulog; the last GNSS fix is stamped 403.4 s). Acceptance check before use: fix type 3 on all 3,212 fixes, GNSS error against simulator
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
