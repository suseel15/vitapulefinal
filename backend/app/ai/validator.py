from pydantic import ValidationError

from app.ai.safety import AIReportSafetyValidator
from app.reports.schemas import AIInterpretation, ReportSource


def validate_structured_output(value: object, sources: list[ReportSource]) -> AIInterpretation:
    parsed = AIInterpretation.model_validate(value)
    return AIReportSafetyValidator().validate(parsed, sources)


__all__ = ["ValidationError", "validate_structured_output"]
