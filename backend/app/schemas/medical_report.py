from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProcessingStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    OCR_PROCESSING = "OCR_PROCESSING"
    EXTRACTING = "EXTRACTING"
    VALIDATING_DATA = "VALIDATING_DATA"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SourceType(StrEnum):
    DIRECTLY_REPORTED = "DIRECTLY_REPORTED"
    CALCULATED = "CALCULATED"
    AI_INTERPRETED = "AI_INTERPRETED"
    USER_ENTERED = "USER_ENTERED"


class OCRQuality(StrEnum):
    GOOD = "GOOD"
    LOW_QUALITY = "LOW_QUALITY"
    TEXT_LAYER = "TEXT_LAYER"


class PageText(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class OCRResult(BaseModel):
    pages: list[PageText]
    ocr_engine: str
    ocr_version: str
    pages_processed: int = Field(ge=0)
    text_length: int = Field(ge=0)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    quality: OCRQuality


class ExtractedBiomarker(BaseModel):
    biomarker_name: str = Field(min_length=1, max_length=120)
    canonical_name: str | None = Field(default=None, max_length=120)
    standard_code: str | None = Field(default=None, max_length=64)
    value_numeric: float | None = None
    value_text: str | None = Field(default=None, max_length=250)
    unit: str | None = Field(default=None, max_length=40)
    reference_low: float | None = None
    reference_high: float | None = None
    abnormal_flag: str | None = Field(default=None, pattern="^(HIGH|LOW|ABNORMAL)$")
    source_type: SourceType = SourceType.DIRECTLY_REPORTED
    source_text: str = Field(min_length=1, max_length=1000)
    source_page: int = Field(ge=1)
    extraction_method: str = Field(min_length=1, max_length=64)
    confidence: float | None = Field(default=None, ge=0, le=1)


class StructuredReportExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = None
    report_date: date | None = None
    laboratory: str | None = None
    biomarkers: list[ExtractedBiomarker] = Field(default_factory=list)
    findings: list[dict[str, object]] = Field(default_factory=list)
    medications: list[dict[str, object]] = Field(default_factory=list)
    diagnoses_mentioned: list[dict[str, object]] = Field(default_factory=list)
    reference_ranges: list[dict[str, object]] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)


class ReportStatusResponse(BaseModel):
    id: UUID
    processing_status: ProcessingStatus
    ocr_status: str
    extraction_status: str
    analysis_status: str
    ocr_quality: OCRQuality | None = None
    error_code: str | None = None
    uploaded_at: datetime
    processed_at: datetime | None = None


class MedicalReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    athlete_id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    consent_purpose: str
    consented_at: datetime
    report_date: date | None = None
    uploaded_at: datetime
    processed_at: datetime | None = None
    processing_status: ProcessingStatus
    ocr_status: str
    extraction_status: str
    analysis_status: str
    ocr_engine: str | None = None
    ocr_version: str | None = None
    ocr_confidence: float | None = None
    pages_processed: int | None = None
    text_length: int | None = None
    data_quality_warnings: list[str] = Field(default_factory=list)
    biomarkers: list[ExtractedBiomarker] = Field(default_factory=list)
    error_code: str | None = None
