#!/usr/bin/env python3
"""Fly a PX4 SITL (SIH) quadrotor in a square and inject GPS faults on a timer.

Run inside WSL/Linux while `make px4_sitl sihsim_quadx` is running and the vehicle is hovering
(`param set SYS_FAILURE_EN 1`, then `commander takeoff` in the pxh> shell). Needs pymavlink.
Writes sitl_events.txt with the script-relative time of every injection, so a replayed log can be
compared against the ground truth. Faults are injected receiver faults, NOT RF spoofing.
"""
import sys, time
from pymavlink import mavutil

LEG_S, SPEED = 30, 5.0
# (start s, fault type, duration s) -- type numbers follow the MAVLink FAILURE_TYPE enum
FAULTS = [(40, 4, 20, "wrong"), (100, 2, 20, "stuck"), (160, 1, 20, "off"), (220, 3, 20, "garbage")]
GPS_UNIT = 4  # as printed by PX4: "unit: gps (4)"
END_S = 300

m = mavutil.mavlink_connection("udpin:127.0.0.1:14540")
print("waiting for heartbeat on udp 14540 ...")
m.wait_heartbeat()
sysid, comp = m.target_system, m.target_component or 1
print("connected, system", sysid)


def vel(vn, ve, vd):
    m.mav.set_position_target_local_ned_send(
        0, sysid, comp, mavutil.mavlink.MAV_FRAME_LOCAL_NED, 3527, 0, 0, 0, vn, ve, vd, 0, 0, 0, 0, 0)


def cmd(c, *p):
    p = list(p) + [0] * (7 - len(p))
    m.mav.command_long_send(sysid, comp, c, 0, *p)


def inject(ftype, name):
    cmd(420, GPS_UNIT, ftype, 0)
    return name


def stream(vn, ve, vd, secs, tick=None):
    end = time.time() + secs
    while time.time() < end:
        vel(vn, ve, vd)
        if tick:
            tick()
        time.sleep(0.05)


stream(0, 0, 0, 3)                         # offboard needs a setpoint stream first
cmd(176, 1, 6, 0)                          # DO_SET_MODE: custom mode enabled, PX4 main mode 6 = offboard
stream(0, 0, -1.0, 8)                      # climb ~8 m
legs = [(SPEED, 0), (0, SPEED), (-SPEED, 0), (0, -SPEED)]
t0 = time.time()
events = open("sitl_events.txt", "w")
events.write(f"# t0 wall clock {t0:.3f}; times below are seconds after t0\n")
state = {"i": 0, "active": None}


def tick():
    t = time.time() - t0
    for i, (start, ftype, dur, name) in enumerate(FAULTS):
        if state["active"] is None and start <= t < start + dur and state["i"] == i:
            inject(ftype, name); state["active"] = i
            events.write(f"{t:.1f} inject gps {name}\n"); events.flush(); print(f"{t:6.1f}s inject {name}")
        elif state["active"] == i and t >= start + dur:
            inject(0, "ok"); state["active"] = None; state["i"] = i + 1
            events.write(f"{t:.1f} clear gps\n"); events.flush(); print(f"{t:6.1f}s clear")


k = 0
while time.time() - t0 < END_S:
    vn, ve = legs[k % 4]
    stream(vn, ve, 0, LEG_S, tick)
    k += 1
inject(0, "ok")
stream(0, 0, 0, 2)
events.write(f"{time.time()-t0:.1f} end\n"); events.close()
print("done. In pxh> run: commander land")
