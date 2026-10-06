from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceSource(BaseModel):
    id: UUID
    source_title: str
    source_type: str
    source_identifier: str | None = None
    source_url: str | None = None
    retrieved_at: datetime | None = None
    relevance: str | None = None
    claim_supported: str | None = None


class HealthIntelligenceItem(BaseModel):
    id: UUID
    athlete_id: UUID
    item_type: str
    category: str
    title: str
    explanation: str
    status: str
    source_ids: list[UUID] = Field(default_factory=list)
    observed_at: date | None = None
    created_at: datetime


class HealthAnalysisAIRequest(BaseModel):
    athlete_id: UUID
    validated_biomarkers: list[dict[str, object]] = Field(default_factory=list)
    longitudinal_trends: list[dict[str, object]] = Field(default_factory=list)
    structured_findings: list[dict[str, object]] = Field(default_factory=list)
    source_evidence: list[EvidenceSource] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)


class HealthAnalysisAIResponse(BaseModel):
    observed_values_unchanged: bool
    interpretations: list[dict[str, object]] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    professional_review_recommended: bool = True
