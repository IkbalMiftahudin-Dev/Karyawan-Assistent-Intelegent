from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleOut,
    ScheduleMutationResponse,
    ConflictBrief,
    FreeSlotOut,
    DashboardStatsOut,
)
from backend.services import schedule_service

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])


def _to_conflict_list(conflicts) -> List[ConflictBrief]:
    return [
        ConflictBrief(
            id=c.id,
            title=c.title,
            start_time=c.start_time,
            end_time=c.end_time,
        )
        for c in conflicts
    ]


@router.get("/stats", response_model=DashboardStatsOut)
def get_stats(
    target_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    return schedule_service.get_dashboard_stats(db, target_date)


@router.get("/free-slots", response_model=List[FreeSlotOut])
def get_free_slots(
    target_date: date = Query(default_factory=date.today),
    duration_minutes: int = Query(60, ge=15, le=480),
    db: Session = Depends(get_db),
):
    return schedule_service.find_free_slots(db, target_date, duration_minutes)


@router.get("", response_model=List[ScheduleOut])
def list_schedules(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return schedule_service.list_schedules(
        db,
        date_from=date_from,
        date_to=date_to,
        status=status,
        category=category,
        priority=priority,
        search=search,
    )


@router.post("", response_model=ScheduleMutationResponse, status_code=201)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    try:
        item, conflicts = schedule_service.create_schedule(
            db=db,
            title=payload.title,
            start_time=payload.start_time,
            end_time=payload.end_time,
            description=payload.description or "",
            category=payload.category,
            priority=payload.priority,
            status=payload.status,
            location=payload.location or "",
            reminder_minutes=payload.reminder_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    c_list = _to_conflict_list(conflicts)
    return ScheduleMutationResponse(
        schedule=item,
        conflicts=c_list,
        has_conflict=len(c_list) > 0,
    )


@router.put("/{schedule_id}", response_model=ScheduleMutationResponse)
def update_schedule(schedule_id: int, payload: ScheduleUpdate, db: Session = Depends(get_db)):
    try:
        item, conflicts = schedule_service.update_schedule(
            db, schedule_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not item:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan.")

    c_list = _to_conflict_list(conflicts)
    return ScheduleMutationResponse(
        schedule=item,
        conflicts=c_list,
        has_conflict=len(c_list) > 0,
    )


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    ok = schedule_service.delete_schedule(db, schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan.")
    return {"deleted": True, "id": schedule_id}
