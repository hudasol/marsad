"""ROS 2 adapter.

STUB-TESTED ONLY: no ROS 2 runtime is available in the development environment, so MarsadNode itself has
never been run. The pure functions (process_navsat, process_odom, process_cn0, build_diagnostic) and the
RosBridge pipeline are unit-tested against duck-typed stand-ins (types.SimpleNamespace). rclpy and the
ROS message packages are imported lazily/guardedly: this module imports fine without ROS.

Conventions (REP-103/105): ROS world frames are ENU (x east, y north). NavSatFix has no velocity, so GNSS
velocity is optional via a separate TwistStamped/TwistWithCovarianceStamped topic.
"""
from __future__ import annotations
import math
from types import SimpleNamespace
from typing import Callable, Optional

from ..config import preset
from ..engine import TrustEngine
from ..types import GnssFix, RefMotion, TrustReport, TrustState
from ._common import CONTAMINATED_WARNING, mean_std

try:                                        # pragma: no cover - exercised only with ROS installed
    import rclpy
    from rclpy.node import Node
    HAVE_ROS2 = True
except Exception:                           # ImportError or a broken ROS environment
    rclpy = None
    Node = object
    HAVE_ROS2 = False

DIAG_LEVEL = {TrustState.TRUSTED: 0, TrustState.DEGRADED: 1, TrustState.DENIED: 2}   # OK / WARN / ERROR


def _stamp(msg, default: Optional[float] = None) -> Optional[float]:
    h = getattr(msg, "header", None)
    st = getattr(h, "stamp", None)
    if st is not None:
        sec = getattr(st, "sec", getattr(st, "secs", 0))
        ns = getattr(st, "nanosec", getattr(st, "nsecs", 0))
        t = float(sec) + float(ns) * 1e-9
        if t > 0:
            return t
    return default


def _yaw_from_quat(q) -> Optional[float]:
    try:
        x, y, z, w = float(q.x), float(q.y), float(q.z), float(q.w)
    except (AttributeError, TypeError, ValueError):
        return None
    if x * x + y * y + z * z + w * w < 0.5:
        return None
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def process_navsat(msg, t: Optional[float] = None, *, vel: Optional[tuple] = None,
                   cn0: Optional[tuple] = None, uere_m: float = 3.0) -> Optional[GnssFix]:
    """sensor_msgs/NavSatFix (duck-typed) -> GnssFix, or None for NaN lat/lon.

    status.status: -1 NO_FIX -> fix_type 1; >=0 (FIX/SBAS/GBAS) -> 3 (NavSatFix cannot express 2D vs 3D).
    hdop is a PROXY: sqrt(var_e + var_n)/uere_m from position_covariance diagonal (unless covariance type is
    UNKNOWN=0). n_sats and AGC are not in NavSatFix (None). vel=(ve, vn) and cn0=(mean, std) are optional
    side inputs kept by the bridge from other topics.
    """
    lat, lon = float(msg.latitude), float(msg.longitude)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    status = getattr(getattr(msg, "status", None), "status", 0)
    cov = getattr(msg, "position_covariance", None)
    ctype = getattr(msg, "position_covariance_type", 0)
    hdop = None
    if cov is not None and len(cov) >= 5 and ctype != 0:
        v = float(cov[0]) + float(cov[4])
        if math.isfinite(v) and v >= 0:
            hdop = math.sqrt(v) / uere_m
    alt = float(getattr(msg, "altitude", 0.0))
    tt = t if t is not None else _stamp(msg, 0.0)
    return GnssFix(t=float(tt), lat=lat, lon=lon, alt=alt if math.isfinite(alt) else 0.0,
                   ve=vel[0] if vel else None, vn=vel[1] if vel else None,
                   cn0_mean=cn0[0] if cn0 else None, cn0_std=cn0[1] if cn0 else None,
                   n_sats=None, agc=None, hdop=hdop, fix_type=1 if status < 0 else 3, t_gnss=None)


