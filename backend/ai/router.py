"""
AI router — /ai endpoints
All endpoints require authentication and are rate-limited.
"""
from fastapi import APIRouter, Depends, Query
from slowapi import Limiter
from slowapi.util import get_remote_address

from ai.models import (
    AnalyzeEntryRequest, DecisionAnalysisRequest,
    AIInsightResponse, PatternResponse, DecisionResponse,
    ChatRequest, ChatResponse
)
import ai.service as svc
from dependencies import get_current_user
from config import get_settings

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/analyze", response_model=AIInsightResponse)
async def analyze_entry(body: AnalyzeEntryRequest, user=Depends(get_current_user)):
    """
    Analyze a journal entry or any free text.
    Returns themes, emotional tone, summary, and follow-up prompt.
    """
    return await svc.analyze_entry(user["id"], body.journal_id, body.content)


@router.post("/generate-prompt")
async def generate_prompt(user=Depends(get_current_user)):
    """Generate a personalized reflection prompt based on user's history."""
    return await svc.generate_prompt(user["id"])


@router.post("/decision", response_model=DecisionResponse)
async def analyze_decision(body: DecisionAnalysisRequest, user=Depends(get_current_user)):
    """
    Analyze a pros/cons list for a decision.
    Returns a reflective insight and follow-up question — not advice.
    """
    return await svc.analyze_decision(body.title, body.pros, body.cons)


@router.get("/patterns", response_model=PatternResponse)
async def get_patterns(
    limit: int = Query(10, ge=3, le=30),
    user=Depends(get_current_user)
):
    """
    Detect recurring themes and emotional patterns across recent journal entries.
    Requires at least 3 entries.
    """
    return await svc.get_patterns(user["id"], limit=limit)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
):
    """
    Multi-turn AI reflection chatbot powered by Gemini.
    Accessible to authenticated users AND guests.
    History is maintained on the client side and passed with each request.
    """
    result = await svc.chat_with_reflection_guide(
        message=body.message,
        history=[m.model_dump() for m in body.history]
    )
    return ChatResponse(**result)
