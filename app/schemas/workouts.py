from pydantic import BaseModel
from typing import Optional

class StartSessionIn(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None

class AddExerciseIn(BaseModel):
    name: str
    order_index: int | None = 0

class AddSetIn(BaseModel):
    set_number: int
    reps: int | None = None
    weight_kg: float | None = None

class UpdateSetIn(BaseModel):
    reps: int | None = None
    weight_kg: float | None = None

class CreateTemplateIn(BaseModel):
    name: str
    description: str | None = None

class AddTemplateExerciseIn(BaseModel):
    name: str
    order_index: int | None = 0

class CreateTemplateFromActiveIn(BaseModel):
    name: str
    description: str | None = None
