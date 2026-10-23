"""A velocity consistent carry off must not be learned away as reference bias (docs/PREREGISTRATION_BIAS.md).

The spoofer shifts the GNSS velocity together with the position, so (reference minus GNSS velocity) equals the drift
rate and the bias estimator would absorb it. The guard refuses an estimate that moves faster than a reference sensor
bias can wander and turns the refusal into drift evidence.
"""
from test_mixed_rate import first_alarm, flight


def test_slow_velocity_consistent_drift_is_not_absorbed():
    lat = first_alarm(flight(ref_hz=5.0, gnss_hz=5.0, interleaved=False, rate=0.25, duration=300.0))
    assert lat is not None


def test_clean_flight_stays_trusted_with_guard():
    assert first_alarm(flight(ref_hz=5.0, gnss_hz=5.0, interleaved=False, rate=0.0, duration=300.0)) is None
