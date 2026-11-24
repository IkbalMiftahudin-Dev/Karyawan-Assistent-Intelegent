import json
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ChatMessage
from backend.schemas import ChatRequest, ChatResponse, ChatMessageOut, ToolActionOut
from backend.services import gemini_service

router = APIRouter(prefix="/api/chat", tags=["AI Assistant"])


@router.get("/history", response_model=List[ChatMessageOut])
def get_history(
    session_id: str = Query("default"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .limit(limit)
        .all()
    )
    result = []
    for r in rows:
        actions = []
        if r.tool_actions_json:
            try:
                parsed = json.loads(r.tool_actions_json)
                actions = [ToolActionOut(**a) for a in parsed]
            except Exception:
                actions = []
        result.append(
            ChatMessageOut(
                id=r.id,
                session_id=r.session_id,
                role=r.role,
                content=r.content,
                tool_actions=actions,
                created_at=r.created_at,
            )
        )
    return result


@router.delete("/history")
def clear_history(
    session_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    deleted = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return {"cleared": True, "deleted_count": deleted}


@router.post("", response_model=ChatResponse)
def send_message(payload: ChatRequest, db: Session = Depends(get_db)):
    res = gemini_service.chat_with_assistant(
        db=db,
        user_message=payload.message,
        session_id=payload.session_id,
    )
    return ChatResponse(**res)


@router.get("/briefing")
def get_daily_briefing(db: Session = Depends(get_db)):
    return gemini_service.generate_daily_briefing(db)