def process_odom(msg, t: Optional[float] = None, *, twist_frame: str = "child",
                 source: str = "ros2:odom") -> Optional[RefMotion]:
    """nav_msgs/Odometry, geometry_msgs/TwistStamped or TwistWithCovarianceStamped -> RefMotion (ENU).

    twist_frame='child' (REP-105 default for Odometry): linear velocity is in the child (body) frame and
    is rotated by the pose orientation yaw; if no orientation is available it is used as-is.
    twist_frame='parent': linear velocity already in the world/odom frame (x east, y north).
    TwistStamped/TwistWithCovariance carry no pose: they are always used as-is (assumed ENU world frame).
    The caller is responsible for the independence of the source (an EKF fused with GPS is CONTAMINATED).
    """
    sigma = None
    tw = getattr(msg, "twist", None)
    if tw is None:
        return None
    if hasattr(tw, "twist"):                        # Odometry / TwistWithCovarianceStamped
        lin = tw.twist.linear
        cov = getattr(tw, "covariance", None)
        if cov is not None and len(cov) > 0 and math.isfinite(cov[0]) and cov[0] > 0:
            sigma = math.sqrt(cov[0])
        yaw = None
        if twist_frame == "child":
            yaw = _yaw_from_quat(getattr(getattr(getattr(msg, "pose", None), "pose", None), "orientation", None))
    else:                                           # TwistStamped
        lin, yaw = tw.linear, None
    vx, vy = float(lin.x), float(lin.y)
    if not (math.isfinite(vx) and math.isfinite(vy)):
        return None
    if yaw is not None:                             # body (x fwd, y left) -> ENU
        ve = vx * math.cos(yaw) - vy * math.sin(yaw)
        vn = vx * math.sin(yaw) + vy * math.cos(yaw)
    else:
        ve, vn = vx, vy
    tt = t if t is not None else _stamp(msg, 0.0)
    return RefMotion(t=float(tt), ve=ve, vn=vn, sigma=sigma, source=source)


def process_cn0(msg) -> Optional[tuple]:
    """Generic C/N0 input -> (mean, std). Accepts std_msgs/Float32MultiArray-like (.data), or any message with
    a .cn0 / .snr / .data sequence of dB-Hz values. Zeros/NaN are ignored. Configure the real topic type in
    deployment; this is intentionally permissive because no standard ROS message carries per-satellite C/N0."""
    seq = None
    for name in ("cn0", "snr", "data"):
        seq = getattr(msg, name, None)
        if seq is not None:
            break
    if seq is None:
        return None
    m, sd = mean_std([float(v) for v in seq if float(v) > 0])
    return None if m is None else (m, sd)


def build_diagnostic(report: TrustReport, *, name: str = "marsad/gnss_trust", hardware_id: str = "gnss",
                     status_cls: Optional[Callable] = None, value_cls: Optional[Callable] = None):
    """TrustReport -> diagnostic_msgs/DiagnosticStatus-shaped object (SimpleNamespace unless classes given).

    level: OK(0) TRUSTED, WARN(1) DEGRADED, ERROR(2) DENIED. With real classes the level is encoded as
    bytes (ROS 2 DiagnosticStatus.level is a byte)."""
    level = DIAG_LEVEL[report.state]
    kv = [("trust", f"{report.trust:.4f}"), ("state", report.state.value), ("action", report.action.value),
          ("dominant_hypothesis", report.dominant), ("warmup", str(report.warmup)),
          ("gnss_offset_m", "" if report.gnss_offset_m is None else f"{report.gnss_offset_m:.1f}")]
    for i, e in enumerate(report.evidence[:3]):
        kv.append((f"evidence_{i}", e.message))
    if value_cls is None:
        values = [SimpleNamespace(key=k, value=v) for k, v in kv]
    else:
        values = []
        for k, v in kv:
            kvm = value_cls()
            kvm.key, kvm.value = k, v
            values.append(kvm)
    if status_cls is None:
        return SimpleNamespace(level=level, name=name, message=report.summary or report.state.value,
                               hardware_id=hardware_id, values=values)
    st = status_cls()
    st.level = bytes([level])
    st.name, st.message, st.hardware_id = name, report.summary or report.state.value, hardware_id
    st.values = values
    return st


