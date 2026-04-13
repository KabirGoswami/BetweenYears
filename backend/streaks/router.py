"""
Streaks router — /streaks endpoints
"""
from fastapi import APIRouter, Depends
import streaks.service as svc
from dependencies import get_current_user

router = APIRouter(prefix="/streaks", tags=["Streaks & Gamification"])


@router.get("/me")
async def get_my_streak(user=Depends(get_current_user)):
    """Get current streak, XP, level, and progress."""
    return await svc.get_streak_data(user["id"])


@router.get("/badges")
async def get_badges(user=Depends(get_current_user)):
    """Get all badges with earned/locked status for current user."""
    return await svc.get_badges(user["id"])


@router.post("/values-complete", status_code=200)
async def values_test_complete(user=Depends(get_current_user)):
    """Award Values Explorer badge when user completes the values test."""
    await svc.award_values_badge(user["id"])
    return {"message": "Values badge awarded!", "badge": "values_explorer"}
