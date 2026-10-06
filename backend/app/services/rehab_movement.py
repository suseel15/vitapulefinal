from __future__ import annotations

import math
import random
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from app.schemas.rehab import FatigueSignal, MovementQuality, SessionSource
from app.services.contracts import MovementDataSource, MovementSample


class SimulationScenario(StrEnum):
    NORMAL = "NORMAL"
    GOOD_FORM = "GOOD_FORM"
    POOR_FORM = "POOR_FORM"
    FATIGUE = "FATIGUE"
    ABNORMAL_MOVEMENT = "ABNORMAL_MOVEMENT"
    CONNECTION_DROP = "CONNECTION_DROP"


class SimulationMovementDataSource(MovementDataSource):
    def __init__(
        self,
        *,
        scenario: SimulationScenario = SimulationScenario.NORMAL,
        seed: int = 0,
    ) -> None:
        self.scenario = scenario
        self._random = random.Random(seed)

    async def samples(
        self,
        *,
        duration_seconds: float,
        sample_rate_hz: float = 10,
    ) -> AsyncIterator[MovementSample]:
        if not math.isfinite(duration_seconds) or duration_seconds < 0:
            raise ValueError("duration_seconds must be finite and non-negative")
        if not math.isfinite(sample_rate_hz) or not 0 < sample_rate_hz <= 100:
            raise ValueError("sample_rate_hz must be greater than zero and at most 100")
        interval_ms = 1000 / sample_rate_hz
        count = math.ceil(duration_seconds * sample_rate_hz)
        for index in range(count):
            phase = index / sample_rate_hz
            rep_phase = phase % 3.0
            if self.scenario == SimulationScenario.CONNECTION_DROP and index >= count // 2:
                break
            in_rest = rep_phase >= 2.3
            fatigue = self.scenario == SimulationScenario.FATIGUE and phase >= duration_seconds / 2
            amplitude = 0.18 if in_rest else 1.0 + (0.2 if fatigue else 0)
            if self.scenario == SimulationScenario.GOOD_FORM:
                noise = 0.006
            elif self.scenario in {SimulationScenario.POOR_FORM, SimulationScenario.ABNORMAL_MOVEMENT}:
                noise = 0.16
            else:
                noise = 0.035
            if self.scenario == SimulationScenario.ABNORMAL_MOVEMENT and index % max(1, round(sample_rate_hz * 3)) == 0:
                amplitude *= 2.5
            sway = amplitude * math.sin(2 * math.pi * rep_phase / 2.3)
            jitter = lambda: self._random.uniform(-noise, noise)
            yield MovementSample(
                timestamp=round(index * interval_ms),
                ax=sway + jitter(),
                ay=jitter(),
                az=1.0 + 0.1 * math.cos(2 * math.pi * rep_phase / 2.3) * amplitude + jitter(),
                gx=0.3 * sway + jitter(),
                gy=0.1 * sway + jitter(),
                gz=jitter(),
                source=SessionSource.SIMULATION.value,
            )


class HttpPollingMovementDataSource:
    """Phase 4 transport contract for the ESP32 /status and /data polling API."""

    status_path = "/status"
    data_path = "/data"
    default_base_url = "http://192.168.4.1"


class WebSocketMovementDataSource:
    """Reserved transport contract; the Phase 4 firmware protocol is not connected."""


class BasicSessionSafetyMonitor:
    def evaluate(self, sample: MovementSample) -> str:
        if not _valid_sample(sample):
            return "REVIEW_REQUIRED"
        return "CAUTION" if max(abs(sample.ax), abs(sample.ay), abs(sample.az)) > 2.5 else "NORMAL"


@dataclass(frozen=True)
class DetectedRepetition:
    rep_number: int
    started_at: int
    ended_at: int
    duration_ms: int


class RepetitionDetector(Protocol):
    def feed(self, sample: MovementSample) -> DetectedRepetition | None: ...

    def reset(self) -> None: ...


class GenericMovementRepetitionDetector:
    def __init__(self, threshold: float = 0.45, minimum_duration_ms: int = 250) -> None:
        self.threshold = threshold
        self.minimum_duration_ms = minimum_duration_ms
        self._moving = False
        self._start = 0
        self._count = 0

    def feed(self, sample: MovementSample) -> DetectedRepetition | None:
        if not _valid_sample(sample):
            return None
        magnitude = math.sqrt(sample.ax**2 + sample.ay**2 + sample.az**2)
        is_moving = abs(magnitude - 1.0) >= self.threshold
        if is_moving and not self._moving:
            self._moving = True
            self._start = sample.timestamp
            return None
        if self._moving and not is_moving:
            self._moving = False
            duration = sample.timestamp - self._start
            if duration < self.minimum_duration_ms:
                return None
            self._count += 1
            return DetectedRepetition(self._count, self._start, sample.timestamp, duration)
        return None

    def reset(self) -> None:
        self._moving = False
        self._start = 0
        self._count = 0


