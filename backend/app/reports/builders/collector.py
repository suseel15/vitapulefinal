import hashlib
import json
from datetime import UTC, date, datetime, time
from typing import Any

from app.repositories.health_repository import HealthRepository
from app.reports.builders.common import tables_for_report
from app.reports.schemas import DataCompleteness, ReportRequest, ReportSection, ReportSource, ReportValue, SourceCategorySummary

_FEATURE_FILTER_COLUMNS = {"session_id", "program_id"}


async def collect_report_sources(
    repository: HealthRepository,
    request: ReportRequest,
) -> tuple[list[ReportSource], list[ReportSection], list[SourceCategorySummary], list[str], DataCompleteness]:
    sources: list[ReportSource] = []
    values_by_category: dict[str, list[ReportValue]] = {}
    table_counts: dict[str, dict[str, int]] = {}
    data_gaps: list[str] = []

    for table in tables_for_report(request.report_type):
        filters: dict[str, str] = {}
        date_constraints = []
        if request.date_range_start is not None:
            date_constraints.append(f"{table.timestamp_column}.gte.{request.date_range_start.isoformat()}")
        if request.date_range_end is not None:
            date_constraints.append(f"{table.timestamp_column}.lte.{request.date_range_end.isoformat()}")
        if date_constraints:
            filters["and"] = "(" + ",".join(date_constraints) + ")"
        if request.feature_id is not None:
            feature_column = next((field for field in _FEATURE_FILTER_COLUMNS if field in table.fields), None)
            if feature_column is not None:
                filters[feature_column] = f"eq.{request.feature_id}"
            elif "id" in table.fields:
                filters["id"] = f"eq.{request.feature_id}"
        if request.source_ids:
            filters[table.id_column] = "in.(" + ",".join(str(item) for item in request.source_ids) + ")"

        rows = await repository.list_rows(
            table.table,
            select="*",
            order=f"{table.timestamp_column}.desc",
            limit=100,
            filters=filters,
        )
        table_counts[table.table] = {"found": len(rows), "total": 1}
        for row in rows:
            timestamp = _timestamp(row.get(table.timestamp_column) or row.get("created_at"))
            record_id = row.get(table.id_column) or row.get("id")
            if timestamp is None or record_id is None:
                data_gaps.append(f"A {table.event_type or table.table} record is missing its source identifier or timestamp.")
                continue
            source_values = {
                field: _json_value(row[field])
                for field in table.fields
                if field in row and field not in {"id", "created_at"}
            }
            source_hash = hashlib.sha256(_canonical_json(source_values).encode("utf-8")).hexdigest()
            source_ref = f"SOURCE-{len(sources) + 1:03d}"
            source_type = table.source_type
            label = (table.event_type or table.table).replace("_", " ").title()
            source = ReportSource(
                source_type=source_type,
                source_id=source_ref,
                record_id=str(record_id),
                timestamp=timestamp,
                source_label=label,
                provenance=table.provenance,
                source_hash=source_hash,
                values=source_values,
            )
            sources.append(source)
            values_by_category.setdefault(source_type.value, []).extend(
                ReportValue(
                    label=field.replace("_", " ").title(),
                    value=_display_value(value),
                    source_ids=[source_ref],
                    provenance=table.provenance,
                )
                for field, value in source_values.items()
                if value is not None
            )

    categories = sorted({table.source_type.value for table in tables_for_report(request.report_type)})
    table_total = len(table_counts)
    table_found = sum(1 for count in table_counts.values() if count["found"] > 0)
    category_summaries: list[SourceCategorySummary] = []
    for category in categories:
        category_sources = [source for source in sources if source.source_type.value == category]
        category_tables = [table for table in tables_for_report(request.report_type) if table.source_type.value == category]
        category_tables_with_data = sum(
            1 for table in category_tables if table_counts.get(table.table, {}).get("found", 0) > 0
        )
        if not category_sources:
            completeness = DataCompleteness.NO_EVENTS if request.date_range_start or request.date_range_end else DataCompleteness.NO_DATA
            data_gaps.append(f"No {category.lower().replace('_', ' ')} records were found in the selected period.")
        elif category_tables_with_data == len(category_tables):
            completeness = DataCompleteness.COMPLETE
        else:
            completeness = DataCompleteness.PARTIAL
        category_summaries.append(
            SourceCategorySummary(
                source_type=category,
                source_count=len(category_sources),
                latest_timestamp=max((source.timestamp for source in category_sources), default=None),
                completeness=completeness,
            )
        )

    if not sources:
        overall = DataCompleteness.NO_EVENTS if request.date_range_start or request.date_range_end else DataCompleteness.NO_DATA
    elif table_found < table_total:
        overall = DataCompleteness.PARTIAL
    else:
        overall = DataCompleteness.COMPLETE

    sections = [
        ReportSection(category=category.source_type, title=category.source_type.value.replace("_", " ").title(), values=values_by_category.get(category.source_type.value, []))
        for category in category_summaries
    ]
    return sources, sections, category_summaries, data_gaps, overall


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.combine(date.fromisoformat(value), time.min, tzinfo=UTC)
            except ValueError:
                return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, dict)):
        return value
    return str(value)


def _display_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return _canonical_json(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
