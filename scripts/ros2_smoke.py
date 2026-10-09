"""ROS 2 smoke test: run MarsadNode against synthetic NavSatFix + Odometry on a real rclpy runtime.

Needs a sourced ROS 2 environment (CI: ros:humble container). Checks that the node
 1. publishes TRUSTED for clean, consistent fixes of a stationary platform, and
 2. publishes DENIED within a few seconds of a 1.1 km position jump (a takeover).
Synthetic data only; not a validation on a robot.
"""
import sys
import time
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import String

from marsad.adapters.ros2 import MarsadNode


class Feeder(Node):
    def __init__(self):
        super().__init__("feeder")
        self.fix = self.create_publisher(NavSatFix, "/gps/fix", 10)
        self.odo = self.create_publisher(Odometry, "/odom", 10)
        self.lat, self.lon = 24.4539, 54.3773
        self.states = []
        self.create_subscription(String, "/marsad_trust/state", lambda m: self.states.append((time.time(), m.data)), 10)
        self.create_timer(0.2, self.tick)

    def tick(self):
        now = self.get_clock().now().to_msg()
        f = NavSatFix()
        f.header.stamp = now; f.header.frame_id = "gps"
        f.status.status = NavSatStatus.STATUS_FIX
        f.latitude, f.longitude, f.altitude = self.lat, self.lon, 10.0
        f.position_covariance = [4.0, 0.0, 0.0, 0.0, 4.0, 0.0, 0.0, 0.0, 9.0]
        f.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        self.fix.publish(f)
        o = Odometry()
        o.header.stamp = now; o.header.frame_id = "odom"; o.child_frame_id = "base_link"
        o.pose.pose.orientation.w = 1.0
        self.odo.publish(o)


def main() -> int:
    rclpy.init()
    node = MarsadNode()
    feeder = Feeder()
    ex = MultiThreadedExecutor()
    ex.add_node(node); ex.add_node(feeder)
    t0 = time.time()
    while time.time() - t0 < 12.0:
        ex.spin_once(timeout_sec=0.05)
    clean = [s for _, s in feeder.states]
    feeder.lat += 0.01                       # ~1.1 km takeover jump
    t1 = time.time()
    while time.time() - t1 < 6.0:
        ex.spin_once(timeout_sec=0.05)
    after = [s for ts, s in feeder.states if ts >= t1]
    print("clean states seen:", sorted(set(clean)), " after jump:", sorted(set(after)))
    ok = bool(clean) and set(clean) == {"TRUSTED"} and "DENIED" in after
    rclpy.shutdown()
    print("ROS2 SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