class SquatRepetitionDetector(GenericMovementRepetitionDetector):
    def __init__(self, threshold: float = 0.35, minimum_duration_ms: int = 700) -> None:
        super().__init__(threshold, minimum_duration_ms)


@dataclass(frozen=True)
class MovementQualitySummary:
    sample_count: int
    peak_acceleration: float | None
    peak_angular_velocity: float | None
    variability: float | None
    movement_quality: MovementQuality
    stability: MovementQuality
    smoothness: MovementQuality
    fatigue_signal: FatigueSignal


class MovementQualityEngine:
    def summarize(self, samples: Iterable[MovementSample]) -> MovementQualitySummary:
        valid = [sample for sample in samples if _valid_sample(sample)]
        if len(valid) < 10:
            return MovementQualitySummary(
                len(valid), None, None, None,
                MovementQuality.INSUFFICIENT_DATA,
                MovementQuality.INSUFFICIENT_DATA,
                MovementQuality.INSUFFICIENT_DATA,
                FatigueSignal.INSUFFICIENT_DATA,
            )
        accel = [math.sqrt(sample.ax**2 + sample.ay**2 + sample.az**2) for sample in valid]
        gyro = [math.sqrt(sample.gx**2 + sample.gy**2 + sample.gz**2) for sample in valid]
        mean = sum(accel) / len(accel)
        variability = math.sqrt(sum((value - mean) ** 2 for value in accel) / len(accel))
        changes = [abs(right - left) for left, right in zip(accel, accel[1:])]
        jerk_signal = sum(changes) / len(changes) if changes else None
        stability = _quality_from_variability(variability)
        smoothness = _quality_from_variability(jerk_signal)
        overall = (
            MovementQuality.NEEDS_ATTENTION
            if MovementQuality.NEEDS_ATTENTION in {stability, smoothness}
            else MovementQuality.MODERATE
            if MovementQuality.MODERATE in {stability, smoothness}
            else MovementQuality.GOOD
        )
        return MovementQualitySummary(
            len(valid),
            max(accel),
            max(gyro),
            variability,
            overall,
            stability,
            smoothness,
            FatigueSignal.INSUFFICIENT_DATA,
        )


def fatigue_from_repetitions(durations_ms: list[int], qualities: list[MovementQuality]) -> FatigueSignal:
    if len(durations_ms) < 3:
        return FatigueSignal.INSUFFICIENT_DATA
    if any(duration <= 0 for duration in durations_ms):
        raise ValueError("repetition durations must be positive")
    first = sum(durations_ms[: len(durations_ms) // 2]) / len(durations_ms[: len(durations_ms) // 2])
    last_values = durations_ms[len(durations_ms) // 2 :]
    last = sum(last_values) / len(last_values)
    slower_ratio = (last - first) / first
    worsening = sum(quality == MovementQuality.NEEDS_ATTENTION for quality in qualities)
    if slower_ratio >= 0.35 or worsening >= max(2, len(qualities) // 2):
        return FatigueSignal.HIGH
    if slower_ratio >= 0.15 or worsening:
        return FatigueSignal.MODERATE
    return FatigueSignal.LOW


def _quality_from_variability(variability: float | None) -> MovementQuality:
    if variability is None or not math.isfinite(variability):
        return MovementQuality.INSUFFICIENT_DATA
    if variability <= 0.18:
        return MovementQuality.GOOD
    if variability <= 0.38:
        return MovementQuality.MODERATE
    return MovementQuality.NEEDS_ATTENTION


def _valid_sample(sample: MovementSample) -> bool:
    return all(math.isfinite(value) for value in (sample.ax, sample.ay, sample.az, sample.gx, sample.gy, sample.gz))


def build_repetition_record(detected: DetectedRepetition) -> dict[str, object]:
    return {
        "rep_number": detected.rep_number,
        "started_at": datetime.fromtimestamp(detected.started_at / 1000, UTC).isoformat(),
        "ended_at": datetime.fromtimestamp(detected.ended_at / 1000, UTC).isoformat(),
        "duration_ms": detected.duration_ms,
    }
