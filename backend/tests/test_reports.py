from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from app.ai.safety import AIReportSafetyValidator, AIValidationError
from app.core.config import Settings
from app.reports.builders.collector import collect_report_sources
from app.reports.builders.common import tables_for_report
from app.reports.engine import ReportEngine
from app.repositories.health_repository import HealthRepository
from app.repositories.supabase import SupabaseRepository
from app.reports.renderers import render_html, render_pdf
from app.reports.schemas import (
    AIInterpretation,
    AIObservation,
    DataCompleteness,
    EvidenceStrength,
    LongitudinalInsight,
    ReportData,
    ReportProvenance,
    ReportRequest,
    ReportSource,
    ReportType,
    SourceType,
)
from app.reports.longitudinal import MINIMUM_PERIOD_RECORDS, build_longitudinal_insights

ATHLETE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
REPORT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class FakeSupabaseRepository(SupabaseRepository):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def rest(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
        prefer: str | None = None,
    ) -> Any:
        del method, payload, prefer
        self.calls.append((table, params))
        if table == "biomarker_measurements":
            return [
                {
                    "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "athlete_id": str(ATHLETE_ID),
                    "biomarker_name": "Marker <script>alert(1)</script>",
                    "value_numeric": 3.0,
                    "unit": "mg/L",
                    "source_page": 2,
                    "collection_date": "2026-02-02",
                    "created_at": "2026-02-03T10:00:00+00:00",
                }
            ]
        return []

def _interpretation(text: str = "The reported value is 3.") -> AIInterpretation:
    return AIInterpretation(
        summary=text,
        summary_source_ids=["SOURCE-001"],
        key_observations=[
            AIObservation(
                observation=text,
                source_ids=["SOURCE-001"],
                source_type=SourceType.HEALTH,
                evidence_strength=EvidenceStrength.DIRECT,
            )
        ],
        patterns=[],
        explanations=[],
        recommendations=[],
        limitations=[],
        follow_up=[],
    )


@pytest.mark.asyncio
async def test_collector_uses_owner_scoped_repository_and_source_whitelist() -> None:
    client = FakeSupabaseRepository()
    repository = HealthRepository(client, ATHLETE_ID)
    request = ReportRequest(reportType=ReportType.BIOMARKER_REPORT)
    request = request.model_copy(
        update={
            "date_range_start": datetime(2026, 2, 1, tzinfo=UTC),
            "date_range_end": datetime(2026, 2, 4, tzinfo=UTC),
        }
    )

    sources, sections, summaries, gaps, completeness = await collect_report_sources(repository, request)

    assert len(sources) == 1
    assert sources[0].source_id == "SOURCE-001"
    assert sources[0].record_id == "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    assert "athlete_id" not in sources[0].values
    assert "source_page" in sources[0].values
    assert sections[0].values[0].source_ids == ["SOURCE-001"]
    assert summaries[0].completeness is DataCompleteness.COMPLETE
    assert completeness is DataCompleteness.COMPLETE
    assert not gaps
    params = client.calls[0][1]
    assert params is not None
    assert params["athlete_id"] == f"eq.{ATHLETE_ID}"
    assert params["and"].startswith("(collection_date.gte.")


def test_ai_validator_requires_cited_source_values_and_rejects_diagnosis() -> None:
    from app.reports.schemas import ReportProvenance, ReportSource

    source = ReportSource(
        source_type=SourceType.HEALTH,
        source_id="SOURCE-001",
        record_id="record-1",
        timestamp=datetime(2026, 2, 3, tzinfo=UTC),
        source_label="Biomarker measurement",
        provenance=ReportProvenance.DIRECTLY_REPORTED,
        source_hash="a" * 64,
        values={"value_numeric": 3.0},
    )
    validator = AIReportSafetyValidator()
    assert validator.validate(_interpretation(), [source]).summary == "The reported value is 3."

    with pytest.raises(AIValidationError, match="number not supported"):
        validator.validate(_interpretation("The reported value is 4."), [source])
    with pytest.raises(AIValidationError, match="disallowed"):
        validator.validate(_interpretation("The athlete has a diagnosis."), [source])


