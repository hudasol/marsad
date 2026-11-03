#!/usr/bin/env python3
"""Fly a PX4 SIH quadrotor with PX4's own EKF2 consuming shifted GNSS fixes (label: SITL EKF2).

Needs the PX4 build patched with scripts/px4_sensor_gps_sim_offset.patch and pymavlink. The script starts and stops
PX4 itself. One run = one ULog. The offset is a measurement edit inside the simulated receiver; no RF is involved.

usage:
  python scripts/sitl_ekf2_spoof.py --px4 /path/to/PX4-Autopilot --out DIR --case jump:200 --heading 90
  python scripts/sitl_ekf2_spoof.py ... --case drift:1.0 --velcons --heading 0
  python scripts/sitl_ekf2_spoof.py ... --case clean
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from pymavlink import mavutil

LEG_S, SPEED, ONSET_S, END_S = 30.0, 5.0, 60.0, 240.0


class Clock:
    """Simulation time from the vehicle's own boot time, so a faster-than-real-time run keeps its schedule."""

    def __init__(self, m):
        self.m, self.t = m, 0.0

    def now(self) -> float:
        while True:
            msg = self.m.recv_match(type=["LOCAL_POSITION_NED", "ATTITUDE"], blocking=False)
            if msg is None:
                return self.t
            self.t = msg.time_boot_ms / 1000.0


def set_param(m, sysid, comp, name, value, ptype):
    m.mav.param_set_send(sysid, comp, name.encode(), float(value), ptype)
    time.sleep(0.15)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--px4", required=True, help="PX4-Autopilot checkout with build/px4_sitl_default built")
    ap.add_argument("--out", required=True)
    ap.add_argument("--case", required=True, help="clean | jump:<m> | drift:<m/s>")
    ap.add_argument("--heading", type=float, default=0.0)
    ap.add_argument("--velcons", action="store_true", help="drift: also shift the receiver velocity")
    ap.add_argument("--speed", type=float, default=4.0, help="PX4_SIM_SPEED_FACTOR")
    ap.add_argument("--name", default=None)
    a = ap.parse_args(argv)

    kind, _, val = a.case.partition(":")
    name = a.name or f"{kind}{val}_h{int(a.heading)}{'_vel' if a.velcons else ''}"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    build = Path(a.px4) / "build" / "px4_sitl_default"
    run = out / f"run_{name}"
    if run.exists():
        shutil.rmtree(run)
    shutil.copytree(build / "rootfs", run, symlinks=True)
    env = dict(
        os.environ,
        PX4_SYS_AUTOSTART="10040",
        PX4_SIM_MODEL="sihsim_quadx",
        PX4_SIM_SPEED_FACTOR=str(a.speed),
        HEADLESS="1",
    )
    proc = subprocess.Popen(
        [str(build / "bin" / "px4"), str(build / "etc"), "-s", "etc/init.d-posix/rcS", "-d"],
        cwd=run,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=open(run / "px4.out", "w"),
        stderr=subprocess.STDOUT,
    )
    events = []
    try:
        m = mavutil.mavlink_connection("udpin:127.0.0.1:14540")
        m.wait_heartbeat(timeout=90)
        sysid, comp = m.target_system, m.target_component or 1
        clk = Clock(m)
        # SIH has no GPS fix for a few seconds; let EKF2 converge before arming
        t_wait = time.time()
        while clk.now() < 30.0 and time.time() - t_wait < 300:
            time.sleep(0.2)

        def vel(vn, ve, vd):
            m.mav.set_position_target_local_ned_send(
                0, sysid, comp, mavutil.mavlink.MAV_FRAME_LOCAL_NED, 3527, 0, 0, 0, vn, ve, vd, 0, 0, 0, 0, 0
            )

        for _ in range(60):  # offboard needs a setpoint stream before the mode switch and before arming
            vel(0, 0, 0)
            time.sleep(0.05)
        m.mav.command_long_send(sysid, comp, 176, 0, 1, 6, 0, 0, 0, 0, 0)  # offboard
        time.sleep(0.5)
        m.mav.command_long_send(sysid, comp, 400, 0, 1, 0, 0, 0, 0, 0, 0)  # arm
        t_up = clk.now()
        while clk.now() < t_up + 12.0:  # climb about 10 m
            vel(0, 0, -1.0)
            time.sleep(0.05)
        legs = [(SPEED, 0), (0, SPEED), (-SPEED, 0), (0, -SPEED)]
        t0 = clk.now()
        events.append({"t_sim": t0, "event": "square_start"})
        injected = False
        k = 0
        while clk.now() - t0 < END_S:
            vn, ve = legs[k % 4]
            leg_end = clk.now() + LEG_S
            while clk.now() < leg_end and clk.now() - t0 < END_S:
                vel(vn, ve, 0)
                if not injected and kind != "clean" and clk.now() - t0 >= ONSET_S:
                    set_param(m, sysid, comp, "SIM_SPF_MODE", 1 if kind == "jump" else 0, 6)
                    set_param(m, sysid, comp, "SIM_SPF_VAL", float(val), 9)
                    set_param(m, sysid, comp, "SIM_SPF_HDG", a.heading, 9)
                    set_param(m, sysid, comp, "SIM_SPF_VEL", 1 if a.velcons else 0, 6)
                    set_param(m, sysid, comp, "SIM_SPF_ON", 1, 6)
                    events.append({"t_sim": clk.now(), "t_after_square_start": clk.now() - t0, "event": "offset_on"})
                    injected = True
                time.sleep(0.05)
            k += 1
        m.mav.command_long_send(sysid, comp, 21, 0, 0, 0, 0, 0, 0, 0, 0)  # land
        t_l = clk.now()
        while clk.now() < t_l + 15.0:
            time.sleep(0.1)
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    logs = sorted(run.glob("log/**/*.ulg"))
    meta = {
        "name": name,
        "case": a.case,
        "heading": a.heading,
        "velcons": a.velcons,
        "speed_factor": a.speed,
        "events": events,
        "ulog": str(logs[-1].relative_to(out)) if logs else None,
    }
    json.dump(meta, open(out / f"{name}.json", "w"), indent=1)
    if logs:
        shutil.copy(logs[-1], out / f"{name}.ulg")
    shutil.rmtree(run, ignore_errors=True)
    print(json.dumps(meta))
    return 0 if logs else 1


if __name__ == "__main__":
    raise SystemExit(main())
