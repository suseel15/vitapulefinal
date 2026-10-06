from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.api.v1 import wellbeing as wellbeing_api
from app.api.v1.health import athlete_context
from app.main import app
from app.schemas.wellbeing import CameraFeaturesCreate, CameraSessionCreate, CheckInCreate, SleepRecordCreate
from app.services.wellbeing_service import classify_trend, interpret_wellbeing, recovery_state

client = TestClient(app)


def test_wellbeing_endpoints_require_an_authenticated_athlete() -> None:
    paths = (
        "/api/v1/wellbeing/overview",
        "/api/v1/wellbeing/checkins",
        "/api/v1/wellbeing/camera/sessions",
        "/api/v1/wellbeing/sleep",
        "/api/v1/wellbeing/recovery",
        "/api/v1/wellbeing/history",
        "/api/v1/wellbeing/trends",
        "/api/v1/wellbeing/reports",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["success"] is False


def test_checkin_accepts_only_self_reported_bounded_scales() -> None:
    record = CheckInCreate(energy=2, stress=4, fatigue=3, soreness=1, recovery_feeling=2)
    assert record.source == "SELF_REPORTED"
    with pytest.raises(ValidationError):
        CheckInCreate(energy=6, stress=4, fatigue=3, soreness=1, recovery_feeling=2)
    with pytest.raises(ValidationError):
        CheckInCreate(energy=2, stress=4, fatigue=3, soreness=1, recovery_feeling=2, source="CAMERA_OBSERVED")


def test_camera_payload_rejects_raw_video_and_non_30_second_completion() -> None:
    started = datetime.now(UTC)
    with pytest.raises(ValidationError, match="30 seconds"):
        CameraSessionCreate(
            started_at=started,
            completed_at=started + timedelta(seconds=20),
            duration_seconds=20,
            status="COMPLETED",
            capture_quality="GOOD",
            valid_frame_ratio=0.9,
            face_presence_ratio=0.9,
        )
    with pytest.raises(ValidationError):
        CameraSessionCreate(
            started_at=started,
            duration_seconds=30,
            status="COMPLETED",
            capture_quality="GOOD",
            valid_frame_ratio=0.9,
            face_presence_ratio=0.9,
            raw_video_retained=True,
        )
    features = CameraFeaturesCreate(
        face_presence_ratio=0.8,
        face_position_stability="STABLE",
        head_movement_magnitude=None,
        head_movement_variability=None,
        head_orientation_range=None,
        capture_quality="FAIR",
        feature_schema_version="camera-wellbeing-v1",
    )
    assert features.head_movement_magnitude is None


def test_sleep_duration_is_derived_from_timestamps_and_rejects_inconsistent_input() -> None:
    record = SleepRecordCreate(
        start_time=datetime(2026, 10, 5, 22, 30, tzinfo=UTC),
        end_time=datetime(2026, 10, 6, 6, 30, tzinfo=UTC),
    )
    assert record.duration_minutes == 480
    with pytest.raises(ValidationError, match="must match"):
        SleepRecordCreate(
            start_time=datetime(2026, 10, 5, 22, 30, tzinfo=UTC),
            end_time=datetime(2026, 10, 6, 6, 30, tzinfo=UTC),
            duration_minutes=400,
        )


def test_recovery_and_interpretation_keep_data_sources_explicit_and_avoid_diagnosis() -> None:
    checkin = {"recovery_feeling": 2, "fatigue": 4, "soreness": 3, "stress": 4}
    recovery, factors = recovery_state(checkin, {"duration_minutes": 390, "source": "SELF_REPORTED"})
    assert recovery == "LOW"
    assert factors["fatigue"]["source"] == "SELF_REPORTED"
    assert factors["sleep_duration_minutes"]["source"] == "SELF_REPORTED"
    context = interpret_wellbeing(checkin, None, None, {"recovery_state": recovery})
    assert context["recovery_source"] == "CALCULATED"
    assert all(observation["source"] == "SELF_REPORTED" for observation in context["observations"])
    assert "does not establish a medical or psychological diagnosis" in context["summary"]


def test_trends_require_real_observations_and_report_variability() -> None:
    assert classify_trend([4])["classification"] == "INSUFFICIENT_DATA"
    assert classify_trend([1, 2, 3])["classification"] == "IMPROVING"
    assert classify_trend([1, 5, 1, 5, 1, 5])["classification"] == "VARIABLE"


def test_overview_derives_unsaved_recovery_context_from_available_records(monkeypatch: pytest.MonkeyPatch) -> None:
    class Repository:
        async def list(self, table: str, **kwargs: object) -> list[dict]:
            if table == "wellbeing_checkins":
                return [{"recovery_feeling": 2, "fatigue": 4, "soreness": 3, "stress": 4}]
            if table == "sleep_records":
                return [{"duration_minutes": 390, "source": "SELF_REPORTED"}]
            return []

    async def fake_athlete_context() -> tuple:
        return (), (), ()

    app.dependency_overrides[athlete_context] = fake_athlete_context
    monkeypatch.setattr(wellbeing_api, "_repo", lambda _context: Repository())
    try:
        response = client.get("/api/v1/wellbeing/overview")
    finally:
        app.dependency_overrides.pop(athlete_context, None)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["recovery"] is None
    assert payload["recovery_context"]["recovery_state"] == "LOW"
    assert payload["recovery_context"]["source"] == "CALCULATED"
    assert payload["recovery_context"]["supporting_factors"]["fatigue"]["source"] == "SELF_REPORTED"
