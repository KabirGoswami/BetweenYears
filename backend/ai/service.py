"""
AI service — Gemini integration for BetweenYears
Uses the new google-genai SDK (google.genai).
All prompts are structured to be:
  - Reflective, not directive
  - Safe for teens
  - Non-judgmental
  - No PII sent to Gemini
"""
import re
import json
from google import genai
from google.genai import types
from fastapi import HTTPException
from config import get_settings
from database import get_admin_client

settings = get_settings()

# Lazy singleton client
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


MODEL = "gemini-2.0-flash"

SYSTEM_INSTRUCTION = """You are a compassionate reflection guide for BetweenYears, a journaling app for 
teens and college students navigating life transitions.

Your role is ONLY to help users reflect — not to give advice, diagnose, or prescribe actions.
Always respond like a thoughtful mirror, not a counselor.

Rules:
- Never give direct advice or tell the user what to do.
- Never make diagnoses or clinical statements.
- Be warm, curious, and non-judgmental.
- Respond concisely — 2-4 sentences max unless asked for more.
- For safety: if content suggests self-harm or crisis, gently refer to a trusted adult or counselor.
- You are not a therapist. This is a reflection tool only.
"""

SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT",  threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",          threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT",   threshold="BLOCK_MEDIUM_AND_ABOVE"),
]


def _generate(prompt: str) -> str:
    """Synchronous Gemini call — runs in background tasks."""
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            safety_settings=SAFETY_SETTINGS,
            temperature=0.7,
        )
    )
    return response.text.strip()


def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON."""
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


async def analyze_entry(user_id: str, journal_id: str | None, content: str) -> dict:
    """
    Analyze a journal entry: themes, emotional tone, follow-up prompt.
    Stores result in ai_insights table.
    """
    prompt = f"""Analyze this reflection entry and respond in JSON format only.

Entry:
\"\"\"
{content[:2000]}
\"\"\"

