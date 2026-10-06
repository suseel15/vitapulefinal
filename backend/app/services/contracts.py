from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class MovementStatus:
    connected: bool
    device_name: str | None
    checked_at: datetime


@dataclass(frozen=True)
class MovementSample:
    timestamp: int
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    source: str


class MovementDataSource(Protocol):
    async def samples(
        self,
        *,
        duration_seconds: float,
        sample_rate_hz: float,
    ) -> AsyncIterator[MovementSample]: ...


class HttpPollingMovementDataSource(Protocol):
    base_url: str
    status_path: str
    data_path: str


class WebSocketMovementDataSource(Protocol):
    endpoint: str


@dataclass(frozen=True)
class ReportRequest:
    subject_id: UUID
    report_type: str
    requested_by: UUID


@dataclass(frozen=True)
class ReportResult:
    report_id: UUID
    status: str
    created_at: datetime


class ReportGenerator(Protocol):
    async def generate(self, request: ReportRequest) -> ReportResult: ...


@dataclass(frozen=True)
class AIRequest:
    task: str
    structured_input: dict[str, object]


@dataclass(frozen=True)
class AIResult:
    content: dict[str, object]
    provider: str


class AIProvider(Protocol):
    async def generate(self, request: AIRequest) -> AIResult: ...


class CameraAssessmentProvider(Protocol):
    async def assess(self, athlete_id: UUID, consent_id: UUID) -> dict[str, object]: ...


class SleepProvider(Protocol):
    async def latest_sleep(self, athlete_id: UUID) -> dict[str, object] | None: ...


class RecoveryProvider(Protocol):
    async def recovery_context(self, athlete_id: UUID) -> dict[str, object]: ...


class WearableProvider(Protocol):
    async def wearable_status(self, athlete_id: UUID) -> MovementStatus: ...


class AthleteHealthContextProvider(Protocol):
    async def rehab_restrictions(self, athlete_id: UUID) -> list[dict[str, object]]: ...


class RehabSafetyEventSink(Protocol):
    async def record_warning(self, athlete_id: UUID, session_id: UUID, event: dict[str, object]) -> None: ...


class RehabSafetyMonitor(Protocol):
    def evaluate(self, sample: MovementSample) -> str: ...


@dataclass(frozen=True)
class RehabSessionReportData:
    session_id: UUID
    athlete_id: UUID
    source: str
    summary: dict[str, object]


@dataclass(frozen=True)
class MovementAnalysisReportData:
    athlete_id: UUID
    session_ids: tuple[UUID, ...]
    signals: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class ProgressReportData:
    athlete_id: UUID
    program_id: UUID | None
    progress: dict[str, object]


@dataclass(frozen=True)
class FunctionalTestReportData:
    athlete_id: UUID
    result_id: UUID
    result: dict[str, object]


@dataclass(frozen=True)
class ReadinessReportData:
    athlete_id: UUID
    assessment_id: UUID
    assessment: dict[str, object]


@dataclass(frozen=True)
class ReturnToSportReportData:
    athlete_id: UUID
    assessment_id: UUID
    assessment: dict[str, object]
