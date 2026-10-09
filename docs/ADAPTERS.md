# Adapters: getting real data in and verdicts out

The engine consumes `NavSample(t, gnss, ref)` in time order and returns a `TrustReport`. Adapters turn a
data source into that stream. Install the optional dependencies with `pip install marsad[adapters]`
(pyulog, pymavlink); `import marsad.adapters` works without them (imports are lazy).

| Adapter | Module | Status |
|---|---|---|
| PX4 ULog reader | `marsad.adapters.ulog` | Tested on **synthetic** logs and hand-built logs only. **Never run on a real PX4 log.** |
| Synthetic ULog writer | `marsad.adapters.ulog_writer` | Produces SYNTHETIC logs from the simulator. |
| MAVLink source + advisory reporter | `marsad.adapters.mavlink` | Tested offline on pymavlink-encoded bytes, a `.tlog` file and a localhost UDP loop. Never run against a real autopilot. |
| ROS 2 node | `marsad.adapters.ros2` | **Stub-tested only.** No ROS 2 runtime was available; `MarsadNode` has never run. |

> **SYNTHETIC DATA NOTICE.** Everything in this repository that exercises these adapters (`marsad make-log`,
> the test logs, the `.tlog` round trips) was produced by the Marsad measurement-level simulator. It is
> **not real flight data**, contains no real PX4 firmware output, and only demonstrates that the plumbing
> works. Results on it say nothing about performance on real receivers. **Replaying a real PX4 log is the
> first thing to do once one is available** (checklist below).

## CLI

```
marsad make-log --kind spoof_drift --seed 1 --split dev --out sim.ulg   # SYNTHETIC ULog from the simulator
marsad inspect sim.ulg                      # topics, field mapping, reference source, warnings
marsad replay  sim.ulg --preset uav_multirotor --json out.json
marsad replay  flight.tlog                  # MAVLink log (pymavlink)
marsad replay  flight.ulg --no-contaminated-ref   # never use an EKF-fused velocity as the reference
```

`replay` prints state transitions with their top evidence and, when the log carries the autopilot/receiver's
own jamming/spoofing state (`sensor_gps.jamming_state/spoofing_state`, or MAVLink `GNSS_INTEGRITY`), a
"PX4 flag" column plus a summary of how long each side flagged while the other was silent. If those fields
are absent or constant 0 (unknown) the column is omitted and that is said explicitly. Synthetic logs always
write 0 there: the simulator does not model a receiver's built-in detector and we do not invent one.

## ULog reader (`adapters/ulog.py`)

```python
from marsad.adapters import load_ulog, read_ulog_samples, inspect_ulog
d = load_ulog("flight.ulg", reference="auto", allow_contaminated=True)
d.samples      # list[NavSample], time ordered (t = timestamp/1e6 boot seconds)
d.info         # UlogInfo: topics, mapping, warnings, reference_source, reference_contaminated, ...
d.px4_flags    # list[Px4Flag(t, jamming_state, spoofing_state, jamming_indicator)] side-series (never fed to the engine)
for s in read_ulog_samples("flight.ulg"): ...   # generator; emits ContaminatedReferenceWarning if applicable
```

GNSS and reference rows closer than `merge_tol` (2 ms) share one `NavSample`; otherwise they are separate
samples (GNSS-only or reference-only), which the engine handles.

### Field aliases (first present wins; everything optional except lat/lon/timestamp)

| Logical field | Topic / aliases tried | Unit handling |
|---|---|---|
| GPS topic | `sensor_gps`, then `vehicle_gps_position` (pre-1.13 name); instance with most rows (warns on multi) | |
| time | `timestamp` (us) | /1e6 |
| lat, lon | `lat`/`latitude`, `lon`/`longitude` | integer type or `|x|>180` -> 1e-7 deg; else degrees |
| alt | `alt`, `altitude` | integer -> mm to m; float -> m |
| velocity | `vel_n_m_s`/`vel_n`/`vn`, `vel_e_m_s`/`vel_e`/`ve` | m/s |
| fix | `fix_type` | PX4 numbering: 3 = 3D (engine needs >= 3) |
| satellites | `satellites_used`, `satellites_visible`, `n_sats` | |
| hdop | `hdop` (missing -> unset, `eph` is metres and is *not* converted) | |
| AGC | `automatic_gain_control`, `agc`; fallback **proxy** `jamming_indicator` (warns) | normalised, see below |
| GNSS time | `time_utc_usec`, `time_utc` (0 = unknown -> `t_gnss=None`) | /1e6 |
| PX4 flags | `jamming_state`, `spoofing_state`, `jamming_indicator` | raw ints; flag when >= 2 |
| C/N0 | `satellite_info`: `count`, `snr[i]` | mean/std (population) of `snr>0` over the first `count` entries; attached to the latest row at or before each fix, max age 5 s |

