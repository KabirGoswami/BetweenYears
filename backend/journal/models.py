"""
Journal Pydantic models
"""
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import uuid


class CreateJournalRequest(BaseModel):
    content: str
    prompt_id: Optional[str] = None
    prompt_text: Optional[str] = None
    mood: Optional[str] = None  # calm | anxious | hopeful | confused | motivated
    is_public: bool = False

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError("Journal entry must be at least 5 characters")
        return v.strip()

    @field_validator("mood")
    @classmethod
    def valid_mood(cls, v):
        if v and v not in ("calm", "anxious", "hopeful", "confused", "motivated"):
            raise ValueError("Invalid mood value")
        return v


class UpdateJournalRequest(BaseModel):
    content: Optional[str] = None
    mood: Optional[str] = None
    is_public: Optional[bool] = None


class JournalEntry(BaseModel):
    id: str
    user_id: str
    prompt_id: Optional[str]
    prompt_text: Optional[str]
    content: str
    mood: Optional[str]
    word_count: Optional[int]
    is_public: bool
    ai_analyzed: bool
    created_at: str
    updated_at: str


class JournalListResponse(BaseModel):
    items: list[JournalEntry]
    total: int
    page: int
    page_size: int


class PromptResponse(BaseModel):
    id: str
    text: str
    category: str