class RosBridge:
    """ROS-agnostic pipeline: callbacks in, TrustEngine, outputs out. This is what the node wires to topics."""

    def __init__(self, engine: Optional[TrustEngine] = None, *, twist_frame: str = "child",
                 ref_contaminated: bool = False, vel_max_age: float = 0.5, uere_m: float = 3.0,
                 clock: Optional[Callable[[], float]] = None):
        self.engine = engine or TrustEngine(preset("ground_robot"))
        self.twist_frame, self.ref_contaminated = twist_frame, ref_contaminated
        self.vel_max_age, self.uere_m, self.clock = vel_max_age, uere_m, clock
        self.warnings: list = []
        if ref_contaminated:
            self.warnings.append(CONTAMINATED_WARNING)
        self.last_report: Optional[TrustReport] = None
        self.dropped_out_of_order = 0
        self._t = -math.inf
        self._vel = None        # (t, ve, vn)
        self._cn0 = None        # (t, mean, std)

    def _time(self, msg) -> float:
        t = _stamp(msg, None)
        if t is None:
            t = self.clock() if self.clock else 0.0
        return t

    def on_gnss_vel(self, msg) -> None:
        """geometry_msgs/TwistStamped or TwistWithCovarianceStamped from the GNSS driver (ENU)."""
        r = process_odom(msg, self._time(msg), twist_frame="parent")
        if r is not None:
            self._vel = (r.t, r.ve, r.vn)

    def on_cn0(self, msg) -> None:
        c = process_cn0(msg)
        if c is not None:
            self._cn0 = (self._time(msg),) + c

    def on_navsat(self, msg) -> Optional[TrustReport]:
        from ..types import NavSample
        t = self._time(msg)
        if t < self._t:
            self.dropped_out_of_order += 1
            return None
        vel = cn0 = None
        if self._vel and t - self._vel[0] <= self.vel_max_age:
            vel = self._vel[1:]
        if self._cn0 and t - self._cn0[0] <= 5.0:
            cn0 = self._cn0[1:]
        fix = process_navsat(msg, t, vel=vel, cn0=cn0, uere_m=self.uere_m)
        self._t = t
        self.last_report = self.engine.update(NavSample(t=t, gnss=fix))
        return self.last_report

    def on_odom(self, msg) -> Optional[TrustReport]:
        from ..types import NavSample
        t = self._time(msg)
        if t < self._t:
            self.dropped_out_of_order += 1
            return None
        ref = process_odom(msg, t, twist_frame=self.twist_frame,
                           source="ros2:odom" + ("[CONTAMINATED]" if self.ref_contaminated else ""))
        if ref is None:
            return None
        self._t = t
        self.last_report = self.engine.update(NavSample(t=t, ref=ref))
        return self.last_report

    @staticmethod
    def outputs(report: TrustReport) -> dict:
        """What the node publishes: trust (Float32.data), state (String.data), diagnostic (namespace)."""
        return {"trust": float(report.trust), "state": report.state.value,
                "diagnostic": build_diagnostic(report)}


LAUNCH_SNIPPET = '''\
# launch/marsad.launch.py   (UNTESTED on a live ROS 2 system -- adjust topic names)
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([Node(
        package="marsad", executable="marsad_node", name="marsad_trust", output="screen",
        parameters=[{
            "navsat_topic": "/gps/fix",          # sensor_msgs/NavSatFix
            "gnss_vel_topic": "",                # geometry_msgs/TwistStamped (optional)
            "odom_topic": "/vio/odometry",       # nav_msgs/Odometry or geometry_msgs/TwistStamped (independent!)
            "odom_type": "odometry",             # "odometry" | "twist"
            "twist_frame": "child",              # "child" (REP-105) | "parent"
            "ref_contaminated": False,           # True if odom_topic is a GPS-fused EKF
            "cn0_topic": "", "cn0_type": "std_msgs/msg/Float32MultiArray",
            "preset": "ground_robot",
        }])])
'''


