"""
AI Pydantic models
"""
from pydantic import BaseModel
from typing import Optional, List


class AnalyzeEntryRequest(BaseModel):
    content: str
    journal_id: Optional[str] = None


class DecisionAnalysisRequest(BaseModel):
    title: str
    pros: list[str] = []
    cons: list[str] = []


class GeneratePromptRequest(BaseModel):
    pass  # Uses user history from DB


class AIInsightResponse(BaseModel):
    themes: list[str]
    emotional_tone: Optional[str]
    summary: str
    follow_up_prompt: Optional[str]


class PatternResponse(BaseModel):
    recurring_themes: list[str]
    dominant_tone: Optional[str]
    pattern_summary: str
    suggestion: Optional[str]


class DecisionResponse(BaseModel):
    balance: str
    reflection: str
    question: str


class ChatMessage(BaseModel):
    role: str          # "user" | "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    emotional_tone: Optional[str] = None
