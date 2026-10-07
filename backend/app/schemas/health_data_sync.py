from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class HealthDataModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class HealthDataType(StrEnum):
    SLEEP = "SLEEP"
    HEART_RATE = "HEART_RATE"
    STEPS = "STEPS"
    EXERCISE = "EXERCISE"
    OXYGEN_SATURATION = "OXYGEN_SATURATION"


class HealthDataSource(StrEnum):
    HEALTH_CONNECT = "HEALTH_CONNECT"


class HealthSyncStatus(StrEnum):
    SYNCED = "SYNCED"
    PARTIAL = "PARTIAL"
    NO_DATA = "NO_DATA"
    FAILED = "FAILED"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"


class HealthDataRecordCreate(HealthDataModel):
    data_type: HealthDataType
    source_record_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._:-]+$")
    source_application: str = Field(min_length=1, max_length=200)
    start_time: datetime
    end_time: datetime
    last_modified_at: datetime | None = None
    value: dict[str, Any] = Field(max_length=30)

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Health record timestamps must include a timezone.")
        return value

    @field_validator("last_modified_at")
    @classmethod
    def require_timezone_when_present(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Health record modification timestamps must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_range_and_value(self) -> "HealthDataRecordCreate":
        if self.start_time > self.end_time:
            raise ValueError("Health record start_time must not be after end_time.")
        if self.end_time > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Health record timestamps cannot be in the future.")
        value = self.value
        if self.data_type == HealthDataType.SLEEP:
            _only_keys(value, {"duration_minutes"})
            _bounded_number(value, "duration_minutes", 1, 1440, integer=True)
        elif self.data_type == HealthDataType.HEART_RATE:
            _only_keys(value, {"average_bpm", "sample_count", "measurement_type"})
            _bounded_number(value, "average_bpm", 25, 250)
            _bounded_number(value, "sample_count", 1, 1_000_000, integer=True)
            measurement_type = value.get("measurement_type", "UNKNOWN")
            if measurement_type not in {"RESTING", "WORKOUT", "GENERAL", "UNKNOWN"}:
                raise ValueError("Heart-rate measurement_type is invalid.")
        elif self.data_type == HealthDataType.STEPS:
            _only_keys(value, {"count"})
            _bounded_number(value, "count", 0, 10_000_000, integer=True)
        elif self.data_type == HealthDataType.EXERCISE:
            _only_keys(value, {"exercise_type", "duration_minutes", "title"})
            _bounded_number(value, "exercise_type", 0, 10_000, integer=True)
            _bounded_number(value, "duration_minutes", 1, 1440, integer=True)
            title = value.get("title")
            if title is not None and (not isinstance(title, str) or len(title) > 120):
                raise ValueError("Exercise title must be a string no longer than 120 characters.")
        elif self.data_type == HealthDataType.OXYGEN_SATURATION:
            _only_keys(value, {"percentage"})
            _bounded_number(value, "percentage", 0, 100)
        return self


class HealthSyncRunCreate(HealthDataModel):
    id: UUID | None = None
    source: HealthDataSource = HealthDataSource.HEALTH_CONNECT
    started_at: datetime
    completed_at: datetime
    status: HealthSyncStatus
    records_found: int = Field(ge=0, le=100_000)
    records_imported: int = Field(ge=0, le=100_000)
    records_skipped: int = Field(ge=0, le=100_000)
    records_failed: int = Field(ge=0, le=100_000)
    error_code: str | None = Field(default=None, max_length=80)
    data_types: list[HealthDataType] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_times(self) -> "HealthSyncRunCreate":
        for value in (self.started_at, self.completed_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Sync timestamps must include a timezone.")
        if self.completed_at < self.started_at:
            raise ValueError("Sync completion cannot precede its start.")
        if len(set(self.data_types)) != len(self.data_types):
            raise ValueError("Sync run data_types must not contain duplicates.")
        return self


class HealthConnectSyncRequest(HealthDataModel):
    sources: list[HealthDataSource] = Field(min_length=1, max_length=1)
    data_types: list[HealthDataType] = Field(min_length=1, max_length=5)
    from_time: datetime = Field(alias="from")
    to_time: datetime = Field(alias="to")
    records: list[HealthDataRecordCreate] = Field(default_factory=list, max_length=500)
    sync_run: "HealthSyncRunCreate | None" = None

    @model_validator(mode="after")
    def validate_sync_window(self) -> "HealthConnectSyncRequest":
        if (
            self.from_time.tzinfo is None
            or self.from_time.utcoffset() is None
            or self.to_time.tzinfo is None
            or self.to_time.utcoffset() is None
        ):
            raise ValueError("Sync range timestamps must include a timezone.")
        if self.from_time >= self.to_time:
            raise ValueError("Sync range must be increasing.")
        if self.to_time - self.from_time > timedelta(days=30):
            raise ValueError("Health Connect sync ranges are limited to 30 days.")
        if self.to_time > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Health Connect sync range cannot end in the future.")
        if len(set(self.data_types)) != len(self.data_types):
            raise ValueError("Sync data_types must not contain duplicates.")
        if self.sync_run and set(self.sync_run.data_types) != set(self.data_types):
            raise ValueError("Sync run data_types must match the requested data_types.")
        if any(record.data_type not in self.data_types for record in self.records):
            raise ValueError("Every record type must be included in data_types.")
        if any(record.start_time < self.from_time or record.end_time > self.to_time for record in self.records):
            raise ValueError("Health records must fit within the requested sync range.")
        return self


def _bounded_number(
    value: dict[str, Any],
    key: str,
    minimum: int | float,
    maximum: int | float,
    *,
    integer: bool = False,
) -> int | float:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise ValueError(f"{key} must be numeric.")
    if integer and not isinstance(item, int):
        raise ValueError(f"{key} must be an integer.")
    if not isfinite(item) or item < minimum or item > maximum:
        raise ValueError(f"{key} is outside the supported range.")
    return item


def _only_keys(value: dict[str, Any], allowed: set[str]) -> None:
    unexpected = value.keys() - allowed
    if unexpected:
        raise ValueError(f"Unexpected health record value fields: {', '.join(sorted(unexpected))}.")


class HealthConnectPermissionCreate(HealthDataModel):
    data_type: HealthDataType
    permission_state: str = Field(pattern="^(GRANTED|DENIED|REVOKED)$")
    checked_at: datetime

    @field_validator("checked_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Permission timestamps must include a timezone.")
        return value


class ConnectedDeviceCreate(HealthDataModel):
    device_type: str = Field(min_length=1, max_length=40)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=120)
    identifier: str = Field(min_length=1, max_length=120)
    connection_type: str = Field(min_length=1, max_length=40)
    status: str = Field(pattern="^(CONNECTED|DISCONNECTED|REGISTERED|UNAVAILABLE)$")
