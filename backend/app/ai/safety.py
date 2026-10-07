import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.reports.schemas import AIInterpretation, ReportSource

_UNSAFE_CLAIM_PATTERNS = (
    re.compile(r"\b(?:diagnos(?:e|ed|is)|suffers from|confirmed to have|likely has)\b", re.I),
    re.compile(r"\b(?:medically cleared|cleared to return|return-to-sport clearance|guaranteed to|will definitely recover)\b", re.I),
    re.compile(r"\b(?:emergency|life[- ]threatening)\b", re.I),
    re.compile(r"\b(?:start|stop|increase|decrease|change|discontinue|take)\s+(?:taking\s+)?(?:the\s+)?(?:medication|medicine|drug|dose|treatment)\b", re.I),
    re.compile(r"\b(?:caused by|proves that|definitely caused|because of|results from)\b", re.I),
    re.compile(r"\b(?:has|shows|indicates)\s+(?:major\s+)?(?:depression|anxiety|psychiatric disorder|concussion|fracture|tear|injury)\b", re.I),
)
_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?\s*%?")
_IGNORED_NUMERIC_FIELDS = ("_id", "date", "time", "page", "version")
_OPPOSITE_STATUS = {
    "LOW": ("HIGH",),
    "HIGH": ("LOW",),
    "GOOD": ("NEEDS ATTENTION", "NEEDS_ATTENTION"),
    "NEEDS_ATTENTION": ("GOOD",),
    "READY": ("NOT READY", "REST RECOMMENDED"),
    "REST_RECOMMENDED": ("READY",),
}


class AIValidationError(ValueError):
    """Raised when generated interpretation is not source-grounded or safe."""


class AIReportSafetyValidator:
    def validate(self, interpretation: AIInterpretation, sources: list[ReportSource]) -> AIInterpretation:
        sources_by_id = {source.source_id: source for source in sources}
        output = interpretation.model_dump(mode="python")
        self._validate_references(output["summary_source_ids"], None, sources_by_id)
        self._validate_text(output["summary"], output["summary_source_ids"], sources_by_id)
        for field in ("key_observations", "patterns", "explanations"):
            for item in output[field]:
                self._validate_references(item["source_ids"], item["source_type"], sources_by_id)
                self._validate_text(item["observation"], item["source_ids"], sources_by_id)
                item["evidence_strength"] = _evidence_strength(item["source_ids"], sources_by_id)
        for item in output["recommendations"]:
            self._validate_references(item["source_ids"], None, sources_by_id)
            self._validate_text(item["recommendation"], item["source_ids"], sources_by_id)
            self._validate_text(item["reason"], item["source_ids"], sources_by_id)
        for item in [*output["limitations"], *output["follow_up"]]:
            self._validate_text(item, [], sources_by_id)
        return AIInterpretation.model_validate(output)

    @staticmethod
    def _validate_references(
        references: list[str],
        source_type: str | None,
        sources_by_id: dict[str, ReportSource],
    ) -> None:
        if not references or any(reference not in sources_by_id for reference in references):
            raise AIValidationError("AI output referenced an unknown or missing source.")
        if source_type is not None and any(sources_by_id[reference].source_type.value != source_type for reference in references):
            raise AIValidationError("AI output assigned a source to the wrong category.")

    @staticmethod
    def _validate_text(
        text: str,
        references: list[str],
        sources_by_id: dict[str, ReportSource],
    ) -> None:
        if any(pattern.search(text) for pattern in _UNSAFE_CLAIM_PATTERNS):
            raise AIValidationError("AI output contained a disallowed medical or safety claim.")
        cited_sources = [sources_by_id[source_id] for source_id in references]
        numeric_evidence = {
            _canonical_number(str(value))
            for source in cited_sources
            for key, value in source.values.items()
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and not any(part in key.lower() for part in _IGNORED_NUMERIC_FIELDS)
        }
        for match in _NUMBER.finditer(text):
            if _canonical_number(match.group()) not in numeric_evidence:
                raise AIValidationError("AI output contained a number not supported by the report sources.")
        text_lower = text.lower()
        for source in cited_sources:
            for key, value in source.values.items():
                if not isinstance(value, str):
                    continue
                normalized_value = value.upper().replace(" ", "_")
                for opposite in _OPPOSITE_STATUS.get(normalized_value, ()):
                    opposite_words = opposite.lower().replace("_", " ")
                    field_words = key.lower().replace("_", " ")
                    if field_words in text_lower and re.search(rf"\b{re.escape(opposite_words)}\b", text_lower):
                        raise AIValidationError("AI output contradicted a cited source value.")


def _canonical_number(value: str) -> str:
    normalized = value.strip().rstrip("%").replace(",", ".")
    try:
        return str(Decimal(normalized).normalize())
    except InvalidOperation:
        return normalized


def _evidence_strength(source_ids: list[str], sources_by_id: dict[str, ReportSource]) -> str:
    if len(source_ids) >= 2:
        return "SUPPORTED"
    source = sources_by_id[source_ids[0]]
    if source.provenance.value in {"SIMULATION", "MODEL_INFERRED", "AI_INTERPRETED"}:
        return "LIMITED"
    return "DIRECT"