Respond ONLY with valid JSON like this:
{{
  "themes": ["theme1", "theme2"],
  "emotional_tone": "one of: reflective | hopeful | anxious | uncertain | motivated | sad | confused | calm",
  "summary": "2-3 sentence empathetic summary of what this person is working through",
  "follow_up_prompt": "A single open-ended reflective question to deepen their thinking"
}}"""

    try:
        raw = _generate(prompt)
        parsed = _parse_json(raw)
    except Exception:
        parsed = {
            "themes": [],
            "emotional_tone": "reflective",
            "summary": "Your reflection has been saved.",
            "follow_up_prompt": "What else is on your mind about this?"
        }

    # Persist insight to DB
    admin = get_admin_client()
    try:
        insight_payload = {
            "user_id": user_id,
            "journal_id": journal_id,
            "insight_type": "entry_analysis",
            "themes": parsed.get("themes", []),
            "emotional_tone": parsed.get("emotional_tone"),
            "summary": parsed.get("summary", ""),
            "follow_up_prompt": parsed.get("follow_up_prompt"),
            "raw_response": parsed,
        }
        admin.table("ai_insights").insert(insight_payload).execute()

        if journal_id:
            admin.table("journals").update({"ai_analyzed": True}).eq("id", journal_id).execute()

        await _maybe_award_xp(user_id, "ai_analysis", 5)
        await _check_pattern_seeker_badge(user_id)

    except Exception:
        pass

    return parsed


async def analyze_entry_background(user_id: str, journal_id: str, content: str):
    """Background task wrapper for entry analysis."""
    try:
        await analyze_entry(user_id, journal_id, content)
    except Exception:
        pass


async def generate_prompt(user_id: str) -> dict:
    """Generate a personalized prompt based on user's recent themes."""
    admin = get_admin_client()

    try:
        res = (
            admin.table("ai_insights")
            .select("themes, emotional_tone")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        recent = res.data or []
    except Exception:
        recent = []

    all_themes = []
    tones = []
    for r in recent:
        all_themes.extend(r.get("themes") or [])
        if r.get("emotional_tone"):
            tones.append(r["emotional_tone"])

    themes_str = ", ".join(set(all_themes[:10])) if all_themes else "growth, clarity, direction"
    tone_str = tones[0] if tones else "reflective"

    prompt = f"""Generate a single, thoughtful journal reflection prompt for a student.
    
Their recent themes: {themes_str}
Their current emotional tone: {tone_str}

The prompt should:
- Be open-ended and introspective
- Not be advice-giving
- Be 1-2 sentences max
- Feel personally relevant to their themes

Respond with ONLY the prompt text, nothing else."""

    try:
        prompt_text = _generate(prompt).strip().strip('"')
    except Exception:
        prompt_text = "What is one thing you've been putting off thinking about, and what might that reveal?"

    try:
        saved = admin.table("prompts").insert({
            "text": prompt_text,
            "category": "ai-generated",
            "is_active": True
        }).execute()
        prompt_id = saved.data[0]["id"] if saved.data else None
    except Exception:
        prompt_id = None

    return {"id": prompt_id, "text": prompt_text, "category": "ai-generated"}


async def analyze_decision(title: str, pros: list[str], cons: list[str]) -> dict:
    """Analyze a decision's pros and cons and return a reflective insight."""
    if not pros and not cons:
        raise HTTPException(status_code=400, detail="Add at least one pro or con first")

    pros_str = "\n".join(f"- {p}" for p in pros) or "None listed"
    cons_str = "\n".join(f"- {c}" for c in cons) or "None listed"

    prompt = f"""A student is weighing this decision: "{title}"

Pros:
{pros_str}

Cons:
{cons_str}

Respond in JSON only:
{{
  "balance": "pros_heavier | cons_heavier | balanced",
  "reflection": "2-3 sentence empathetic observation about what this list reveals — do NOT give advice",
  "question": "A single reflective question to help them decide based on their own values"
}}"""

    try:
        raw = _generate(prompt)
        return _parse_json(raw)
    except Exception:
        return {
            "balance": "balanced",
            "reflection": "Both sides seem to carry real weight for you.",
            "question": "Which side feels more true to who you want to become?"
        }


async def get_patterns(user_id: str, limit: int = 10) -> dict:
    """Summarize patterns across recent journal entries."""
    admin = get_admin_client()

    try:
        res = (
            admin.table("ai_insights")
            .select("themes, emotional_tone, summary, created_at")
            .eq("user_id", user_id)
            .eq("insight_type", "entry_analysis")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        insights = res.data or []
    except Exception:
        insights = []

    if not insights:
        return {
            "recurring_themes": [],
            "dominant_tone": None,
            "pattern_summary": "Not enough entries yet to detect patterns. Keep reflecting!",
            "suggestion": "Write at least 3 entries to unlock pattern insights."
        }

    all_themes = []
    for i in insights:
        all_themes.extend(i.get("themes") or [])
    tone_counts: dict[str, int] = {}
    for i in insights:
        t = i.get("emotional_tone")
        if t:
            tone_counts[t] = tone_counts.get(t, 0) + 1

    dominant_tone = max(tone_counts, key=tone_counts.get) if tone_counts else None
    summaries = "\n".join(f"- {i['summary']}" for i in insights[:5] if i.get("summary"))

    prompt = f"""Based on these recent reflection summaries for a student:

{summaries}

Recurring themes noticed: {', '.join(set(all_themes[:15]))}
Dominant emotional tone: {dominant_tone}

Respond in JSON:
{{
  "recurring_themes": ["theme1", "theme2", "theme3"],
  "dominant_tone": "{dominant_tone}",
  "pattern_summary": "2-3 sentence compassionate summary of what you notice across their reflections",
  "suggestion": "One gentle reflective area they might want to explore next"
}}"""

    try:
        raw = _generate(prompt)
        return _parse_json(raw)
    except Exception:
        from collections import Counter
        top_themes = [t for t, _ in Counter(all_themes).most_common(5)]
        return {
            "recurring_themes": top_themes,
            "dominant_tone": dominant_tone,
            "pattern_summary": "You've been reflecting consistently — that takes courage.",
            "suggestion": "Consider what common thread runs through your entries."
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _maybe_award_xp(user_id: str, source: str, amount: int):
    admin = get_admin_client()
    try:
        admin.table("xp_events").insert({
            "user_id": user_id, "source": source, "amount": amount
        }).execute()
        streak = admin.table("streaks").select("total_xp").eq("user_id", user_id).single().execute()
        current = streak.data.get("total_xp", 0) if streak.data else 0
        new_xp = current + amount
        level = _xp_to_level(new_xp)
        admin.table("streaks").update({"total_xp": new_xp, "level": level}).eq("user_id", user_id).execute()
    except Exception:
        pass


def _xp_to_level(xp: int) -> str:
    if xp < 100:    return "Beginner"
    if xp < 500:    return "Explorer"
    if xp < 1500:   return "Discoverer"
    if xp < 4000:   return "Thinker"
    return "Sage"


async def _check_pattern_seeker_badge(user_id: str):
    admin = get_admin_client()
    try:
        count_res = (
            admin.table("ai_insights")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("insight_type", "entry_analysis")
            .execute()
        )
        if (count_res.count or 0) >= 5:
            badge = admin.table("badges").select("id").eq("slug", "pattern_seeker").single().execute()
            if badge.data:
                admin.table("user_badges").upsert({
                    "user_id": user_id, "badge_id": badge.data["id"]
                }, on_conflict="user_id,badge_id").execute()
    except Exception:
        pass


CHAT_SYSTEM_INSTRUCTION = """You are Luna, a warm and empathetic AI reflection guide for BetweenYears — 
a journaling app for teens and college students navigating life's in-between moments.

Your purpose:
- Help students reflect on their thoughts, feelings, and experiences.
- Ask thoughtful, open-ended follow-up questions to deepen their thinking.
- Mirror back what you hear without judgment or prescribing solutions.
- Celebrate their courage and honesty.

Your personality:
- Warm, curious, and genuinely interested in their inner world.
- Conversational and natural — like a wise, supportive friend.
- Concise: 2-5 sentences per response unless they ask for more.

Strict rules:
- Never give direct advice. Ask questions instead.
- Do not diagnose or make clinical statements.
- If someone hints at self-harm or crisis: gently say "That sounds really hard. It means a lot that you're sharing this. Please reach out to someone you trust, or a counselor — your feelings deserve real support."
- Stay on topics related to personal reflection, growth, emotions, goals, and student life.
- If asked about unrelated topics, gently redirect: "I'm here to help you reflect on your world — what's on your mind today?"
- You are NOT a therapist.
"""


async def chat_with_reflection_guide(message: str, history: list[dict]) -> dict:
    """
    Multi-turn conversational chat using Gemini.
    history is a list of {"role": "user"|"model", "parts": [{"text": ..."}]}
    Returns {"reply": str, "emotional_tone": str|None}
    """
    client = _get_client()

    # Build contents list from history + new message
    contents = []
    for turn in history:
        role = turn.get("role", "user")
        text = turn.get("content", "")
        if text:
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=text)]
            ))

    # Add the new user message
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=message)]
    ))

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=CHAT_SYSTEM_INSTRUCTION,
                safety_settings=SAFETY_SETTINGS,
                temperature=0.85,
                max_output_tokens=400,
            )
        )
        reply = response.text.strip() if response.text else "I'm here with you. Tell me more."
    except Exception as e:
        print(f"[Chat Error] {e}")
        reply = "I'm here with you. Sometimes words are hard to find — what are you feeling right now?"

    # Quick tone inference from keywords for UI hints
    lower = message.lower()
    tone = None
    if any(w in lower for w in ["anxious", "worried", "stress", "scared", "fear"]):
        tone = "anxious"
    elif any(w in lower for w in ["happy", "excited", "great", "amazing", "love"]):
        tone = "hopeful"
    elif any(w in lower for w in ["confused", "lost", "unsure", "don't know"]):
        tone = "confused"
    elif any(w in lower for w in ["motivated", "ready", "goal", "plan", "determined"]):
        tone = "motivated"
    elif any(w in lower for w in ["calm", "peaceful", "okay", "fine"]):
        tone = "calm"

    return {"reply": reply, "emotional_tone": tone}
