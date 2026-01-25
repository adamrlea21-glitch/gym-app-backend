from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.food_entry import FoodEntry
from app.schemas.nutrition import FoodEntryCreate, FoodEntryUpdate, FoodEntryOut, DayTotals, MealGroup, Last7DaysOut, DayMacroTotals

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.post("/entry", response_model=FoodEntryOut, status_code=201)
async def create_entry(
    payload: FoodEntryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = FoodEntry(
        user_id=user.id,
        date=payload.date,
        meal_type=payload.meal_type,
        name=payload.name,
        calories=payload.calories,
        protein_g=payload.protein_g,
        carbs_g=payload.carbs_g,
        fat_g=payload.fat_g,
        source="manual",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return FoodEntryOut(
        id=entry.id,
        date=entry.date,
        date_time=entry.date_time,
        meal_type=entry.meal_type,
        name=entry.name,
        calories=entry.calories,
        protein_g=entry.protein_g,
        carbs_g=entry.carbs_g,
        fat_g=entry.fat_g,
    )


@router.get("/day", response_model=DayTotals)
async def get_day(
    date: date,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FoodEntry)
        .where(FoodEntry.user_id == user.id, FoodEntry.date == date)
        .order_by(FoodEntry.date_time.asc(), FoodEntry.id.asc())
    )
    entries = res.scalars().all()

    calories = sum(e.calories for e in entries)
    protein = float(sum(e.protein_g for e in entries))
    carbs = float(sum(e.carbs_g for e in entries))
    fat = float(sum(e.fat_g for e in entries))

    order = ["breakfast", "lunch", "dinner", "snacks"]
    meals: list[MealGroup] = []
    for mt in order:
        mt_entries = [e for e in entries if e.meal_type == mt]
        meals.append(
            MealGroup(
                meal_type=mt,
                entries=[
                    FoodEntryOut(
                        id=e.id,
                        date=e.date,
                        date_time=e.date_time,
                        meal_type=e.meal_type,
                        name=e.name,
                        calories=e.calories,
                        protein_g=e.protein_g,
                        carbs_g=e.carbs_g,
                        fat_g=e.fat_g,
                    )
                    for e in mt_entries
                ],
            )
        )

    return DayTotals(
        date=date,
        calories=calories,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        meals=meals,
    )

from fastapi import HTTPException, status


@router.get("/analytics/last7", response_model=Last7DaysOut)
async def nutrition_last7(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    res = await db.execute(
        select(
            FoodEntry.date.label("d"),
            func.coalesce(func.sum(FoodEntry.calories), 0).label("calories"),
            func.coalesce(func.sum(FoodEntry.protein_g), 0.0).label("protein_g"),
            func.coalesce(func.sum(FoodEntry.carbs_g), 0.0).label("carbs_g"),
            func.coalesce(func.sum(FoodEntry.fat_g), 0.0).label("fat_g"),
        )
        .where(
            FoodEntry.user_id == user.id,
            FoodEntry.date >= start_date,
            FoodEntry.date <= end_date,
        )
        .group_by(FoodEntry.date)
        .order_by(FoodEntry.date.asc())
    )

    rows = res.all()
    by_date = {r.d: r for r in rows}

    items = []
    d = start_date
    while d <= end_date:
        r = by_date.get(d)
        items.append(
            DayMacroTotals(
                date=d,
                calories=int(r.calories) if r else 0,
                protein_g=float(r.protein_g) if r else 0.0,
                carbs_g=float(r.carbs_g) if r else 0.0,
                fat_g=float(r.fat_g) if r else 0.0,
            )
        )
        d = d + timedelta(days=1)

    return Last7DaysOut(start_date=start_date, end_date=end_date, items=items)


@router.patch("/entry/{entry_id}", response_model=FoodEntryOut)
async def update_entry(
    entry_id: int,
    payload: FoodEntryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user.id)
    )
    entry = res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(entry, k, v)

    await db.commit()
    await db.refresh(entry)

    return FoodEntryOut(
        id=entry.id,
        date=entry.date,
        date_time=entry.date_time,
        meal_type=entry.meal_type,
        name=entry.name,
        calories=entry.calories,
        protein_g=entry.protein_g,
        carbs_g=entry.carbs_g,
        fat_g=entry.fat_g,
    )

@router.delete("/entry/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user.id)
    )
    entry = res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    await db.delete(entry)
    await db.commit()
    return

@router.delete("/entry/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user.id)
    )
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    await db.delete(entry)
    await db.commit()
    return