@pytest.mark.asyncio
async def test_report_renderers_escape_untrusted_source_text_and_produce_pdf() -> None:
    client = FakeSupabaseRepository()
    repository = HealthRepository(client, ATHLETE_ID)
    request = ReportRequest(reportType=ReportType.BIOMARKER_REPORT)
    sources, sections, summaries, gaps, completeness = await collect_report_sources(repository, request)
    report = ReportData(
        report_id=REPORT_ID,
        athlete_id=ATHLETE_ID,
        requested_by=ATHLETE_ID,
        report_type=ReportType.BIOMARKER_REPORT,
        title="Biomarker report",
        sections=sections,
        sources=sources,
        source_categories=summaries,
        data_completeness=completeness,
        data_gaps=gaps,
        factual_summary="Found one source record.",
        limitations=["Recorded data only."],
    )

    html_output = render_html(report).decode("utf-8")
    pdf_output = render_pdf(report)

    assert "<script>" not in html_output
    assert "&lt;script&gt;" in html_output
    assert pdf_output.startswith(b"%PDF")


def test_report_request_requires_valid_email_and_pdf_for_delivery() -> None:
    with pytest.raises(ValueError):
        ReportRequest(reportType=ReportType.WEEKLY_HEALTH_REPORT, includeEmail=True, recipient="not-an-email")
    with pytest.raises(ValueError, match="PDF"):
        ReportRequest(
            reportType=ReportType.WEEKLY_HEALTH_REPORT,
            includeEmail=True,
            recipient="athlete@example.test",
            includePdf=False,
        )


def test_connectivity_reports_include_sync_heart_rate_and_activity_sources() -> None:
    tables = {table.table for table in tables_for_report(ReportType.CONNECTIVITY_REPORT)}
    assert tables == {
        "health_data_sync_runs",
        "unified_heart_rate_records",
        "unified_activity_records",
    }


def _trend_source(source_id: str, value: float, timestamp: datetime) -> ReportSource:
    return ReportSource(
        source_type=SourceType.WELLBEING,
        source_id=source_id,
        record_id=f"record-{source_id}",
        timestamp=timestamp,
        source_label="Wellbeing check-in",
        provenance=ReportProvenance.SELF_REPORTED,
        source_hash="a" * 64,
        values={"energy": value, "free_text": "private user text"},
    )


def test_longitudinal_calculation_requires_three_records_in_both_periods() -> None:
    current_period = datetime(2026, 2, 4, tzinfo=UTC)
    previous_period = datetime(2026, 1, 28, tzinfo=UTC)
    current = [_trend_source(f"current-{index}", 4.0 + index, current_period) for index in range(3)]
    previous = [_trend_source(f"previous-{index}", 2.0 + index, previous_period) for index in range(3)]

    derived, insights, limitations = build_longitudinal_insights(
        current,
        previous,
        current_period_end=current_period,
    )

    assert len(derived) == 1
    assert derived[0].source_id == "SOURCE-007"
    assert derived[0].values["current_average"] == 5.0
    assert derived[0].values["previous_average"] == 3.0
    assert insights[0].current_count == MINIMUM_PERIOD_RECORDS
    assert insights[0].previous_count == MINIMUM_PERIOD_RECORDS
    assert insights[0].source_ids == [derived[0].source_id]
    assert "private user text" not in str(derived[0].values)
    assert not limitations

    too_few, no_insights, limitations = build_longitudinal_insights(
        current[:2],
        previous,
        current_period_end=current_period,
    )
    assert not too_few
    assert not no_insights
    assert limitations