**AGC normalisation heuristic** (`_common.normalise_agc`): scale chosen from the series maximum:
`<=1` unchanged, `<=100` percent, `<=255` 8-bit, `<=8191` 13-bit counter (u-blox style), else 16-bit. Only the
rise over the in-flight baseline matters to the engine (default signature 0.06), so a wrong absolute scale
changes sensitivity, not direction. Check the printed "agc normalisation" line in `marsad inspect`.

### Reference velocity (priority order)

| # | Topic | Fields used | Independent of GNSS? |
|---|---|---|---|
| 1 | `vehicle_visual_odometry` | `velocity[0..1]` (+ `velocity_frame`, `q` for FRD/body rotation, `velocity_variance[0]`); else `position[0..1]` differenced if pose frame is NED | yes |
| 2 | `vehicle_mocap_odometry` | same | yes |
| 3 | `vehicle_optical_flow_vel` | `vel_ne[0]`=N, `vel_ne[1]`=E | yes |
| 4 | `vehicle_optical_flow` | `pixel_flow[0..1]`, `integration_timespan_us`, `distance_m`, `delta_angle`, + `vehicle_attitude.q` for yaw | yes (axis/sign conventions unverified) |
| 5 | `vehicle_local_position` | `vx`=N, `vy`=E, `v_xy_valid` | **NO: EKF-fused** |
| 6 | `vehicle_odometry` | as #1 | **NO: EKF output** |

### The contaminated-reference warning

Items 5 and 6 are the autopilot's own state estimate, which fuses GNSS. A slow carry-off drags that
estimate along with it, so the engine's independent-reference check (the main defence against slow
carry-off spoofing) is **weakened or blind**. The adapter still falls back to them (replaying *something*
is better than nothing for jamming/jump/signal evidence), but loudly: `UlogInfo.reference_contaminated`,
`RefMotion.source` ends in `[EKF-FUSED,CONTAMINATED]`, a `ContaminatedReferenceWarning`, a `WARNING:` line in
`inspect`/`replay`. `allow_contaminated=False` / `--no-contaminated-ref` disables the fallback. Do **not**
quote carry-off detection results obtained this way. No reference at all is also warned about.

## Synthetic ULog writer (`adapters/ulog_writer.py`)

`write_ulog(path, run_or_samples, include_satellite_info=True)` writes a spec-conforming ULog v1 (header,
flag bits `B`, info `I`, formats `F`, subscriptions `A`, data `D`) containing `sensor_gps`,
`vehicle_visual_odometry` and `satellite_info`, plus info keys `marsad_synthetic` (a SYNTHETIC banner),
`marsad_scenario`, `marsad_seed`. Validated by reading it with pyulog and with `load_ulog`.

Round-trip fidelity (tested): positions within 1e-6 deg (actual <= 5e-8: the 1e-7 deg integer), velocities
and reference within 1e-5 m/s (float32), AGC within 1e-3 (13-bit), C/N0 mean within 0.1 dB and std within
0.2 dB (uint8 SNR quantisation, 20 tracked channels, error-diffused rounding), timestamps within 1 us. The
engine verdict on the round-tripped log has the same state sequence endpoints and visited states; transition
times can move by a few seconds on marginal evidence because of the SNR quantisation (on 7 tested
scenario/seed pairs the first non-TRUSTED time agrees within 5 s; most are identical).
Trailing struct padding is omitted (pyulog treats it as corruption; real PX4 logs omit it too).

## MAVLink (`adapters/mavlink.py`)

Dialect: `MAVLINK20=1`, dialect `all` (pymavlink 2.4.50 `common` does **not** contain `GNSS_INTEGRITY` (441);
`all` does and exposes `jamming_state`/`spoofing_state`; absence is handled and reported).

