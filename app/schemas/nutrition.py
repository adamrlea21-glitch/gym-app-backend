from datetime import date, datetime
from pydantic import BaseModel, Field

class FoodEntryCreate(BaseModel):
    date: date
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner|snacks)$")
    name: str
    calories: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)

class FoodEntryOut(BaseModel):
    id: int
    date: date
    date_time: datetime
    meal_type: str
    name: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float

class FoodEntryUpdate(BaseModel):
    meal_type: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner|snacks)$")
    name: str | None = None
    calories: int | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)

class MealGroup(BaseModel):
    meal_type: str
    entries: list[FoodEntryOut]

class DayTotals(BaseModel):
    date: date
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    meals: list[MealGroup]

# --- Analytics schemas ---

class DayMacroTotals(BaseModel):
    date: date
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float

class Last7DaysOut(BaseModel):
    start_date: date
    end_date: date
    items: list[DayMacroTotals]
