import asyncio

from pydantic import ValidationError
import pytest

from app.schemas.rehab import (
    FatigueSignal,
    MovementQuality,
    RehabSessionCreate,
    ReadinessStatus,
    SensorPlacement,
    SessionSource,
)
from app.services.contracts import MovementSample
from app.services.rehab_movement import (
    GenericMovementRepetitionDetector,
    BasicSessionSafetyMonitor,
    MovementQualityEngine,
    SimulationMovementDataSource,
    SimulationScenario,
    SquatRepetitionDetector,
    fatigue_from_repetitions,
)


def test_simulation_source_is_seeded_and_labels_every_sample() -> None:
    async def collect(source: SimulationMovementDataSource) -> list[MovementSample]:
        return [sample async for sample in source.samples(duration_seconds=1, sample_rate_hz=10)]

    first = asyncio.run(collect(SimulationMovementDataSource(seed=8, scenario=SimulationScenario.GOOD_FORM)))
    second = asyncio.run(collect(SimulationMovementDataSource(seed=8, scenario=SimulationScenario.GOOD_FORM)))

    assert first == second
    assert len(first) == 10
    assert all(sample.source == SessionSource.SIMULATION.value for sample in first)
    assert all(sample.timestamp == index * 100 for index, sample in enumerate(first))


def test_simulation_rejects_unbounded_sampling_inputs() -> None:
    async def collect() -> list[MovementSample]:
        return [sample async for sample in SimulationMovementDataSource().samples(duration_seconds=1, sample_rate_hz=101)]

    try:
        asyncio.run(collect())
    except ValueError as error:
        assert "sample_rate_hz" in str(error)
    else:
        raise AssertionError("Sampling above the supported 100 Hz must be rejected.")


def test_repetition_detector_ignores_short_spikes_and_detects_a_complete_movement() -> None:
    detector = GenericMovementRepetitionDetector(threshold=0.45, minimum_duration_ms=500)
    rest = MovementSample(0, 0, 0, 1, 0, 0, 0, "SIMULATION")
    start = MovementSample(100, 2, 0, 1, 0, 0, 0, "SIMULATION")
    short_end = MovementSample(300, 0, 0, 1, 0, 0, 0, "SIMULATION")
    full_end = MovementSample(800, 0, 0, 1, 0, 0, 0, "SIMULATION")

    assert detector.feed(rest) is None
    assert detector.feed(start) is None
    assert detector.feed(short_end) is None
    assert detector.feed(start) is None
    detected = detector.feed(full_end)

    assert detected is not None
    assert detected.rep_number == 1
    assert detected.duration_ms == 700


def test_squat_detector_requires_a_longer_cycle_than_generic_movement() -> None:
    detector = SquatRepetitionDetector()
    assert detector.minimum_duration_ms > GenericMovementRepetitionDetector().minimum_duration_ms


def test_quality_engine_reports_insufficient_data_instead_of_fabricating_a_result() -> None:
    result = MovementQualityEngine().summarize([
        MovementSample(0, 0, 0, 1, 0, 0, 0, "SIMULATION"),
    ])

    assert result.sample_count == 1
    assert result.movement_quality == MovementQuality.INSUFFICIENT_DATA
    assert result.stability == MovementQuality.INSUFFICIENT_DATA
    assert result.peak_acceleration is None


def test_fatigue_signal_uses_repetition_duration_trend_with_minimum_observations() -> None:
    assert fatigue_from_repetitions([1000, 1000], []) == FatigueSignal.INSUFFICIENT_DATA
    assert fatigue_from_repetitions([1000, 1000, 1000, 1500, 1600, 1700], []) == FatigueSignal.HIGH
    assert fatigue_from_repetitions([1000, 1000, 1000, 1100, 1100, 1100], []) == FatigueSignal.LOW


def test_invalid_repetition_duration_is_rejected() -> None:
    try:
        fatigue_from_repetitions([1000, 0, 1000], [])
    except ValueError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("Invalid repetition durations must not produce a fatigue result.")


def test_manual_session_rejects_sensor_claims() -> None:
    import uuid

    with pytest.raises(ValidationError, match="Manual sessions cannot include sensor fields"):
        RehabSessionCreate(
            exercise_id=uuid.uuid4(),
            source=SessionSource.MANUAL,
            sensor_placement=SensorPlacement.THIGH,
        )


def test_safety_monitor_only_reports_a_simple_signal_caution() -> None:
    monitor = BasicSessionSafetyMonitor()
    normal = MovementSample(0, 0, 0, 1, 0, 0, 0, "SIMULATION")
    caution = MovementSample(100, 3, 0, 1, 0, 0, 0, "SIMULATION")
    invalid = MovementSample(200, float("nan"), 0, 1, 0, 0, 0, "SIMULATION")

    assert monitor.evaluate(normal) == "NORMAL"
    assert monitor.evaluate(caution) == "CAUTION"
    assert monitor.evaluate(invalid) == "REVIEW_REQUIRED"


def test_readiness_requires_review_when_movement_warning_is_unresolved() -> None:
    from app.api.v1.rehab import _readiness

    status, recommendation, factors = _readiness(
        [{"movement_quality": "GOOD"}],
        "GOOD",
        "FEELING_OK",
        "NONE",
        ["CAUTION_MOVEMENT_SIGNAL"],
    )

    assert status == ReadinessStatus.REVIEW_REQUIRED
    assert "movement warning" in recommendation
    assert {"factor": "unresolved_movement_warnings", "value": "1"} in factors


def test_program_requirement_ids_are_validated_and_deduplicated() -> None:
    from uuid import UUID

    from fastapi import HTTPException

    from app.api.v1.rehab import _program_requirement_ids

    identifier = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert _program_requirement_ids([identifier, identifier], "exercise") == [str(UUID(identifier))]
    with pytest.raises(HTTPException) as error:
        _program_requirement_ids(["not-a-uuid"], "exercise")
    assert error.value.status_code == 502
    assert "invalid exercise identifiers" in error.value.detail