| Message | Used for | Notes |
|---|---|---|
| `GPS_RAW_INT` | lat/lon (degE7), alt (mm), `eph` (HDOP*100), `vel` (cm/s) + `cog` (cdeg) -> ve/vn, `satellites_visible`, `fix_type`, `time_usec` | 65535/255 sentinels -> None. Velocity from ground speed + course is unreliable when slow. `t_gnss` set only if `time_usec > 1e15` (epoch-like). |
| `GPS_STATUS` | `satellite_snr` (non-zero) -> C/N0 mean/std | needs the stream enabled; warns if never seen |
| `GNSS_INTEGRITY` | receiver `jamming_state`/`spoofing_state` -> side-series | enums: 0 unknown, 1 ok, 2 mitigated, 3 detected |
| `ODOMETRY` | reference. Independent iff `estimator_type` is VISION/VIO/MOCAP/LIDAR; GPS/GPS_INS/AUTOPILOT/UNKNOWN = contaminated. `child_frame_id` = velocity frame (LOCAL_NED, LOCAL_ENU, LOCAL_FRD/BODY_FRD rotated by yaw from `q`) | optional `ref_ids={(sysid, compid)}` to select the companion's stream |
| `OPTICAL_FLOW` | `flow_comp_m_x/y` (body m/s) rotated by `ATTITUDE.yaw` | quality >= 50 |
| `OPTICAL_FLOW_RAD` + range | `(iy-iygyro)/dt*d`, `-(ix-ixgyro)/dt*d` rotated by yaw; range from the message or `DISTANCE_SENSOR` | axis/sign **unverified** |
| `LOCAL_POSITION_NED` | `vx`,`vy` -> **contaminated** fallback | |

Policy: independent sources are always preferred; EKF-derived ones are used only if **no** independent source
has ever been seen in the stream (never mixed), with the same loud warning as ULog.

```python
from marsad.adapters import MavlinkSource, MavlinkReporter
src = MavlinkSource("udpin:0.0.0.0:14550")        # or tcp:..., serial path, or flight.tlog
rep = MavlinkReporter("udpout:127.0.0.1:14551")   # output link; add heartbeat=True if the GCS needs one
eng = TrustEngine(preset("uav_multirotor"))
for s in src.samples():
    r = eng.update(s)
    if s.gnss: rep.publish(r)
```

**Reporter is advisory only.** It can emit exactly `NAMED_VALUE_FLOAT` `MSD_TRUST` (0..1) and `MSD_STATE`
(0 trusted, 1 degraded, 2 denied) at <= 2 Hz (by report time), `STATUSTEXT` (<= 50 chars) only on state
change (DEGRADED = WARNING, DENIED = CRITICAL, return to TRUSTED = NOTICE), and optionally a `HEARTBEAT`
(`MAV_TYPE_ONBOARD_CONTROLLER`, `MAV_AUTOPILOT_INVALID`, no mode). A single choke point (`_send`) raises for any
other message type; a test tries `COMMAND_LONG`, `SET_MODE`, `PARAM_SET`, `SET_POSITION_TARGET_LOCAL_NED` and
`GPS_INPUT` and asserts none can be sent.

## ROS 2 (`adapters/ros2.py`) -- stub-tested only

Pure functions `process_navsat`, `process_odom`, `process_cn0`, `build_diagnostic` and the ROS-agnostic
`RosBridge` are unit-tested with `types.SimpleNamespace` stand-ins. `MarsadNode` (rclpy) is only syntax- and
import-checked: **never run against ROS 2**.

- `NavSatFix`: `status.status < 0` -> fix_type 1 else 3 (2D/3D inexpressible); `hdop` is a **proxy**
  `sqrt(cov_ee + cov_nn)/3 m`; no satellite count, no AGC, no velocity (optional separate `TwistStamped`).
- Reference: `nav_msgs/Odometry` (twist in child frame by default, rotated by pose yaw, ENU) or
  `geometry_msgs/TwistStamped`; set `ref_contaminated: true` if the odometry is a GPS-fused EKF
  (e.g. robot_localization with navsat_transform). Same weakness as above.
- C/N0: no standard ROS message exists; `process_cn0` accepts anything with `.cn0`/`.snr`/`.data` lists
  (configurable `cn0_topic`/`cn0_type`).
- Outputs: `~/trust` (Float32), `~/state` (String), `~/diagnostics` (DiagnosticStatus; OK/WARN/ERROR).

