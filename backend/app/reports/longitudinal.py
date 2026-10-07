import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.reports.schemas import (
    EvidenceStrength,
    LongitudinalInsight,
    ReportProvenance,
    ReportSource,
    SourceType,
)

MINIMUM_PERIOD_RECORDS = 3
_SAFE_METRIC_NAME = re.compile(r"^[A-Z0-9][A-Z0-9 _-]{0,63}$")
_TREND_FIELDS = {
    "energy": "Self-reported energy",
    "stress": "Self-reported stress",
    "fatigue": "Self-reported fatigue",
    "soreness": "Self-reported soreness",
    "recovery_feeling": "Self-reported recovery feeling",
    "mood_self_report": "Self-reported mood",
    "duration_minutes": "Recorded sleep duration (minutes)",
    "average_bpm": "Recorded average heart rate (bpm)",
    "count": "Recorded activity count",
    "value_numeric": "Biomarker measurement",
    "metric_value": "Recorded metric",
    "calories": "User-entered calories",
    "protein_g": "User-entered protein (g)",
    "carbohydrates_g": "User-entered carbohydrates (g)",
    "fat_g": "User-entered fat (g)",
    "fiber_g": "User-entered fiber (g)",
    "hydration_ml": "User-entered hydration (ml)",
    "completed_repetitions": "Completed repetitions",
    "session_duration_seconds": "Rehabilitation duration (seconds)",
    "completion_rate": "Session completion rate",
    "head_movement_magnitude": "Camera-observed head movement magnitude",
    "head_movement_variability": "Camera-observed head movement variability",
    "head_orientation_range": "Camera-observed head orientation range",
}


def build_longitudinal_insights(
    current_sources: list[ReportSource],
    previous_sources: list[ReportSource],
    *,
    current_period_end: datetime,
) -> tuple[list[ReportSource], list[LongitudinalInsight], list[str]]:
    current = _group_metrics(current_sources)
    previous = _group_metrics(previous_sources)
    insights: list[LongitudinalInsight] = []
    calculated_sources: list[ReportSource] = []
    limitations: list[str] = []

    for key, current_points in current.items():
        previous_points = previous.get(key, [])
        if len(current_points) < MINIMUM_PERIOD_RECORDS or len(previous_points) < MINIMUM_PERIOD_RECORDS:
            continue
        metric_label, source_type, unit = key
        current_average = _mean(value for value, _ in current_points)
        previous_average = _mean(value for value, _ in previous_points)
        delta = current_average - previous_average
        relative_delta = abs(delta) / max(abs(previous_average), 1e-9)
        direction = "INCREASED" if delta > 0 else "DECREASED" if delta < 0 else "UNCHANGED"
        if relative_delta < 0.05:
            direction = "STABLE"

        metric = f"{metric_label}{f' ({unit})' if unit else ''}"
        summary = {
            "metric": metric,
            "current_average": round(current_average, 3),
            "previous_average": round(previous_average, 3),
            "current_count": len(current_points),
            "previous_count": len(previous_points),
            "direction": direction,
        }
        source_ref = f"SOURCE-{len(current_sources) + len(previous_sources) + len(calculated_sources) + 1:03d}"
        source_hash = hashlib.sha256(_canonical_json(summary).encode("utf-8")).hexdigest()
        calculated = ReportSource(
            source_type=source_type,
            source_id=source_ref,
            record_id=f"derived:{metric_label}:{unit or 'unitless'}",
            timestamp=current_period_end,
            source_label="Deterministic longitudinal comparison",
            provenance=ReportProvenance.CALCULATED,
            source_hash=source_hash,
            values=summary,
        )
        calculated_sources.append(calculated)
        insights.append(
            LongitudinalInsight(
                metric=metric,
                source_type=source_type,
                current_average=summary["current_average"],
                previous_average=summary["previous_average"],
                current_count=len(current_points),
                previous_count=len(previous_points),
                direction=direction,
                statement=(
                    f"Recorded average {metric.lower()} was {summary['current_average']} in the selected period "
                    f"and {summary['previous_average']} in the previous period "
                    f"({len(current_points)} and {len(previous_points)} records)."
                ),
                source_ids=[source_ref],
                evidence_strength=EvidenceStrength.SUPPORTED,
            )
        )

    if not insights:
        limitations.append(
            f"Longitudinal comparisons require at least {MINIMUM_PERIOD_RECORDS} numeric records "
            "for the same measure in both periods; no comparison met that threshold."
        )
    return calculated_sources, insights, limitations


def _group_metrics(
    sources: list[ReportSource],
) -> dict[tuple[str, SourceType, str], list[tuple[float, str]]]:
    metrics: dict[tuple[str, SourceType, str], list[tuple[float, str]]] = defaultdict(list)
    for source in sources:
        for field, label in _TREND_FIELDS.items():
            value = source.values.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            name = label
            if field == "value_numeric":
                candidate = str(source.values.get("canonical_name") or source.values.get("biomarker_name") or "").strip().upper()
                if not _SAFE_METRIC_NAME.fullmatch(candidate):
                    continue
                name = f"Biomarker {candidate}"
            unit = str(source.values.get("unit") or "")
            metrics[(name, source.source_type, unit)].append((float(value), source.source_id))
    return metrics


def _mean(values: Any) -> float:
    sequence = list(values)
    return math.fsum(sequence) / len(sequence)


def _canonical_json(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
