# Numerical environment

Pinned for every result file that depends on it. Updated when it changes; each entry carries its date (UTC+4).

| item | value (2026-11-03) |
|---|---|
| operating system | Linux 6.18 x86_64, Ubuntu 24.04 userland, virtual machine |
| CPU | 2 virtual cores, 7 GiB RAM, 30 GiB free disk at start |
| WSL | not used (native Linux) |
| Python | 3.13.16 |
| numpy | 2.5.3 |
| pyulog | 1.2.4 |
| pymavlink | 2.4.50 |
| mypy | 2.4.0 |
| compiler | gcc 13.3.0, cmake, ninja |
| PX4 | pinned when built; see docs/DATA.md |
| worker count | 1 (CPU count 2 minus 1) |

The simulator logs `sitl1.ulg` and `sitl2.ulg` were produced earlier on WSL2 Ubuntu with PX4 v1.18.0 beta, git
`fe24ec2280b62f50fe6b8e206a41a5d1687786fe` (see DATA.md). Results computed from them do not depend on the machine
that replays them.
