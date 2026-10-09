"""Marsad adapters: real-world data in, verdicts out.

Heavy optional dependencies (pyulog, pymavlink, rclpy) are imported lazily, so `import marsad.adapters`
always works. Public names are resolved on first access.
"""
from __future__ import annotations
import importlib

_EXPORTS = {
    # ULog
    "read_ulog_samples": "ulog", "load_ulog": "ulog", "inspect_ulog": "ulog", "UlogInfo": "ulog",
    "UlogData": "ulog", "Px4Flag": "ulog",
    "write_ulog": "ulog_writer", "sat_snrs": "ulog_writer",
    # MAVLink
    "MavlinkSource": "mavlink", "MavlinkReporter": "mavlink", "MavlinkMapper": "mavlink",
    "read_tlog_samples": "mavlink", "sample_from_gps_raw_int": "mavlink", "cn0_from_gps_status": "mavlink",
    "gnss_integrity_flag": "mavlink", "ref_from_odometry": "mavlink", "named_values": "mavlink",
    "status_text": "mavlink", "has_gnss_integrity": "mavlink",
    # ROS 2
    "MarsadNode": "ros2", "RosBridge": "ros2", "process_navsat": "ros2", "process_odom": "ros2",
    "process_cn0": "ros2", "build_diagnostic": "ros2",
    # replay + shared
    "replay_samples": "replay", "format_replay": "replay", "ReplayResult": "replay",
    "ContaminatedReferenceWarning": "_common", "SYNTHETIC_BANNER": "_common",
}
__all__ = sorted(_EXPORTS)


def __getattr__(name):
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(f"module 'marsad.adapters' has no attribute {name!r}")
    return getattr(importlib.import_module(f".{mod}", __name__), name)


def __dir__():
    return sorted(list(globals()) + __all__)
