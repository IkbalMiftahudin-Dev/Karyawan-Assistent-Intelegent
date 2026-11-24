from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from backend.database import Base


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False, default="Karyawan Pribadi")
    role_title = Column(String(120), nullable=False, default="Staff / Professional")
    department = Column(String(120), nullable=False, default="Umum")
    work_start = Column(String(5), nullable=False, default="08:30")
    work_end = Column(String(5), nullable=False, default="17:30")
    timezone = Column(String(64), nullable=False, default="Asia/Jakarta")
    preferences_note = Column(Text, nullable=True, default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True, default="")
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    category = Column(String(40), nullable=False, default="meeting")  # meeting, deep_work, deadline, personal, reminder
    priority = Column(String(20), nullable=False, default="medium")  # high, medium, low
    status = Column(String(20), nullable=False, default="scheduled")  # scheduled, done, cancelled
    location = Column(String(200), nullable=True, default="")
    reminder_minutes = Column(Integer, nullable=False, default=15)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    category = Column(String(80), nullable=False, default="SOP Umum")
    filename = Column(String(255), nullable=True, default="")
    content = Column(LONGTEXT, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), nullable=False, default="default", index=True)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(LONGTEXT, nullable=False)
    tool_actions_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
