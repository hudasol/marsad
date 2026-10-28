# Examples

* `quickstart.py`: library use on a simulated scenario.
* `ground_robot.json`: engine settings for a wheeled robot with a wheel odometry reference, for
  `marsad replay LOG --config examples/ground_robot.json` or `marsad monitor CONNECTION --config ...`.
  Set `ref_bias_bound` to the largest velocity bias your reference sensor can have: it sets the slowest drift that can
  be detected (see docs/KNOWN_LIMITS.md).
