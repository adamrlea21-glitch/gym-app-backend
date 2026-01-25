from fastapi import APIRouter, Depends
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func


from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.workout_session import WorkoutSession
from app.models.user import User

from datetime import datetime, timezone

from app.schemas.workouts import StartSessionIn
from app.models.workout_exercise import WorkoutExercise
from app.schemas.workouts import AddExerciseIn
from app.models.workout_set import WorkoutSet
from app.schemas.workouts import AddSetIn, UpdateSetIn

from app.models.workout_template import WorkoutTemplate
from app.schemas.workouts import CreateTemplateIn
from app.models.workout_template_exercise import WorkoutTemplateExercise
from app.schemas.workouts import AddTemplateExerciseIn

from app.schemas.workouts import CreateTemplateFromActiveIn
from app.models.workout_template_set import WorkoutTemplateSet





router = APIRouter(prefix="/workouts", tags=["workouts"])


@router.post("/session/start")
async def start_session(
    payload: StartSessionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    # If user already has an active session, return it
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        return {
            "id": existing.id,
            "status": existing.status,
            "started_at": existing.started_at,
            "ended_at": existing.ended_at,
            "title": existing.title,
            "notes": existing.notes,
        }

    # Otherwise create a new active session
    session = WorkoutSession(
        user_id=user.id, 
        status="active",
        title=payload.title,
        notes=payload.notes,
        )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "id": session.id,
        "status": session.status,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "title": session.title,
        "notes": session.notes,
    }

@router.get("/session/active")
async def get_active_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    session = res.scalar_one_or_none()

    if not session:
        return {"active": False, "session": None}

    return {
        "active": True,
        "session": {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "title": session.title,
            "notes": session.notes,
        },
    }


