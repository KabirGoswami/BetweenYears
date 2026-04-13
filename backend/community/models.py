"""
Community Pydantic models
"""
from pydantic import BaseModel, field_validator
from typing import Optional


class CreateStoryRequest(BaseModel):
    content: str
    context_label: Optional[str] = None   # e.g. "3rd year, Engineering"
    tags: list[str] = []
    is_anonymous: bool = True
    journal_id: Optional[str] = None     # source journal entry

    @field_validator("content")
    @classmethod
    def content_length(cls, v):
        if len(v.strip()) < 20:
            raise ValueError("Story must be at least 20 characters")
        if len(v) > 2000:
            raise ValueError("Story must be under 2000 characters")
        return v.strip()


class ReactRequest(BaseModel):
    emoji: str = "❤️"


class FlagRequest(BaseModel):
    reason: Optional[str] = None


class StoryResponse(BaseModel):
    id: str
    content: str
    context_label: Optional[str]
    tags: Optional[list[str]]
    is_anonymous: bool
    reaction_count: int
    created_at: str
    # Author info (anonymous or display_name depending on is_anonymous)
    author_display: str


class StoriesListResponse(BaseModel):
    items: list[StoryResponse]
    total: int
    page: int
    page_size: int
