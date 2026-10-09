# Milestones

Annotated git tags exist in the local clone but the session's git proxy refused tag pushes (HTTP 403), so the tagged commits are recorded here. To publish the tags from your machine: `git fetch origin && git tag -a <tag> <sha> -m <tag>` for each row, then `git push origin --tags`.

| tag | commit | content |
|---|---|---|
| `v0.0.1-plan` | `d6b14e1` | docs: add build plan, README and Apache-2.0 license |
| `v0.1.0` | `92de2c9` | v0.1.0: core trust engine, detectors, fusion, state machine, simulator, benchmark harness |
| `v0.3.0` | `c05766b` | v0.3.0: track-trust module, fleet interference map and multi-source track simulator |
| `v0.4.0` | `0e4ff4a` | v0.4.0: PX4 ULog, MAVLink and ROS 2 adapters, synthetic ULog writer, replay/inspect CLI |
| `v0.6.0` | `6156e60` | v0.5.0/v0.6.0: REST+SSE service, MCP server, operator dashboard; serve/mcp CLI |
| `v1.0.0` | `4638548` | docs+eval: held-out evaluation, ablations, detectability sweep, figures, technical report, |

The Dockerfile could not be built in the authoring environment (no Docker daemon), so it is untested. CI workflow was pushed but its first run was not observed.
