from dataclasses import dataclass

from app.reports.schemas import ReportProvenance, ReportType, SourceType


@dataclass(frozen=True)
class SourceTable:
    table: str
    source_type: SourceType
    timestamp_column: str
    id_column: str = "id"
    provenance: ReportProvenance = ReportProvenance.DIRECTLY_REPORTED
    fields: tuple[str, ...] = ("id", "created_at", "source", "status", "result")
    event_type: str | None = None


def tables_for_report(report_type: ReportType) -> tuple[SourceTable, ...]:
    from app.reports.builders.anti_doping import ANTI_DOPING_TABLES
    from app.reports.builders.athlete_summary import ATHLETE_SUMMARY_TABLES
    from app.reports.builders.health import HEALTH_TABLES
    from app.reports.builders.medication import MEDICATION_TABLES
    from app.reports.builders.movement import MOVEMENT_TABLES
    from app.reports.builders.nutrition import NUTRITION_TABLES
    from app.reports.builders.recovery import RECOVERY_TABLES
    from app.reports.builders.rehab import REHAB_TABLES
    from app.reports.builders.safety import SAFETY_TABLES
    from app.reports.builders.skin_screening import SKIN_SCREENING_TABLES
    from app.reports.builders.wellbeing import WELLBEING_TABLES

    by_type = {
        ReportType.MEDICAL_REPORT_ANALYSIS: HEALTH_TABLES[:1],
        ReportType.BIOMARKER_REPORT: HEALTH_TABLES[1:2],
        ReportType.BODY_MAP_REPORT: HEALTH_TABLES[2:3],
        ReportType.HEALTH_INTELLIGENCE_REPORT: HEALTH_TABLES[3:4],
        ReportType.REHAB_SESSION_REPORT: REHAB_TABLES[:1],
        ReportType.MOVEMENT_ANALYSIS_REPORT: MOVEMENT_TABLES,
        ReportType.EXERCISE_PROGRESS_REPORT: REHAB_TABLES[1:2],
        ReportType.FUNCTIONAL_TEST_REPORT: REHAB_TABLES[2:3],
        ReportType.READINESS_REPORT: REHAB_TABLES[3:4],
        ReportType.RETURN_TO_SPORT_REPORT: REHAB_TABLES[4:5],
        ReportType.WELLBEING_CHECKIN_REPORT: WELLBEING_TABLES[:1],
        ReportType.CAMERA_WELLBEING_REPORT: WELLBEING_TABLES[1:2],
        ReportType.SLEEP_REPORT: WELLBEING_TABLES[2:3],
        ReportType.RECOVERY_REPORT: RECOVERY_TABLES,
        ReportType.CONNECTIVITY_REPORT: (
            ATHLETE_SUMMARY_TABLES[0],
            *ATHLETE_SUMMARY_TABLES[1:3],
        ),
        ReportType.NUTRITION_REPORT: NUTRITION_TABLES,
        ReportType.MEDICATION_REPORT: MEDICATION_TABLES,
        ReportType.ANTI_DOPING_REPORT: ANTI_DOPING_TABLES,
        ReportType.SKIN_SCREENING_REPORT: SKIN_SCREENING_TABLES,
        ReportType.SAFETY_INCIDENT_REPORT: SAFETY_TABLES,
        ReportType.WEEKLY_HEALTH_REPORT: HEALTH_TABLES,
        ReportType.WEEKLY_REHAB_REPORT: (*REHAB_TABLES, *MOVEMENT_TABLES),
        ReportType.WEEKLY_WELLBEING_REPORT: WELLBEING_TABLES,
        ReportType.WEEKLY_ATHLETE_REPORT: ATHLETE_SUMMARY_TABLES,
        ReportType.MONTHLY_HEALTH_REPORT: HEALTH_TABLES,
        ReportType.MONTHLY_REHAB_REPORT: (*REHAB_TABLES, *MOVEMENT_TABLES),
        ReportType.MONTHLY_ATHLETE_REPORT: ATHLETE_SUMMARY_TABLES,
        ReportType.DOCTOR_ATHLETE_REPORT: ATHLETE_SUMMARY_TABLES,
        ReportType.FULL_ATHLETE_REPORT: ATHLETE_SUMMARY_TABLES,
    }
    return by_type[report_type]