def test_longitudinal_sources_are_validated_and_rendered() -> None:
    current_period = datetime(2026, 2, 4, tzinfo=UTC)
    current = [_trend_source(f"current-{index}", 4.0 + index, current_period) for index in range(3)]
    previous = [
        _trend_source(f"previous-{index}", 2.0 + index, datetime(2026, 1, 28, tzinfo=UTC))
        for index in range(3)
    ]
    calculated, insights, _ = build_longitudinal_insights(
        current,
        previous,
        current_period_end=current_period,
    )
    insight = insights[0]
    report = ReportData(
        report_id=REPORT_ID,
        athlete_id=ATHLETE_ID,
        requested_by=ATHLETE_ID,
        report_type=ReportType.WEEKLY_ATHLETE_REPORT,
        title="Weekly athlete report",
        sections=[],
        sources=[*current, *previous, *calculated],
        longitudinal_insights=insights,
        source_categories=[],
        data_completeness=DataCompleteness.COMPLETE,
        data_gaps=[],
        factual_summary="Source-linked comparison.",
        limitations=[],
    )

    assert report.longitudinal_insights[0].source_ids == [calculated[0].source_id]
    assert insight.statement in render_html(report).decode("utf-8")
    assert render_pdf(report).startswith(b"%PDF")
    limited = report.model_copy(update={"limitations": ["Longitudinal intelligence is disabled."]})
    assert "Longitudinal intelligence is disabled." in render_html(limited).decode("utf-8")


@pytest.mark.asyncio
async def test_longitudinal_snapshot_and_timeline_persist_migration_fields() -> None:
    current_period = datetime(2026, 2, 4, tzinfo=UTC)
    current = [_trend_source(f"current-{index}", 4.0 + index, current_period) for index in range(3)]
    previous = [
        _trend_source(f"previous-{index}", 2.0 + index, datetime(2026, 1, 28, tzinfo=UTC))
        for index in range(3)
    ]
    calculated, insights, _ = build_longitudinal_insights(
        current,
        previous,
        current_period_end=current_period,
    )
    report = ReportData(
        report_id=REPORT_ID,
        athlete_id=ATHLETE_ID,
        requested_by=ATHLETE_ID,
        report_type=ReportType.WEEKLY_ATHLETE_REPORT,
        title="Weekly athlete report",
        date_range_start=datetime(2026, 1, 28, tzinfo=UTC),
        date_range_end=current_period,
        sections=[],
        sources=[*current, *previous, *calculated],
        longitudinal_insights=insights,
        source_categories=[],
        data_completeness=DataCompleteness.COMPLETE,
        data_gaps=[],
        factual_summary="Source-linked comparison.",
        limitations=[],
    )

    class PersistenceRepository(SupabaseRepository):
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, str] | None, Any, str | None]] = []

        async def rest(
            self,
            method: str,
            table: str,
            *,
            params: dict[str, str] | None = None,
            payload: Any = None,
            prefer: str | None = None,
        ) -> Any:
            self.calls.append((method, table, params, payload, prefer))
            if method == "GET" and table == "athlete_intelligence_snapshots":
                return []
            if method == "POST" and table == "athlete_intelligence_snapshots":
                return [{"id": "snapshot-id"}]
            return None

    repository = PersistenceRepository()
    engine = ReportEngine(Settings(), repository)
    await engine._save_sources(ATHLETE_ID, REPORT_ID, report.sources)
    await engine._save_intelligence_snapshot(report)

    timeline_calls = [call for call in repository.calls if call[1] == "athlete_timeline_events"]
    assert timeline_calls
    prior_timeline_row = next(call[3] for call in timeline_calls if "previous-0" in call[3]["source_id"])
    assert prior_timeline_row["title"] == "Wellbeing check-in"

    snapshot_insert = next(
        call[3] for call in repository.calls
        if call[0] == "POST" and call[1] == "athlete_intelligence_snapshots"
    )
    assert snapshot_insert["report_id"] == str(REPORT_ID)
    insight_upsert = next(
        call for call in repository.calls
        if call[0] == "POST" and call[1] == "athlete_intelligence_insights"
    )
    assert insight_upsert[3]["snapshot_id"] == "snapshot-id"
    assert insight_upsert[2] == {"on_conflict": "snapshot_id,insight_type,statement"}
