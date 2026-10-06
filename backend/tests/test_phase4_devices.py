from math import nan
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.device import DeviceRegistrationCreate
from app.schemas.rehab import (
    FatigueSignal,
    MovementQuality,
    MovementSummaryCreate,
    RehabSessionCreate,
    SensorPlacement,
    SessionSource,
)


def test_device_registration_accepts_only_the_supported_local_protocol() -> None:
    registration = DeviceRegistrationCreate(device_identifier="ESP32-001")

    assert str(registration.ip) == "192.168.4.1"
    assert registration.sensor_type == "MPU6050"
    assert registration.transport == "HTTP"

    with pytest.raises(ValidationError):
        DeviceRegistrationCreate(device_identifier="ESP32-001", ip="192.168.4.2")
    with pytest.raises(ValidationError):
        DeviceRegistrationCreate(device_identifier="ESP32-001", transport="MQTT")
    with pytest.raises(ValidationError):
        DeviceRegistrationCreate(device_identifier="ESP32-001", wifi_password="must-not-be-accepted")


def test_live_sensor_sessions_require_an_owned_device_and_supported_sensor() -> None:
    with pytest.raises(ValidationError, match="registered device"):
        RehabSessionCreate(
            exercise_id=uuid4(),
            source=SessionSource.LIVE_SENSOR,
            sensor_type="MPU6050",
            sensor_placement=SensorPlacement.THIGH,
        )

    session = RehabSessionCreate(
        exercise_id=uuid4(),
        client_session_id=uuid4(),
        source=SessionSource.LIVE_SENSOR,
        sensor_type="MPU6050",
        sensor_placement=SensorPlacement.THIGH,
        device_id=uuid4(),
    )
    assert session.device_id is not None


def test_live_summary_requires_finite_bounded_diagnostics_and_matching_device() -> None:
    values = {
        "source": SessionSource.LIVE_SENSOR,
        "sensor_placement": SensorPlacement.THIGH,
        "device_id": uuid4(),
        "sample_count": 30,
        "target_repetitions": 10,
        "completed_repetitions": 0,
        "movement_quality": MovementQuality.INSUFFICIENT_DATA,
        "stability": MovementQuality.INSUFFICIENT_DATA,
        "smoothness": MovementQuality.INSUFFICIENT_DATA,
        "fatigue_signal": FatigueSignal.INSUFFICIENT_DATA,
        "session_duration_seconds": 3,
        "successful_requests": 30,
        "failed_requests": 0,
        "invalid_samples": 0,
        "measured_rate_hz": 9.1,
        "average_latency_ms": 4.5,
    }
    summary = MovementSummaryCreate(**values)
    assert summary.successful_requests == 30

    with pytest.raises(ValidationError):
        MovementSummaryCreate(**{**values, "measured_rate_hz": nan})
    with pytest.raises(ValidationError):
        MovementSummaryCreate(**{**values, "failed_requests": -1})
    with pytest.raises(ValidationError, match="Only live sensor summaries"):
        MovementSummaryCreate(**{
            **values,
            "source": SessionSource.SIMULATION,
            "device_id": None,
            "successful_requests": 30,
            "measured_rate_hz": None,
            "average_latency_ms": None,
        })


def test_device_registration_is_idempotent_and_owner_scoped(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api.v1 import devices
    from app.api.v1.health import athlete_context
    from app.main import app

    owner_id = uuid4()
    other_owner_id = uuid4()
    active_owner = {"id": owner_id}
    stored: dict[tuple[str, str], dict] = {}

    class FakeRepository:
        def __init__(self, athlete_id):
            self.athlete_id = str(athlete_id)

        async def upsert(self, table, values, *, conflict):
            assert table == "movement_devices"
            assert conflict == "athlete_id,device_identifier"
            key = (self.athlete_id, values["device_identifier"])
            stored.setdefault(
                key,
                {
                    **values,
                    "athlete_id": self.athlete_id,
                    "id": str(uuid4()),
                    "last_seen_at": None,
                },
            )
            return stored[key]

        async def list_rows(self, _table, *, filters=None, **_kwargs):
            return [
                row
                for (athlete_id, _identifier), row in stored.items()
                if athlete_id == self.athlete_id
                and (not filters or row["id"] == filters.get("id", "").removeprefix("eq."))
            ]

        async def patch(self, _table, _device_id, values):
            record = next(
                (
                    row
                    for (athlete_id, _identifier), row in stored.items()
                    if athlete_id == self.athlete_id and row["id"] == str(_device_id)
                ),
                None,
            )
            if record is None:
                return None
            record.update(values)
            return record

    async def context_override():
        return active_owner["id"], None, None

    monkeypatch.setattr(devices, "_repository", lambda context: FakeRepository(context[0]))
    app.dependency_overrides[athlete_context] = context_override
    try:
        with TestClient(app) as client:
            payload = {"device_identifier": "ESP32-001"}
            first = client.post("/api/v1/devices", json=payload)
            second = client.post("/api/v1/devices", json=payload)

            assert first.status_code == 201
            assert second.status_code == 201
            device = first.json()["data"]["device"]
            assert device["id"] == second.json()["data"]["device"]["id"]
            assert device["ip"] == "192.168.4.1"
            assert len(stored) == 1

            active_owner["id"] = other_owner_id
            denied = client.get(f"/api/v1/devices/{device['id']}")
            assert denied.status_code == 404
    finally:
        app.dependency_overrides.pop(athlete_context, None)
