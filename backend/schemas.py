from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


# --- Profile & Settings ---
class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role_title: str
    department: str
    work_start: str
    work_end: str
    timezone: str
    preferences_note: Optional[str] = ""
    updated_at: Optional[datetime] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=120)
    role_title: Optional[str] = Field(None, max_length=120)
    department: Optional[str] = Field(None, max_length=120)
    work_start: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    work_end: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: Optional[str] = Field(None, max_length=64)
    preferences_note: Optional[str] = None


class AISettingsOut(BaseModel):
    gemini_configured: bool
    gemini_key_masked: str
    gemini_model: str
    db_name: str
    db_host: str


class AISettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None


# --- Schedules ---
class ScheduleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    start_time: datetime
    end_time: datetime
    category: str = Field("meeting", pattern=r"^(meeting|deep_work|deadline|personal|reminder)$")
    priority: str = Field("medium", pattern=r"^(high|medium|low)$")
    status: str = Field("scheduled", pattern=r"^(scheduled|done|cancelled)$")
    location: Optional[str] = ""
    reminder_minutes: int = Field(15, ge=0, le=1440)


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    category: Optional[str] = Field(None, pattern=r"^(meeting|deep_work|deadline|personal|reminder)$")
    priority: Optional[str] = Field(None, pattern=r"^(high|medium|low)$")
    status: Optional[str] = Field(None, pattern=r"^(scheduled|done|cancelled)$")
    location: Optional[str] = None
    reminder_minutes: Optional[int] = Field(None, ge=0, le=1440)


class ScheduleOut(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConflictBrief(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime


class ScheduleMutationResponse(BaseModel):
    schedule: ScheduleOut
    conflicts: List[ConflictBrief] = []
    has_conflict: bool = False


class FreeSlotOut(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_minutes: int


class DashboardStatsOut(BaseModel):
    today_total: int
    today_done: int
    today_pending: int
    high_priority_pending: int
    upcoming_7_days: int
    free_minutes_today: int
    total_documents: int


# --- Knowledge Base ---
class KnowledgeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: str = Field("SOP Umum", max_length=80)
    content: str = Field(..., min_length=1)


class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    filename: Optional[str] = ""
    content: str
    created_at: Optional[datetime] = None


# --- Chat ---
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field("default", max_length=64)


class ToolActionOut(BaseModel):
    tool: str
    summary: str
    data: Optional[Any] = None


class ChatMessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    tool_actions: List[ToolActionOut] = []
    created_at: datetime


class ChatResponse(BaseModel):
    reply: str
    tool_actions: List[ToolActionOut] = []
    schedules_modified: bool = False
    ai_powered: bool = True
    message_id: int
