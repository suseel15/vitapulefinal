import re
from datetime import date
from typing import Any
from uuid import UUID

from app.schemas.medical_report import ExtractedBiomarker, OCRResult, SourceType, StructuredReportExtraction

BIOMARKER_ALIASES = {
    "albumin": ("albumin",),
    "alanine aminotransferase": ("alanine aminotransferase", "alt"),
    "aspartate aminotransferase": ("aspartate aminotransferase", "ast"),
    "bilirubin": ("total bilirubin", "bilirubin"),
    "calcium": ("calcium",),
    "cholesterol": ("total cholesterol", "cholesterol"),
    "c-reactive protein": ("c-reactive protein", "crp"),
    "creatinine": ("creatinine",),
    "cortisol": ("cortisol",),
    "ferritin": ("ferritin",),
    "glucose": ("glucose",),
    "hemoglobin": ("hemoglobin", "haemoglobin", "hgb"),
    "hemoglobin a1c": ("hemoglobin a1c", "haemoglobin a1c", "hba1c", "a1c"),
    "hematocrit": ("hematocrit", "haematocrit", "hct"),
    "high-density lipoprotein cholesterol": ("high-density lipoprotein", "hdl cholesterol", "hdl"),
    "low-density lipoprotein cholesterol": ("low-density lipoprotein", "ldl cholesterol", "ldl"),
    "platelet count": ("platelet count", "platelets"),
    "potassium": ("potassium",),
    "red blood cell count": ("red blood cell count", "rbc"),
    "sodium": ("sodium",),
    "thyroid-stimulating hormone": ("thyroid-stimulating hormone", "thyroid stimulating hormone", "tsh"),
    "triglycerides": ("triglycerides", "triglyceride"),
    "vitamin b12": ("vitamin b12", "b12"),
    "vitamin d": ("25-hydroxy vitamin d", "25 hydroxy vitamin d", "vitamin d"),
    "white blood cell count": ("white blood cell count", "wbc"),
}
_ALIAS_LOOKUP = sorted(
    ((alias, canonical) for canonical, aliases in BIOMARKER_ALIASES.items() for alias in aliases),
    key=lambda item: len(item[0]),
    reverse=True,
)
_NUMBER = r"[<>≤≥]?\s*-?\d+(?:[.,]\d+)?"
_VALUE_PREFIX = re.compile(rf"^\s*(?P<value>{_NUMBER})(?P<rest>.*)$")
_RANGE = re.compile(
    rf"(?P<low>-?\d+(?:[.,]\d+)?)\s*(?:-|–|—|\bto\b)\s*(?P<high>-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_ABNORMAL = re.compile(r"(?<![A-Za-z])(HIGH|LOW|ABNORMAL|H|L)(?![A-Za-z])", re.IGNORECASE)
_DATE = re.compile(r"\b(?:20\d{2})[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b")
_NUMBER_TOKEN = re.compile(_NUMBER)


def _numeric(value: str) -> float | None:
    normalized = value.replace(",", ".").replace(" ", "")
    if normalized.startswith(("<", ">", "≤", "≥")):
        normalized = normalized[1:]
    try:
        return float(normalized)
    except ValueError:
        return None


def _extract_line(line: str, page_number: int) -> ExtractedBiomarker | None:
    normalized_line = " ".join(line.split())
    for alias, canonical in _ALIAS_LOOKUP:
        match = re.match(
            rf"^\s*{re.escape(alias)}(?:\s*[:=]\s*|\s+)(?P<tail>.+?)\s*$",
            normalized_line,
            re.IGNORECASE,
        )
        if not match:
            continue
        tail = match.group("tail")
        value_match = _VALUE_PREFIX.match(tail)
        if not value_match:
            return None
        value_raw = value_match.group("value")
        value = _numeric(value_raw)
        if value is None:
            return None
        remainder = value_match.group("rest").strip()
        range_match = _RANGE.search(remainder)
        reference_low = _numeric(range_match.group("low")) if range_match else None
        reference_high = _numeric(range_match.group("high")) if range_match else None
        abnormal_match = _ABNORMAL.search(remainder)
        abnormal_flag = None
        if abnormal_match:
            flag = abnormal_match.group(1).upper()
            abnormal_flag = {"H": "HIGH", "L": "LOW"}.get(flag, flag)
        unit_text = _NUMBER_TOKEN.sub(" ", remainder, count=2).strip()
        unit_match = re.match(r"^([A-Za-zµμ%/]+(?:[0-9]+)?(?:/[A-Za-zµμ0-9]+)*)", unit_text)
        unit = unit_match.group(1) if unit_match else None
        return ExtractedBiomarker(
            biomarker_name=alias.title(),
            canonical_name=canonical,
            standard_code=None,
            value_numeric=value,
            unit=unit,
            reference_low=reference_low,
            reference_high=reference_high,
            abnormal_flag=abnormal_flag,
            source_type=SourceType.DIRECTLY_REPORTED,
            source_text=normalized_line[:1000],
            source_page=page_number,
            extraction_method="CONSERVATIVE_TEXT_PATTERN",
            confidence=None,
        )
    return None


def extract_structured_report(ocr_result: OCRResult) -> StructuredReportExtraction:
    biomarkers: list[ExtractedBiomarker] = []
    source_pages = []
    seen: set[tuple[int, str, float]] = set()
    for page in ocr_result.pages:
        source_pages.append(page.page_number)
        for line in page.text.splitlines():
            extracted = _extract_line(line, page.page_number)
            if not extracted or extracted.value_numeric is None:
                continue
            duplicate_key = (page.page_number, extracted.canonical_name or "", extracted.value_numeric)
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)
            biomarkers.append(extracted)

    report_date = None
    for page in ocr_result.pages:
        match = _DATE.search(page.text)
        if match:
            try:
                report_date = date.fromisoformat(match.group().replace("/", "-"))
                break
            except ValueError:
                continue
    return StructuredReportExtraction(
        report_date=report_date,
        biomarkers=biomarkers,
        source_pages=source_pages,
    )


def to_measurement_rows(
    extraction: StructuredReportExtraction,
    athlete_id: UUID,
    medical_report_id: UUID,
) -> list[dict[str, Any]]:
    return [
        {
            "athlete_id": str(athlete_id),
            "medical_report_id": str(medical_report_id),
            "biomarker_name": item.biomarker_name,
            "canonical_name": item.canonical_name,
            "standard_code": item.standard_code,
            "value_numeric": item.value_numeric,
            "value_text": item.value_text,
            "unit": item.unit,
            "reference_low": item.reference_low,
            "reference_high": item.reference_high,
            "abnormal_flag": item.abnormal_flag,
            "collection_date": extraction.report_date.isoformat() if extraction.report_date else None,
            "source_page": item.source_page,
            "source_text": item.source_text,
            "source_type": item.source_type.value,
            "extraction_method": item.extraction_method,
            "confidence": item.confidence,
        }
        for item in extraction.biomarkers
    ]
