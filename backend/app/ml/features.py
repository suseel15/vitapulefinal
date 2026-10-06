from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import mean, pstdev
from typing import Any

FEATURE_SCHEMA_VERSION = "movement-features-v1"
AXES = ("ax", "ay", "az", "gx", "gy", "gz")
FEATURE_NAMES = tuple(
    [f"{axis}_{stat}" for axis in AXES for stat in ("mean", "std", "min", "max", "range")]
    + [
        "acc_magnitude_mean",
        "acc_magnitude_std",
        "acc_magnitude_rms",
        "acc_magnitude_peak",
        "gyro_magnitude_mean",
        "gyro_magnitude_std",
        "gyro_magnitude_peak",
        "dynamic_acceleration_rms",
        "peak_count",
        "mean_peak_spacing_ms",
        "movement_duration_ms",
        "cadence_hz",
        "sampling_rate_hz",
        "sample_count",
        "missing_sample_percentage",
    ]
)


def extract_features(
    samples: Sequence[Mapping[str, Any]],
    *,
    expected_rate_hz: float = 10.0,
) -> dict[str, float]:
    """Extract stable features from one time-ordered raw-IMU window."""
    if not math.isfinite(expected_rate_hz) or expected_rate_hz <= 0:
        raise ValueError("expected_rate_hz must be finite and positive")
    if len(samples) < 2:
        raise ValueError("A feature window needs at least two samples.")

    timestamps = [_number(sample, "timestamp") for sample in samples]
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise ValueError("Sample timestamps must be strictly increasing.")
    vectors = {axis: [_number(sample, axis) for sample in samples] for axis in AXES}
    duration_ms = timestamps[-1] - timestamps[0]
    observed_rate = (len(samples) - 1) * 1000 / duration_ms

    output: dict[str, float] = {}
    for axis, values in vectors.items():
        axis_mean = mean(values)
        output.update({
            f"{axis}_mean": axis_mean,
            f"{axis}_std": pstdev(values),
            f"{axis}_min": min(values),
            f"{axis}_max": max(values),
            f"{axis}_range": max(values) - min(values),
        })

    acc_magnitude = [
        math.sqrt(vectors["ax"][i] ** 2 + vectors["ay"][i] ** 2 + vectors["az"][i] ** 2)
        for i in range(len(samples))
    ]
    gyro_magnitude = [
        math.sqrt(vectors["gx"][i] ** 2 + vectors["gy"][i] ** 2 + vectors["gz"][i] ** 2)
        for i in range(len(samples))
    ]
    magnitude_mean = mean(acc_magnitude)
    dynamic = [value - magnitude_mean for value in acc_magnitude]
    peaks = _peak_timestamps(acc_magnitude, timestamps, min_prominence=0.08)
    peak_spacings = [right - left for left, right in zip(peaks, peaks[1:])]
    output.update({
        "acc_magnitude_mean": magnitude_mean,
        "acc_magnitude_std": pstdev(acc_magnitude),
        "acc_magnitude_rms": math.sqrt(mean(value * value for value in acc_magnitude)),
        "acc_magnitude_peak": max(acc_magnitude),
        "gyro_magnitude_mean": mean(gyro_magnitude),
        "gyro_magnitude_std": pstdev(gyro_magnitude),
        "gyro_magnitude_peak": max(gyro_magnitude),
        "dynamic_acceleration_rms": math.sqrt(mean(value * value for value in dynamic)),
        "peak_count": float(len(peaks)),
        "mean_peak_spacing_ms": mean(peak_spacings) if peak_spacings else 0.0,
        "movement_duration_ms": float(duration_ms),
        "cadence_hz": 1000 / mean(peak_spacings) if peak_spacings else 0.0,
        "sampling_rate_hz": observed_rate,
        "sample_count": float(len(samples)),
        "missing_sample_percentage": max(0.0, 1 - observed_rate / expected_rate_hz) * 100,
    })
    if tuple(output) != FEATURE_NAMES:
        raise RuntimeError("Feature implementation does not match its declared schema.")
    if not all(math.isfinite(value) for value in output.values()):
        raise ValueError("Feature extraction produced a non-finite value.")
    return output


def _number(sample: Mapping[str, Any], key: str) -> float:
    value = sample.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Sample field {key!r} must be a finite number.")
    return float(value)


def _peak_timestamps(
    values: Sequence[float],
    timestamps: Sequence[float],
    *,
    min_prominence: float,
) -> list[float]:
    candidates = [
        index for index in range(1, len(values) - 1)
        if values[index] > values[index - 1] and values[index] >= values[index + 1]
    ]
    threshold = mean(values) + min_prominence
    return [timestamps[index] for index in candidates if values[index] >= threshold]
