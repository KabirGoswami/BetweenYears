"""
Journal router — /journal endpoints
"""
from fastapi import APIRouter, Depends, Query, BackgroundTasks

from journal.models import (
    CreateJournalRequest, UpdateJournalRequest,
    JournalEntry, JournalListResponse, PromptResponse
)
import journal.service as svc
import streaks.service as streak_svc
import ai.service as ai_svc
from dependencies import get_current_user

router = APIRouter(prefix="/journal", tags=["Journal"])


@router.post("/", status_code=201)
async def create_entry(
    body: CreateJournalRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """Save a new journal entry. Triggers streak update and async AI analysis."""
    entry = await svc.create_entry(user["id"], body.model_dump())

    # Fire-and-forget: update streak + XP, then run AI analysis
    background_tasks.add_task(streak_svc.record_journal_entry, user["id"], entry["id"])
    background_tasks.add_task(ai_svc.analyze_entry_background, user["id"], entry["id"], entry["content"])

    return {"message": "Entry saved", "data": entry}


@router.get("/", response_model=JournalListResponse)
async def list_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mood: str | None = Query(None),
    user=Depends(get_current_user)
):
    """List own journal entries, newest first."""
    return await svc.list_entries(user["id"], page=page, page_size=page_size, mood=mood)


@router.get("/prompts/daily", response_model=PromptResponse)
async def daily_prompt():
    """Get today's curated reflection prompt."""
    return await svc.get_daily_prompt()


@router.get("/prompts/random", response_model=PromptResponse)
async def random_prompt():
    """Get a random reflection prompt."""
    return await svc.get_random_prompt()


@router.get("/{entry_id}")
async def get_entry(entry_id: str, user=Depends(get_current_user)):
    """Get a single journal entry."""
    return await svc.get_entry(entry_id, user["id"])


@router.patch("/{entry_id}")
async def update_entry(
    entry_id: str,
    body: UpdateJournalRequest,
    user=Depends(get_current_user)
):
    """Update content, mood, or visibility of an entry."""
    return await svc.update_entry(entry_id, user["id"], body.model_dump(exclude_none=True))


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(entry_id: str, user=Depends(get_current_user)):
    """Soft-delete a journal entry."""
    await svc.delete_entry(entry_id, user["id"])