Launch snippet (`ros2.LAUNCH_SNIPPET`; the console entry point `marsad_node` is **not** registered in
`pyproject.toml` yet: use `python -m marsad.adapters.ros2` or add the entry point):

```python
from launch import LaunchDescription
from launch_ros.actions import Node
def generate_launch_description():
    return LaunchDescription([Node(package="marsad", executable="marsad_node", name="marsad_trust",
        parameters=[{"navsat_topic": "/gps/fix", "odom_topic": "/vio/odometry", "odom_type": "odometry",
                     "twist_frame": "child", "ref_contaminated": False, "preset": "ground_robot"}])])
```

## Known unknowns (verify against a real log before trusting any result)

PX4 / ULog:
1. `sensor_gps` field names and types: `lat`/`lon` (int32, 1e-7 deg), `alt` (int32 mm), `vel_n_m_s`,
   `vel_e_m_s`, `hdop`, `eph`, `fix_type`, `satellites_used`, `time_utc_usec`, `noise_per_ms`,
   `jamming_indicator`, `automatic_gain_control` (**may not exist** in a given PX4 version), `jamming_state`,
   `spoofing_state` (**enum values and whether they are populated at all** depend on receiver/driver).
2. Raw unit and range of `automatic_gain_control` / `jamming_indicator` per receiver (drives the AGC heuristic).
3. `satellite_info`: existence in the log (needs the logger topic enabled), `snr[]` in dB-Hz, `count` semantics,
   update rate (we hold the last row for up to 5 s).
4. `vehicle_visual_odometry` / `vehicle_odometry`: `velocity[]` vs legacy `vx/vy`, `velocity_frame` numbering
   (assumed 1 = NED, 2 = FRD, 3 = body FRD), `pose_frame`, `velocity_variance`, NaN conventions.
5. `vehicle_optical_flow_vel.vel_ne` order (N,E assumed); `vehicle_optical_flow` `pixel_flow` axis/sign and
   gyro compensation (`delta_angle`).
6. `vehicle_local_position` `vx` = north, `vy` = east, `v_xy_valid`.
7. Whether timestamps of different topics share a clock and are stamped at sample vs publish time (we use
   `timestamp`, not `timestamp_sample`).
8. Multi-instance GPS (we pick the instance with most rows).

MAVLink:
9. What `GPS_RAW_INT.time_usec` holds (boot vs epoch; we only trust values > 1e15).
10. Whether `GPS_STATUS` is streamed and how SNR is populated by the autopilot; `GNSS_INTEGRITY` availability.
11. `OPTICAL_FLOW_RAD` axis/sign convention and gyro compensation; `ODOMETRY.estimator_type` honesty (a companion
    that mislabels an EKF as VIO would defeat the independence rule).
12. `STATUSTEXT`/`NAMED_VALUE_FLOAT` visibility in the GCS in use; UDP routing so the FC/GCS receives our output.

ROS 2: everything about `MarsadNode` at runtime (QoS, executors, parameter handling, message package names).

## "First real log" checklist

1. Get a PX4 `.ulg` (SITL attack scenario or real flight). Keep it out of git unless you may share it.
2. `marsad inspect flight.ulg`. Read every line: which GPS topic/instance, units line, AGC normalisation line,
   whether C/N0, AGC and PX4 flags were found, which reference was chosen, every WARNING.
3. If a field was missed, add its real name to `ALIASES` in `adapters/ulog.py` (and to this document), add a
   regression test with a minimal hand-built log (see `build_ulog` in `tests/test_adapters.py`).
4. Confirm the reference is **independent** (VIO/flow/mocap). If `CONTAMINATED`, treat carry-off results as
   invalid; fix the logger config (log `vehicle_visual_odometry` / optical flow) and re-fly.
5. Sanity-check the reader against pyulog directly: first/last lat-lon, fix_type, satellites_used, speed from
   `vel_n/e` vs position derivative.
6. `marsad replay flight.ulg --json out.json` on a **nominal** flight first: expect TRUSTED throughout. Any
   DEGRADED/DENIED here is a false alarm; investigate (usually C/N0 baseline, hdop, units) before attack logs.
7. Replay logs with known interference and compare against the PX4 flag column; record disagreements both ways.
8. Do not tune detector thresholds on the same logs you report. Label results "real-log replay", with the
   log count, the PX4 version and this checklist's findings, separately from simulated numbers.
9. Update this "known unknowns" list: move confirmed items out, record the PX4 version they were confirmed on.
