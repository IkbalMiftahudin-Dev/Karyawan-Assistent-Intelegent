from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import UserProfile
from backend.schemas import ProfileOut, ProfileUpdate, AISettingsOut, AISettingsUpdate

router = APIRouter(prefix="/api", tags=["Profile & Settings"])


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": settings.db_name,
        "db_connected": db_ok,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.gemini_model,
        "server_time": datetime.now().isoformat(),
    }


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.put("/profile", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(profile, k, v)
    profile.updated_at = datetime.now()
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/settings/ai", response_model=AISettingsOut)
def get_ai_settings():
    key = settings.gemini_api_key
    return AISettingsOut(
        gemini_configured=bool(key),
        gemini_key_masked=_mask_key(key),
        gemini_model=settings.gemini_model,
        db_name=settings.db_name,
        db_host=f"{settings.db_host}:{settings.db_port}",
    )


@router.put("/settings/ai", response_model=AISettingsOut)
def update_ai_settings(payload: AISettingsUpdate):
    settings.update_ai_settings(
        api_key=payload.gemini_api_key,
        model=payload.gemini_model,
    )
    key = settings.gemini_api_key
    return AISettingsOut(
        gemini_configured=bool(key),
        gemini_key_masked=_mask_key(key),
        gemini_model=settings.gemini_model,
        db_name=settings.db_name,
        db_host=f"{settings.db_host}:{settings.db_port}",
    )
