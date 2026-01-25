from sqlalchemy import String, Date, DateTime, Integer, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

class FoodEntry(Base):
    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    date: Mapped[str] = mapped_column(Date, index=True, nullable=False)
    date_time: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)  # breakfast/lunch/dinner/snacks
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    calories: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

