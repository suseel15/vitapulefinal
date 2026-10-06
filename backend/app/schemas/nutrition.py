from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class NutritionGoal(StrEnum):
    RECOVERY = "RECOVERY"
    PERFORMANCE = "PERFORMANCE"
    STRENGTH = "STRENGTH"
    ENDURANCE = "ENDURANCE"
    BODY_COMPOSITION = "BODY_COMPOSITION"
    GENERAL_SPORTS_NUTRITION = "GENERAL_SPORTS_NUTRITION"


class NutritionProfileUpdate(BaseModel):
    goal: NutritionGoal = NutritionGoal.GENERAL_SPORTS_NUTRITION
    hydration_goal_ml: int | None = Field(default=None, ge=0, le=15000)


class NutritionProfile(BaseModel):
    athlete_id: UUID
    goal: NutritionGoal
    hydration_goal_ml: int | None = None
    updated_at: datetime


class NutritionEntryCreate(BaseModel):
    entry_date: date
    entry_type: str = Field(pattern="^(MEAL|HYDRATION|MICRONUTRIENT)$")
    name: str = Field(min_length=1, max_length=160)
    calories: float | None = Field(default=None, ge=0, le=10000)
    protein_g: float | None = Field(default=None, ge=0, le=1000)
    carbohydrates_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=1000)
    fiber_g: float | None = Field(default=None, ge=0, le=1000)
    hydration_ml: int | None = Field(default=None, ge=0, le=15000)
    micronutrients: dict[str, float] = Field(default_factory=dict)
    source_type: str = Field(default="USER_ENTERED", pattern="^USER_ENTERED$")


class NutritionEntry(NutritionEntryCreate):
    id: UUID
    athlete_id: UUID
    created_at: datetime
