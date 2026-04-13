"""
Community router — /community/stories endpoints
"""
from fastapi import APIRouter, Depends, Query
import community.service as svc
import streaks.service as streak_svc
from community.models import CreateStoryRequest, ReactRequest, FlagRequest
from dependencies import get_current_user

router = APIRouter(prefix="/community", tags=["Community"])


@router.get("/stories")
async def list_stories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    tag: str | None = Query(None),
    user=Depends(get_current_user)
):
    """List active community stories, newest first. Optionally filter by tag."""
    return await svc.list_stories(page=page, page_size=page_size, tag=tag)


@router.post("/stories", status_code=201)
async def create_story(body: CreateStoryRequest, user=Depends(get_current_user)):
    """Share a story to the community (anonymous by default)."""
    story = await svc.create_story(user["id"], body.model_dump())
    # Award Community Voice badge
    import asyncio
    asyncio.create_task(streak_svc._award_badge_if_not_earned(user["id"], "community_voice"))
    return {"message": "Story shared", "data": story}


@router.get("/stories/{story_id}")
async def get_story(story_id: str, user=Depends(get_current_user)):
    """Get a single community story."""
    return await svc.get_story(story_id)


@router.post("/stories/{story_id}/react")
async def react(story_id: str, body: ReactRequest, user=Depends(get_current_user)):
    """React to a community story."""
    return await svc.react_to_story(story_id, user["id"], body.emoji)


@router.post("/stories/{story_id}/flag")
async def flag(story_id: str, body: FlagRequest, user=Depends(get_current_user)):
    """Flag a community story as inappropriate."""
    return await svc.flag_story(story_id, user["id"], body.reason)


@router.delete("/stories/{story_id}", status_code=204)
async def delete_story(story_id: str, user=Depends(get_current_user)):
    """Remove your own story from the community feed."""
    await svc.delete_story(story_id, user["id"])