class MarsadNode(Node):                     # type: ignore[misc]
    """rclpy node: subscribes to NavSatFix + reference odometry (+optional GNSS twist, C/N0), publishes
    ~/trust (std_msgs/Float32), ~/state (std_msgs/String), ~/diagnostics (diagnostic_msgs/DiagnosticStatus).
    Advisory only: it publishes, it never commands. UNTESTED against a real ROS 2 runtime."""

    def __init__(self, bridge: Optional[RosBridge] = None):
        if not HAVE_ROS2:
            raise ImportError("rclpy is not available; source a ROS 2 environment (this node is untested here)")
        super().__init__("marsad_trust")
        from importlib import import_module
        from std_msgs.msg import Float32, String
        from diagnostic_msgs.msg import DiagnosticStatus, KeyValue
        from sensor_msgs.msg import NavSatFix
        P = self.declare_parameter
        navsat_topic = P("navsat_topic", "/gps/fix").value
        gnss_vel_topic = P("gnss_vel_topic", "").value
        odom_topic = P("odom_topic", "/odom").value
        odom_type = P("odom_type", "odometry").value
        twist_frame = P("twist_frame", "child").value
        contaminated = bool(P("ref_contaminated", False).value)
        cn0_topic = P("cn0_topic", "").value
        cn0_type = P("cn0_type", "std_msgs/msg/Float32MultiArray").value
        pname = P("preset", "ground_robot").value
        self._bridge = bridge or RosBridge(TrustEngine(preset(pname)), twist_frame=twist_frame,
                                           ref_contaminated=contaminated, clock=self._now)
        for w in self._bridge.warnings:
            self.get_logger().warn(w)
        self._DS, self._KV = DiagnosticStatus, KeyValue
        self._pub_trust = self.create_publisher(Float32, "~/trust", 10)
        self._pub_state = self.create_publisher(String, "~/state", 10)
        self._pub_diag = self.create_publisher(DiagnosticStatus, "~/diagnostics", 10)
        self._Float32, self._String = Float32, String
        self.create_subscription(NavSatFix, navsat_topic, self._on_navsat, 10)
        if odom_type == "odometry":
            from nav_msgs.msg import Odometry
            self.create_subscription(Odometry, odom_topic, self._on_odom, 10)
        else:
            from geometry_msgs.msg import TwistStamped
            self.create_subscription(TwistStamped, odom_topic, self._on_odom, 10)
        if gnss_vel_topic:
            from geometry_msgs.msg import TwistStamped
            self.create_subscription(TwistStamped, gnss_vel_topic, self._bridge.on_gnss_vel, 10)
        if cn0_topic:
            pkg, _, cls = cn0_type.replace("/msg/", "/").partition("/")
            msg_cls = getattr(import_module(f"{pkg}.msg"), cls)
            self.create_subscription(msg_cls, cn0_topic, self._bridge.on_cn0, 10)

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_odom(self, msg):
        self._bridge.on_odom(msg)

    def _on_navsat(self, msg):
        rep = self._bridge.on_navsat(msg)
        if rep is None:
            return
        out = self._bridge.outputs(rep)
        a = self._Float32(); a.data = out["trust"]; self._pub_trust.publish(a)
        b = self._String(); b.data = out["state"]; self._pub_state.publish(b)
        self._pub_diag.publish(build_diagnostic(rep, status_cls=self._DS, value_cls=self._KV))


def main(args=None):                        # pragma: no cover
    if not HAVE_ROS2:
        raise SystemExit("rclpy not available")
    rclpy.init(args=args)
    node = MarsadNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":      # pragma: no cover
    main()
