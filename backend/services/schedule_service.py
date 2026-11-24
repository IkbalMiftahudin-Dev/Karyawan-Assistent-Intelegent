from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from backend.models import Schedule, UserProfile, KnowledgeDocument


def _parse_hhmm(hhmm: str, fallback_h: int, fallback_m: int) -> Tuple[int, int]:
    try:
        parts = hhmm.strip().split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        return fallback_h, fallback_m


def find_conflicts(
    db: Session,
    start_time: datetime,
    end_time: datetime,
    exclude_id: Optional[int] = None,
) -> List[Schedule]:
    """Mencari jadwal aktif yang waktunya bertabrakan dengan rentang waktu baru."""
    query = db.query(Schedule).filter(
        Schedule.status == "scheduled",
        Schedule.start_time < end_time,
        Schedule.end_time > start_time,
    )
    if exclude_id is not None:
        query = query.filter(Schedule.id != exclude_id)
    return query.order_by(Schedule.start_time.asc()).all()


def create_schedule(
    db: Session,
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: str = "",
    category: str = "meeting",
    priority: str = "medium",
    status: str = "scheduled",
    location: str = "",
    reminder_minutes: int = 15,
) -> Tuple[Schedule, List[Schedule]]:
    if end_time <= start_time:
        raise ValueError("Waktu selesai harus lebih besar dari waktu mulai.")

    conflicts = find_conflicts(db, start_time, end_time) if status == "scheduled" else []

    item = Schedule(
        title=title.strip(),
        description=(description or "").strip(),
        start_time=start_time,
        end_time=end_time,
        category=category,
        priority=priority,
        status=status,
        location=(location or "").strip(),
        reminder_minutes=reminder_minutes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, conflicts


def list_schedules(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Schedule]:
    query = db.query(Schedule)
    if date_from:
        query = query.filter(Schedule.end_time >= date_from)
    if date_to:
        query = query.filter(Schedule.start_time <= date_to)
    if status:
        query = query.filter(Schedule.status == status)
    if category:
        query = query.filter(Schedule.category == category)
    if priority:
        query = query.filter(Schedule.priority == priority)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Schedule.title.ilike(like),
                Schedule.description.ilike(like),
                Schedule.location.ilike(like),
            )
        )
    return query.order_by(Schedule.start_time.asc()).all()


def update_schedule(
    db: Session,
    schedule_id: int,
    updates: dict,
) -> Tuple[Optional[Schedule], List[Schedule]]:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        return None, []

    new_start = updates.get("start_time", item.start_time)
    new_end = updates.get("end_time", item.end_time)
    if new_end <= new_start:
        raise ValueError("Waktu selesai harus lebih besar dari waktu mulai.")

    for key, value in updates.items():
        if value is not None and hasattr(item, key):
            setattr(item, key, value)

    item.updated_at = datetime.now()
    db.commit()
    db.refresh(item)

    conflicts = (
        find_conflicts(db, item.start_time, item.end_time, exclude_id=item.id)
        if item.status == "scheduled"
        else []
    )
    return item, conflicts


def delete_schedule(db: Session, schedule_id: int) -> bool:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def find_free_slots(
    db: Session,
    target_date: date,
    duration_minutes: int = 60,
) -> List[dict]:
    """Menemukan slot waktu kosong pada tanggal tertentu berdasarkan jam kerja profil."""
    profile = db.query(UserProfile).first()
    ws_h, ws_m = _parse_hhmm(profile.work_start if profile else "08:30", 8, 30)
    we_h, we_m = _parse_hhmm(profile.work_end if profile else "17:30", 17, 30)

    work_start = datetime(target_date.year, target_date.month, target_date.day, ws_h, ws_m)
    work_end = datetime(target_date.year, target_date.month, target_date.day, we_h, we_m)
    if work_end <= work_start:
        work_end = work_start + timedelta(hours=8)

    busy_items = (
        db.query(Schedule)
        .filter(
            Schedule.status == "scheduled",
            Schedule.start_time < work_end,
            Schedule.end_time > work_start,
        )
        .order_by(Schedule.start_time.asc())
        .all()
    )

    intervals: List[Tuple[datetime, datetime]] = []
    for item in busy_items:
        s = max(item.start_time, work_start)
        e = min(item.end_time, work_end)
        if not intervals or s > intervals[-1][1]:
            intervals.append((s, e))
        else:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], e))

    slots: List[dict] = []
    cursor = work_start
    for s, e in intervals:
        gap = int((s - cursor).total_seconds() // 60)
        if gap >= duration_minutes:
            slots.append(
                {
                    "start_time": cursor,
                    "end_time": s,
                    "duration_minutes": gap,
                }
            )
        cursor = max(cursor, e)

    final_gap = int((work_end - cursor).total_seconds() // 60)
    if final_gap >= duration_minutes:
        slots.append(
            {
                "start_time": cursor,
                "end_time": work_end,
                "duration_minutes": final_gap,
            }
        )

    return slots


def get_dashboard_stats(db: Session, target_date: Optional[date] = None) -> dict:
    ref = target_date or date.today()
    day_start = datetime(ref.year, ref.month, ref.day, 0, 0, 0)
    day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
    week_end = day_start + timedelta(days=7)

    today_items = (
        db.query(Schedule)
        .filter(and_(Schedule.start_time <= day_end, Schedule.end_time >= day_start))
        .all()
    )
    today_done = sum(1 for x in today_items if x.status == "done")
    today_pending = sum(1 for x in today_items if x.status == "scheduled")

    high_priority_pending = (
        db.query(Schedule)
        .filter(Schedule.status == "scheduled", Schedule.priority == "high")
        .count()
    )
    upcoming_7_days = (
        db.query(Schedule)
        .filter(
            Schedule.status == "scheduled",
            Schedule.start_time >= day_start,
            Schedule.start_time <= week_end,
        )
        .count()
    )

    free_slots = find_free_slots(db, ref, duration_minutes=15)
    free_minutes_today = sum(s["duration_minutes"] for s in free_slots)
    total_documents = db.query(KnowledgeDocument).count()

    return {
        "today_total": len(today_items),
        "today_done": today_done,
        "today_pending": today_pending,
        "high_priority_pending": high_priority_pending,
        "upcoming_7_days": upcoming_7_days,
        "free_minutes_today": free_minutes_today,
        "total_documents": total_documents,
    }
