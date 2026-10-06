from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
import math
from statistics import mean, pstdev


class SignalQualityStatus(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    INSUFFICIENT = "INSUFFICIENT"


class BaselineStatus(StrEnum):
    PERSONAL_BASELINE_NOT_AVAILABLE = "PERSONAL_BASELINE_NOT_AVAILABLE"
    STABLE = "STABLE"
    IMPROVED = "IMPROVED"
    DEVIATION_DETECTED = "DEVIATION_DETECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FatigueStatus(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class QualityMetrics:
    status: SignalQualityStatus
    sample_count: int
    sampling_rate_hz: float | None
    missing_sample_percentage: float | None
    latency_ms: float | None
    variance: float | None
    clipping_count: int
    stale_sample_count: int


def assess_signal_quality(
    timestamps_ms: Sequence[int],
    magnitudes: Sequence[float],
    *,
    invalid_samples: int = 0,
    failed_requests: int = 0,
    average_latency_ms: float | None = None,
    expected_rate_hz: float = 10.0,
    minimum_rate_hz: float = 8.0,
) -> QualityMetrics:
    if invalid_samples < 0 or failed_requests < 0:
        raise ValueError("sample error counts cannot be negative")
    if len(timestamps_ms) != len(magnitudes):
        raise ValueError("timestamps and magnitudes must have the same length")
    if len(timestamps_ms) < 2:
        return QualityMetrics(SignalQualityStatus.INSUFFICIENT, len(timestamps_ms), None, None,
                              average_latency_ms, None, 0, 0)
    if any(not math.isfinite(value) for value in magnitudes):
        raise ValueError("magnitudes must be finite")
    deltas = [right - left for left, right in zip(timestamps_ms, timestamps_ms[1:])]
    if any(delta <= 0 for delta in deltas):
        raise ValueError("timestamps must be strictly increasing")
    duration_s = (timestamps_ms[-1] - timestamps_ms[0]) / 1000
    rate = (len(timestamps_ms) - 1) / duration_s
    estimated = round(duration_s * expected_rate_hz) + 1
    missing = max(0.0, (estimated - len(timestamps_ms)) / estimated * 100)
    stale = sum(delta > 1500 for delta in deltas)
    clipping = sum(abs(value) >= 16.0 for value in magnitudes)
    variance = pstdev(magnitudes) ** 2
    bad_percentage = (invalid_samples + failed_requests) / max(1, len(timestamps_ms) + invalid_samples)
    if rate < minimum_rate_hz or bad_percentage >= 0.25 or stale >= 2:
        state = SignalQualityStatus.INSUFFICIENT
    elif bad_percentage >= 0.10 or stale or clipping:
        state = SignalQualityStatus.POOR
    elif missing >= 10:
        state = SignalQualityStatus.DEGRADED
    elif missing >= 3 or (average_latency_ms is not None and average_latency_ms > 100):
        state = SignalQualityStatus.GOOD
    else:
        state = SignalQualityStatus.EXCELLENT
    return QualityMetrics(state, len(timestamps_ms), rate, missing, average_latency_ms,
                          variance, clipping, stale)


def fatigue_signal(durations_ms: Sequence[int], quality_ranks: Sequence[int] = ()) -> FatigueStatus:
    if len(durations_ms) < 6 or any(value <= 0 for value in durations_ms):
        return FatigueStatus.INSUFFICIENT_DATA
    midpoint = len(durations_ms) // 2
    first = mean(durations_ms[:midpoint])
    last = mean(durations_ms[midpoint:])
    ratio = (last - first) / first
    worsening = sum(rank <= 0 for rank in quality_ranks)
    if ratio >= 0.35 or worsening >= max(2, len(quality_ranks) // 2):
        return FatigueStatus.HIGH
    if ratio >= 0.15 or worsening:
        return FatigueStatus.MODERATE
    return FatigueStatus.LOW


@dataclass(frozen=True)
class PersonalBaseline:
    exercise_id: str
    sensor_placement: str
    session_count: int
    repetition_count: int
    mean_duration_ms: float
    duration_std_ms: float
    mean_amplitude: float
    baseline_version: str = "1"


def compare_baseline(
    baseline: PersonalBaseline | None,
    *,
    exercise_id: str,
    sensor_placement: str,
    durations_ms: Sequence[int],
    amplitudes: Sequence[float],
    minimum_sessions: int = 3,
    minimum_repetitions: int = 20,
) -> BaselineStatus:
    if baseline is None:
        return BaselineStatus.PERSONAL_BASELINE_NOT_AVAILABLE
    if baseline.exercise_id != exercise_id or baseline.sensor_placement != sensor_placement:
        return BaselineStatus.INSUFFICIENT_DATA
    if baseline.session_count < minimum_sessions or baseline.repetition_count < minimum_repetitions:
        return BaselineStatus.INSUFFICIENT_DATA
    if not durations_ms or len(durations_ms) != len(amplitudes):
        return BaselineStatus.INSUFFICIENT_DATA
    current_duration = mean(durations_ms)
    current_amplitude = mean(amplitudes)
    duration_scale = max(baseline.duration_std_ms, baseline.mean_duration_ms * 0.1, 1.0)
    deviation = abs(current_duration - baseline.mean_duration_ms) / duration_scale
    amplitude_deviation = abs(current_amplitude - baseline.mean_amplitude) / max(abs(baseline.mean_amplitude), 0.05)
    if deviation >= 2 or amplitude_deviation >= 0.5:
        return BaselineStatus.DEVIATION_DETECTED
    if current_duration < baseline.mean_duration_ms * 0.9 and amplitude_deviation < 0.2:
        return BaselineStatus.IMPROVED
    return BaselineStatus.STABLE


@dataclass(frozen=True)
class AnomalyObservation:
    movement_deviation: float
    duration_deviation: float
    timestamp_ms: int


class MovementAnomalyEngine:
    """Rule-based repeated-deviation signal; it is not an injury detector."""

    def __init__(self, confirmation_count: int = 3) -> None:
        if confirmation_count < 2:
            raise ValueError("confirmation_count must be at least two")
        self.confirmation_count = confirmation_count
        self._recent: list[AnomalyObservation] = []

    def observe(self, observation: AnomalyObservation) -> bool:
        if not all(math.isfinite(value) for value in
                   (observation.movement_deviation, observation.duration_deviation)):
            raise ValueError("anomaly deviations must be finite")
        unusual = observation.movement_deviation >= 2 or observation.duration_deviation >= 2
        self._recent.append(observation)
        self._recent = self._recent[-self.confirmation_count:]
        return unusual and len(self._recent) == self.confirmation_count and all(
            item.movement_deviation >= 2 or item.duration_deviation >= 2 for item in self._recent
        )


def classify_progress(states: Sequence[str]) -> str:
    rank = {"NEEDS_ATTENTION": 0, "MODERATE": 1, "GOOD": 2}
    if len(states) < 3 or any(state not in rank for state in states):
        return "INSUFFICIENT_DATA"
    first = mean(rank[state] for state in states[: len(states) // 2])
    last = mean(rank[state] for state in states[len(states) // 2 :])
    if last - first >= 0.5:
        return "IMPROVING"
    if first - last >= 0.5:
        return "DECLINING"
    if pstdev(rank[state] for state in states) >= 0.75:
        return "VARIABLE"
    return "STABLE"
