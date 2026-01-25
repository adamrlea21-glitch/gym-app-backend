from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WorkoutTemplateSet(Base):
    __tablename__ = "workout_template_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    template_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("workout_template_exercises.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