@router.post("/session/finish")
async def finish_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    session = res.scalar_one_or_none()

    if not session:
        return {"finished": False, "detail": "No active session"}

    session.status = "finished"
    session.ended_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(session)

    # Build summary for the finished session
    sums = await db.execute(
        select(
            func.count(func.distinct(WorkoutExercise.id)).label("exercises_count"),
            func.count(WorkoutSet.id).label("total_sets"),
            func.sum(WorkoutSet.weight_kg * WorkoutSet.reps).label("total_volume"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .where(WorkoutExercise.session_id == session.id)
    )
    row = sums.one()

    exercises_count = int(row.exercises_count or 0)
    total_sets = int(row.total_sets or 0)
    total_volume = float(row.total_volume or 0)

    duration_seconds = None
    if session.started_at and session.ended_at:
        duration_seconds = int((session.ended_at - session.started_at).total_seconds())

    return {
        "finished": True,
        "session": {
            "id": session.id,
            "source_template_id": session.source_template_id,  # NEW LINE - Return template ID
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        },
        "summary": {
            "exercises_count": exercises_count,
            "total_sets": total_sets,
            "total_volume": total_volume,
            "duration_seconds": duration_seconds,
        },
    }


@router.post("/session/exercise")
async def add_exercise_to_active_session(
    payload: AddExerciseIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Find active session
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        return {"created": False, "detail": "No active session"}

    ex = WorkoutExercise(
        session_id=session.id,
        name=payload.name,
        order_index=payload.order_index or 0,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)

    return {
        "created": True,
        "exercise": {
            "id": ex.id,
            "session_id": ex.session_id,
            "name": ex.name,
            "order_index": ex.order_index,
        },
    }

@router.post("/session/exercise/{exercise_id}/set")
async def add_set_to_exercise(
    exercise_id: int,
    payload: AddSetIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify exercise belongs to user's active session
    res = await db.execute(
        select(WorkoutExercise)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutExercise.id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    exercise = res.scalar_one_or_none()
    if not exercise:
        return {"created": False, "detail": "Exercise not found or no active session"}

    s = WorkoutSet(
        exercise_id=exercise.id,
        set_number=payload.set_number,
        reps=payload.reps,
        weight_kg=payload.weight_kg,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)

    return {
        "created": True,
        "set": {
            "id": s.id,
            "exercise_id": s.exercise_id,
            "set_number": s.set_number,
            "reps": s.reps,
            "weight_kg": s.weight_kg,
        },
    }


@router.patch("/session/exercise/{exercise_id}/set/{set_id}")
async def update_set(
    exercise_id: int,
    set_id: int,
    payload: UpdateSetIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print(f"=== UPDATE SET - exercise_id={exercise_id}, set_id={set_id} ===")
    print(f"Payload: {payload.model_dump()}")
    
    res = await db.execute(
        select(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSet.id == set_id,
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    s_obj = res.scalar_one_or_none()
    
    if not s_obj:
        print("ERROR: Set not found!")
        return {"updated": False, "detail": "Set not found or no active session"}

    print(f"Found set: id={s_obj.id}, set_number={s_obj.set_number}, old_reps={s_obj.reps}, old_weight={s_obj.weight_kg}")

    data = payload.model_dump(exclude_unset=True)
    if "reps" in data:
        s_obj.reps = data["reps"]
        print(f"Updated reps to: {s_obj.reps}")
    if "weight_kg" in data:
        s_obj.weight_kg = data["weight_kg"]
        print(f"Updated weight to: {s_obj.weight_kg}")

    await db.commit()
    await db.refresh(s_obj)
    
    print(f"After commit: id={s_obj.id}, reps={s_obj.reps}, weight={s_obj.weight_kg}")
    print("=== UPDATE SET COMPLETE ===")

    return {
        "updated": True,
        "set": {
            "id": s_obj.id,
            "exercise_id": s_obj.exercise_id,
            "set_number": s_obj.set_number,
            "reps": s_obj.reps,
            "weight_kg": s_obj.weight_kg,
        },
    }


@router.delete("/session/exercise/{exercise_id}/set/{set_id}")
async def delete_set(
    exercise_id: int,
    set_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSet.id == set_id,
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    s_obj = res.scalar_one_or_none()
    if not s_obj:
        return {"deleted": False, "detail": "Set not found or no active session"}

    await db.delete(s_obj)
    await db.commit()

    return {"deleted": True, "set_id": set_id}

@router.get("/session/active/full")
async def get_active_session_full(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Active session
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        return {"active": False, "session": None}

    # Exercises in session
    ex_res = await db.execute(
        select(WorkoutExercise)
        .where(WorkoutExercise.session_id == session.id)
        .order_by(WorkoutExercise.order_index.asc(), WorkoutExercise.id.asc())
    )
    exercises = ex_res.scalars().all()

    exercise_ids = [e.id for e in exercises]
    sets_by_ex: dict[int, list[WorkoutSet]] = {eid: [] for eid in exercise_ids}

    if exercise_ids:
        set_res = await db.execute(
            select(WorkoutSet)
            .where(WorkoutSet.exercise_id.in_(exercise_ids))
            .order_by(WorkoutSet.exercise_id.asc(), WorkoutSet.set_number.asc(), WorkoutSet.id.asc())
        )
        sets = set_res.scalars().all()
        for s in sets:
            sets_by_ex[s.exercise_id].append(s)

    return {
        "active": True,
        "session": {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "title": session.title,
            "notes": session.notes,
            "exercises": [
                {
                    "id": e.id,
                    "name": e.name,
                    "order_index": e.order_index,
                    "sets": [
                        {
                            "id": s.id,
                            "set_number": s.set_number,
                            "reps": s.reps,
                            "weight_kg": s.weight_kg,
                            "created_at": s.created_at,
                        }
                        for s in sets_by_ex.get(e.id, [])
                    ],
                }
                for e in exercises
            ],
        },
    }


@router.get("/templates")
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(WorkoutTemplate)
        .where(WorkoutTemplate.user_id == user.id)
        .order_by(WorkoutTemplate.created_at.desc())
    )
    templates = res.scalars().all()

    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "created_at": t.created_at,
            }
            for t in templates
        ]
    }



@router.post("/templates")
async def create_template(
    payload: CreateTemplateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = WorkoutTemplate(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)

    return {
        "created": True,
        "template": {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "created_at": t.created_at,
        },
    }


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print(f"=== UPDATE TEMPLATE - Template ID: {template_id} ===")
    print(f"Payload has exercises: {'exercises' in payload}")
    
    # Get the template
    res = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            WorkoutTemplate.user_id == user.id,
        )
    )
    template = res.scalar_one_or_none()
    
    if not template:
        return {"updated": False, "detail": "Template not found"}
    
    # Update name and description if provided
    if "name" in payload:
        template.name = payload["name"]
    if "description" in payload:
        template.description = payload["description"]
    
    # Update exercises if provided
    if "exercises" in payload:
        # First, manually delete all sets for this template
        print("Deleting existing template sets...")
        sets_to_delete = await db.execute(
            select(WorkoutTemplateSet)
            .join(WorkoutTemplateExercise)
            .where(WorkoutTemplateExercise.template_id == template_id)
        )
        all_sets = sets_to_delete.scalars().all()
        print(f"Found {len(all_sets)} sets to delete")
        for s in all_sets:
            print(f"  Deleting set: id={s.id}, set_number={s.set_number}, reps={s.reps}")
            await db.delete(s)
        await db.flush()
        
        # Delete existing exercises
        print("Deleting existing template exercises...")
        ex_res = await db.execute(
            select(WorkoutTemplateExercise).where(
                WorkoutTemplateExercise.template_id == template_id
            )
        )
        existing_exercises = ex_res.scalars().all()
        print(f"Found {len(existing_exercises)} exercises to delete")
        for ex in existing_exercises:
            print(f"  Deleting exercise: id={ex.id}, name={ex.name}")
            await db.delete(ex)
        await db.flush()
        
        # Add new exercises
        print(f"Adding {len(payload['exercises'])} new exercises...")
        for ex_data in payload["exercises"]:
            print(f"  Creating exercise: {ex_data['name']}")
            new_ex = WorkoutTemplateExercise(
                template_id=template_id,
                name=ex_data["name"],
                order_index=ex_data["order_index"],
            )
            db.add(new_ex)
            await db.flush()
            print(f"    Exercise created: ID={new_ex.id}")
            
            # Add sets for this exercise
            sets_data = ex_data.get("sets", [])
            print(f"    Adding {len(sets_data)} sets...")
            for set_data in sets_data:
                print(f"      Creating set: set_number={set_data['set_number']}, reps={set_data.get('target_reps')}, weight={set_data.get('target_weight_kg')}")
                new_set = WorkoutTemplateSet(
                    template_exercise_id=new_ex.id,
                    set_number=set_data["set_number"],
                    reps=set_data.get("target_reps"),
                    weight_kg=set_data.get("target_weight_kg"),
                )
                db.add(new_set)
    
    await db.commit()
    await db.refresh(template)
    
    print("=== UPDATE TEMPLATE COMPLETE ===")
    
    return {
        "updated": True,
        "template": {
            "id": template.id,
            "name": template.name,
            "description": template.description,
        },
    }


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            WorkoutTemplate.user_id == user.id,
        )
    )
    tpl = res.scalar_one_or_none()

    if not tpl:
        return {"deleted": False, "detail": "Template not found"}

    await db.delete(tpl)
    await db.commit()

    return {"deleted": True, "template_id": template_id}



@router.post("/templates/{template_id}/exercises")
async def add_exercise_to_template(
    template_id: int,
    payload: AddTemplateExerciseIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Ensure template belongs to user
    res = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            WorkoutTemplate.user_id == user.id,
        )
    )
    template = res.scalar_one_or_none()
    if not template:
        return {"created": False, "detail": "Template not found"}

    ex = WorkoutTemplateExercise(
        template_id=template.id,
        name=payload.name,
        order_index=payload.order_index or 0,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)

    return {
        "created": True,
        "exercise": {
            "id": ex.id,
            "template_id": ex.template_id,
            "name": ex.name,
            "order_index": ex.order_index,
        },
    }


@router.post("/templates/{template_id}/start")
async def start_session_from_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print(f"=== START FROM TEMPLATE - Template ID: {template_id} ===")
    
    # Get template
    res = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            WorkoutTemplate.user_id == user.id,
        )
    )
    template = res.scalar_one_or_none()
    if not template:
        return {"started": False, "detail": "Template not found"}

    # Prevent multiple active sessions
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    if res.scalar_one_or_none():
        return {"started": False, "detail": "Active session already exists"}

    # Create new session with source_template_id
    session = WorkoutSession(
        user_id=user.id,
        status="active",
        title=template.name,
        notes=template.description,
        source_template_id=template_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    print(f"Session created: ID={session.id}")

    # Get template exercises
    ex_res = await db.execute(
        select(WorkoutTemplateExercise)
        .where(WorkoutTemplateExercise.template_id == template.id)
        .order_by(
            WorkoutTemplateExercise.order_index.asc(),
            WorkoutTemplateExercise.id.asc(),
        )
    )
    template_exercises = ex_res.scalars().all()
    print(f"Found {len(template_exercises)} template exercises")

    for tex in template_exercises:
        print(f"Processing template exercise: {tex.name} (ID={tex.id})")
        
        ex = WorkoutExercise(
            session_id=session.id,
            name=tex.name,
            order_index=tex.order_index,
            source_template_exercise_id=tex.id,
        )
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        print(f"  Workout exercise created: ID={ex.id}")

        # Copy template sets into real sets
        ts_res = await db.execute(
            select(WorkoutTemplateSet)
            .where(WorkoutTemplateSet.template_exercise_id == tex.id)
            .order_by(WorkoutTemplateSet.set_number.asc())
        )
        tsets = ts_res.scalars().all()
        print(f"  Found {len(tsets)} template sets")

        for ts in tsets:
            print(f"    Creating workout set: set_number={ts.set_number}, reps={ts.reps}, weight={ts.weight_kg}")
            s = WorkoutSet(
                exercise_id=ex.id,
                set_number=ts.set_number,
                reps=ts.reps,
                weight_kg=ts.weight_kg,
                source_template_set_id=ts.id,
            )
            db.add(s)

    await db.commit()
    print("=== START FROM TEMPLATE COMPLETE ===")

    return {
        "started": True,
        "session": {
            "id": session.id,
            "title": session.title,
            "notes": session.notes,
        },
    }


@router.get("/analytics/weekly-review")
async def analytics_weekly_review(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Weekly review summary for the last 7 days:
    - sessions_count
    - total_sets
    - total_reps
    - total_volume
    - top_exercises_by_volume (top 5)
    - prs_count (new max-weight PRs in last 7 days)
    """
    # Sessions finished in last 7 days
    sess_res = await db.execute(
        select(func.count(WorkoutSession.id))
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.ended_at >= func.datetime("now", "-7 days"),
        )
    )
    sessions_count = int(sess_res.scalar() or 0)

    # Totals across sets in last 7 days (finished sessions only)
    totals_res = await db.execute(
        select(
            func.count(WorkoutSet.id).label("sets"),
            func.coalesce(func.sum(WorkoutSet.reps), 0).label("reps"),
            func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0).label("volume"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSet.reps.isnot(None),
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.ended_at >= func.datetime("now", "-7 days"),
        )
    )
    tr = totals_res.first()
    total_sets = int(tr.sets or 0)
    total_reps = int(tr.reps or 0)
    total_volume = float(tr.volume or 0)

    # Top 5 exercises by volume in last 7 days
    top_res = await db.execute(
        select(
            WorkoutExercise.name.label("exercise"),
            func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0).label("volume"),
            func.count(WorkoutSet.id).label("sets"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSet.reps.isnot(None),
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.ended_at >= func.datetime("now", "-7 days"),
        )
        .group_by(WorkoutExercise.name)
        .order_by(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps).desc())
        .limit(5)
    )
    top_rows = top_res.all()

    # PRs count in last 7 days:
    # For each exercise name, determine all-time max weight; count exercises whose max occurred in last 7 days.
    subq = (
        select(
            WorkoutExercise.name.label("exercise"),
            func.max(WorkoutSet.weight_kg).label("max_weight"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(WorkoutExercise.name)
        .subquery()
    )

    prs_res = await db.execute(
        select(func.count(func.distinct(subq.c.exercise)))
        .select_from(subq)
        .join(WorkoutExercise, WorkoutExercise.name == subq.c.exercise)
        .join(WorkoutSet, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutExercise.session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg == subq.c.max_weight,
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.ended_at >= func.datetime("now", "-7 days"),
        )
    )
    prs_count = int(prs_res.scalar() or 0)

    return {
        "range": "last_7_days",
        "sessions_count": sessions_count,
        "total_sets": total_sets,
        "total_reps": total_reps,
        "total_volume": total_volume,
        "prs_count": prs_count,
        "top_exercises_by_volume": [
            {"exercise": r.exercise, "volume": float(r.volume or 0), "sets": int(r.sets or 0)}
            for r in top_rows
        ],
    }



@router.get("/analytics/volume")
async def analytics_volume_last_7_days(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # last 7 days (SQLite-compatible)
    # Only finished sessions to avoid counting in-progress workouts
    res = await db.execute(
        select(
            WorkoutExercise.name.label("exercise"),
            func.sum((WorkoutSet.weight_kg * WorkoutSet.reps)).label("volume"),
            func.count(WorkoutSet.id).label("sets"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSet.reps.isnot(None),
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.ended_at >= func.datetime("now", "-7 days"),
        )
        .group_by(WorkoutExercise.name)
        .order_by(func.sum((WorkoutSet.weight_kg * WorkoutSet.reps)).desc())
    )

    rows = res.all()
    return {
        "range": "last_7_days",
        "items": [
            {
                "exercise": r.exercise,
                "volume": float(r.volume or 0),
                "sets": int(r.sets or 0),
            }
            for r in rows
        ],
    }


@router.get("/analytics/prs")
async def analytics_personal_bests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get max weight per exercise name
    subq = (
        select(
            WorkoutExercise.name.label("exercise"),
            func.max(WorkoutSet.weight_kg).label("max_weight"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(WorkoutExercise.name)
        .subquery()
    )

    # Join back to find one matching set (weight == max_weight)
    res = await db.execute(
        select(
            subq.c.exercise,
            subq.c.max_weight,
            WorkoutSet.reps,
            WorkoutSession.ended_at,
        )
        .select_from(subq)
        .join(WorkoutExercise, WorkoutExercise.name == subq.c.exercise)
        .join(WorkoutSet, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutExercise.session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSet.weight_kg == subq.c.max_weight,
        )
        .order_by(subq.c.exercise.asc(), WorkoutSession.ended_at.desc())
    )

    rows = res.all()

    # Keep only the newest match per exercise (in case multiple sets hit the same max)
    best: dict[str, dict] = {}
    for r in rows:
        if r.exercise not in best:
            best[r.exercise] = {
                "exercise": r.exercise,
                "weight_kg": float(r.max_weight or 0),
                "reps": r.reps,
                "date": r.ended_at,
            }

    return {"items": list(best.values())}


@router.get("/analytics/exercise/{exercise_name}/timeline")
async def analytics_exercise_timeline(
    exercise_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Timeline of max weight used per finished session for a given exercise.
    """

    res = await db.execute(
        select(
            WorkoutSession.ended_at.label("date"),
            func.max(WorkoutSet.weight_kg).label("max_weight"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutExercise.name == exercise_name,
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(WorkoutSession.id)
        .order_by(WorkoutSession.ended_at.asc())
    )

    rows = res.all()

    return {
        "exercise": exercise_name,
        "points": [
            {
                "date": r.date,
                "weight_kg": float(r.max_weight),
            }
            for r in rows
        ],
    }


@router.get("/analytics/exercises")
async def analytics_list_exercises(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Return distinct exercise names, with a stable "exercise_key" = name for now,
    # plus an example id from the most recent finished session.
    res = await db.execute(
        select(
            WorkoutExercise.name.label("name"),
            func.max(WorkoutExercise.id).label("exercise_id"),
        )
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
        )
        .group_by(WorkoutExercise.name)
        .order_by(WorkoutExercise.name.asc())
    )

    return {
        "items": [
            {"id": int(r.exercise_id), "name": r.name}
            for r in res.all()
            if r.exercise_id is not None
        ]
    }


@router.get("/analytics/exercise/{exercise_id}/timeline")
async def analytics_exercise_timeline_by_id(
    exercise_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # First, confirm this exercise id belongs to the user (finished sessions only)
    chk = await db.execute(
        select(WorkoutExercise)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutExercise.id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
        )
    )
    ex = chk.scalar_one_or_none()
    if not ex:
        return {"found": False, "detail": "Exercise not found"}

    # Timeline: per finished session, max weight for this exercise name
    res = await db.execute(
        select(
            WorkoutSession.ended_at.label("date"),
            func.max(WorkoutSet.weight_kg).label("max_weight"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutExercise.name == ex.name,  # group by name for consistent history
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(WorkoutSession.id)
        .order_by(WorkoutSession.ended_at.asc())
    )

    rows = res.all()

    return {
        "found": True,
        "exercise": {"id": ex.id, "name": ex.name},
        "points": [{"date": r.date, "weight_kg": float(r.max_weight)} for r in rows],
    }


@router.get("/analytics/exercise/{exercise_id}/weekly")
async def analytics_exercise_weekly_max_weight(
    exercise_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Confirm this exercise belongs to the user (finished sessions)
    chk = await db.execute(
        select(WorkoutExercise)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutExercise.id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
        )
    )
    ex = chk.scalar_one_or_none()
    if not ex:
        return {"found": False, "detail": "Exercise not found"}

    # SQLite: week bucket = Monday of that week (approx using 'weekday 1')
    # We group by week_start and take max weight that week.
    res = await db.execute(
        select(
            func.date(WorkoutSession.ended_at, "weekday 1", "-7 days").label("week_start"),
            func.max(WorkoutSet.weight_kg).label("max_weight"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutExercise.name == ex.name,  # keep history consistent even if ids differ
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(func.date(WorkoutSession.ended_at, "weekday 1", "-7 days"))
        .order_by(func.date(WorkoutSession.ended_at, "weekday 1", "-7 days").asc())
    )

    rows = res.all()

    return {
        "found": True,
        "exercise": {"id": ex.id, "name": ex.name},
        "points": [
            {"week_start": r.week_start, "weight_kg": float(r.max_weight)}
            for r in rows
            if r.week_start is not None and r.max_weight is not None
        ],
    }


@router.get("/analytics/exercise/{exercise_id}/weekly-volume")
async def analytics_exercise_weekly_volume(
    exercise_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Confirm exercise belongs to user (finished sessions)
    chk = await db.execute(
        select(WorkoutExercise)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutExercise.id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
        )
    )
    ex = chk.scalar_one_or_none()
    if not ex:
        return {"found": False, "detail": "Exercise not found"}

    res = await db.execute(
        select(
            func.date(WorkoutSession.ended_at, "weekday 1", "-7 days").label("week_start"),
            func.sum(WorkoutSet.weight_kg * WorkoutSet.reps).label("volume"),
            func.sum(WorkoutSet.reps).label("total_reps"),
            func.count(WorkoutSet.id).label("sets"),
        )
        .select_from(WorkoutSet)
        .join(WorkoutExercise, WorkoutSet.exercise_id == WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutExercise.name == ex.name,
            WorkoutSet.weight_kg.isnot(None),
            WorkoutSet.reps.isnot(None),
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(func.date(WorkoutSession.ended_at, "weekday 1", "-7 days"))
        .order_by(func.date(WorkoutSession.ended_at, "weekday 1", "-7 days").asc())
    )

    rows = res.all()

    return {
        "found": True,
        "exercise": {"id": ex.id, "name": ex.name},
        "points": [
            {
                "week_start": r.week_start,
                "volume": float(r.volume or 0),
                "total_reps": int(r.total_reps or 0),
                "sets": int(r.sets or 0),
            }
            for r in rows
            if r.week_start is not None
        ],
    }


@router.get("/history")
async def workout_history(
    limit: int = 20,
    offset: int = 0,
    date: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 100))

    stmt = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
        )
        .order_by(WorkoutSession.ended_at.desc(), WorkoutSession.id.desc())
        .limit(limit)
        .offset(offset)
    )

    if date:
        d = datetime.strptime(date, "%Y-%m-%d").date()
        stmt = stmt.where(func.date(WorkoutSession.ended_at) == d)

    res = await db.execute(stmt)
    sessions = res.scalars().all()

    return {
        "items": [
            {
                "id": s.id,
                "title": s.title,
                "notes": s.notes,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
            }
            for s in sessions
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/session/{session_id}")
async def get_session_full_by_id(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print(f"=== GET SESSION BY ID: {session_id} ===")
    
    # Session must belong to user
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.user_id == user.id,
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        return {"found": False, "detail": "Session not found"}

    # Exercises in session
    ex_res = await db.execute(
        select(WorkoutExercise)
        .where(WorkoutExercise.session_id == session.id)
        .order_by(WorkoutExercise.order_index.asc(), WorkoutExercise.id.asc())
    )
    exercises = ex_res.scalars().all()
    ex_ids = [e.id for e in exercises]
    print(f"Found {len(exercises)} exercises")

    sets_by_ex: dict[int, list[WorkoutSet]] = {eid: [] for eid in ex_ids}
    if ex_ids:
        set_res = await db.execute(
            select(WorkoutSet)
            .where(WorkoutSet.exercise_id.in_(ex_ids))
            .order_by(WorkoutSet.exercise_id.asc(), WorkoutSet.set_number.asc(), WorkoutSet.id.asc())
        )
        sets = set_res.scalars().all()
        print(f"Found {len(sets)} total sets")
        for s in sets:
            print(f"  Set: exercise_id={s.exercise_id}, set_number={s.set_number}, reps={s.reps}, weight={s.weight_kg}")
            sets_by_ex[s.exercise_id].append(s)

    result = {
        "found": True,
        "session": {
            "id": session.id,
            "status": session.status,
            "title": session.title,
            "notes": session.notes,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "exercises": [
                {
                    "id": e.id,
                    "name": e.name,
                    "order_index": e.order_index,
                    "sets": [
                        {
                            "id": s.id,
                            "set_number": s.set_number,
                            "reps": s.reps,
                            "weight_kg": s.weight_kg,
                            "created_at": s.created_at,
                        }
                        for s in sets_by_ex.get(e.id, [])
                    ],
                }
                for e in exercises
            ],
        },
    }
    
    print(f"Returning {len(result['session']['exercises'])} exercises in response")
    for ex in result['session']['exercises']:
        print(f"  Exercise {ex['name']}: {len(ex['sets'])} sets")
    
    print("=== GET SESSION COMPLETE ===")
    return result


@router.post("/templates/from-active")
async def create_template_from_active(
    payload: CreateTemplateFromActiveIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print(f"=== CREATE TEMPLATE FROM ACTIVE CALLED - User: {user.id}, Name: {payload.name} ===")
    
    # Get active session
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        return {"created": False, "detail": "No active session"}

    # Create template
    template = WorkoutTemplate(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    print(f"Template created: ID={template.id}")

    # Get exercises in session
    ex_res = await db.execute(
        select(WorkoutExercise)
        .where(WorkoutExercise.session_id == session.id)
        .order_by(WorkoutExercise.order_index.asc(), WorkoutExercise.id.asc())
    )
    exercises = ex_res.scalars().all()
    print(f"Found {len(exercises)} exercises in session")

    for ex in exercises:
        print(f"Processing exercise: {ex.name} (ID={ex.id})")
        
        # Create template exercise
        tex = WorkoutTemplateExercise(
            template_id=template.id,
            name=ex.name,
            order_index=ex.order_index,
        )
        db.add(tex)
        await db.commit()
        await db.refresh(tex)
        print(f"  Template exercise created: ID={tex.id}")

        # Copy sets into template sets
        set_res = await db.execute(
            select(WorkoutSet)
            .where(WorkoutSet.exercise_id == ex.id)
            .order_by(WorkoutSet.set_number.asc(), WorkoutSet.id.asc())
        )
        sets = set_res.scalars().all()
        print(f"  Found {len(sets)} sets for this exercise")

        for s in sets:
            print(f"    Creating set: set_number={s.set_number}, reps={s.reps}, weight={s.weight_kg}")
            ts = WorkoutTemplateSet(
                template_exercise_id=tex.id,
                set_number=s.set_number,
                reps=s.reps,
                weight_kg=s.weight_kg,
            )
            db.add(ts)

    await db.commit()
    print("=== TEMPLATE CREATION COMPLETE ===")

    return {
        "created": True,
        "template": {
            "id": template.id,
            "name": template.name,
            "description": template.description,
        },
    }



@router.get("/calendar/month")
async def workout_calendar_month(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the days of the given month that have at least one finished workout.
    Example: /workouts/calendar/month?year=2026&month=1
    """
    from datetime import datetime, timezone
    from calendar import monthrange

    if month < 1 or month > 12:
        return {"detail": "month must be 1-12"}

    days_in_month = monthrange(year, month)[1]
    start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc)

    res = await db.execute(
        select(func.date(WorkoutSession.ended_at).label("d"))
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "finished",
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.ended_at >= start_dt,
            WorkoutSession.ended_at <= end_dt,
        )
        .group_by(func.date(WorkoutSession.ended_at))
        .order_by(func.date(WorkoutSession.ended_at).asc())
    )

    rows = res.all()
    # rows contain strings like "2026-01-23"
    days = []
    for r in rows:
        try:
            days.append(int(str(r.d)[8:10]))
        except Exception:
            pass

    return {"year": year, "month": month, "days": days}


@router.delete("/session/exercise/{exercise_id}")
async def delete_exercise(
    exercise_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify exercise belongs to user's active session
    res = await db.execute(
        select(WorkoutExercise)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutExercise.id == exercise_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "active",
        )
    )
    exercise = res.scalar_one_or_none()
    if not exercise:
        return {"deleted": False, "detail": "Exercise not found or no active session"}

    await db.delete(exercise)
    await db.commit()

    return {"deleted": True, "exercise_id": exercise_id}

@router.delete("/purge-workouts")
async def purge_all_workouts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes ALL workout data for the current user:
    - workout sessions
    - exercises
    - sets
    """

    # Get all session IDs for this user
    res = await db.execute(
        select(WorkoutSession.id).where(WorkoutSession.user_id == user.id)
    )
    session_ids = [r[0] for r in res.all()]

    if not session_ids:
        return {"deleted": 0}

    # Delete sets
    await db.execute(
        delete(WorkoutSet).where(
            WorkoutSet.exercise_id.in_(
                select(WorkoutExercise.id).where(
                    WorkoutExercise.session_id.in_(session_ids)
                )
            )
        )
    )

    # Delete exercises
    await db.execute(
        delete(WorkoutExercise).where(
            WorkoutExercise.session_id.in_(session_ids)
        )
    )

    # Delete sessions
    await db.execute(
        delete(WorkoutSession).where(
            WorkoutSession.id.in_(session_ids)
        )
    )

    await db.commit()

    return {"deleted_sessions": len(session_ids)}

@router.delete("/session/{session_id}")
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Ensure session belongs to current user
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.user_id == user.id,
        )
    )
    sess = res.scalar_one_or_none()
    if not sess:
        return {"deleted": False, "detail": "Session not found"}

    # Delete sets -> exercises -> session (safe for SQLite)
    ex_ids_res = await db.execute(
        select(WorkoutExercise.id).where(WorkoutExercise.session_id == session_id)
    )
    ex_ids = [r[0] for r in ex_ids_res.all()]

    if ex_ids:
        await db.execute(delete(WorkoutSet).where(WorkoutSet.exercise_id.in_(ex_ids)))
        await db.execute(delete(WorkoutExercise).where(WorkoutExercise.id.in_(ex_ids)))

    await db.execute(delete(WorkoutSession).where(WorkoutSession.id == session_id))
    await db.commit()

    return {"deleted": True, "session_id": session_id}

@router.delete("/exercise/{exercise_name}/purge")
async def purge_exercise_history(
    exercise_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    name_norm = exercise_name.strip().lower()
    if not name_norm:
        return {"deleted_exercises": 0, "deleted_sets": 0}

    # Find ALL workout_exercises for this user matching the name (case-insensitive)
    ex_ids_res = await db.execute(
        select(WorkoutExercise.id)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            func.lower(WorkoutExercise.name) == name_norm,
        )
    )
    ex_ids = [r[0] for r in ex_ids_res.all()]

    if not ex_ids:
        return {"deleted_exercises": 0, "deleted_sets": 0, "detail": "No matching exercises found"}

    # Delete sets first
    sets_del = await db.execute(delete(WorkoutSet).where(WorkoutSet.exercise_id.in_(ex_ids)))
    # Delete exercises
    ex_del = await db.execute(delete(WorkoutExercise).where(WorkoutExercise.id.in_(ex_ids)))

    await db.commit()

    return {
        "exercise": exercise_name,
        "deleted_exercises": ex_del.rowcount or 0,
        "deleted_sets": sets_del.rowcount or 0,
    }

