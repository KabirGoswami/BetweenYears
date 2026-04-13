"""
Journal service — CRUD operations for journal entries
Also triggers streak updates and XP awards after saving.
"""
from fastapi import HTTPException
from database import get_admin_client


async def create_entry(user_id: str, data: dict) -> dict:
    admin = get_admin_client()
    payload = {
        "user_id": user_id,
        "content": data["content"],
        "mood": data.get("mood"),
        "prompt_id": data.get("prompt_id"),
        "prompt_text": data.get("prompt_text"),
        "is_public": data.get("is_public", False),
    }
    try:
        res = admin.table("journals").insert(payload).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save entry: {e}")


async def list_entries(user_id: str, page: int = 1, page_size: int = 20,
                       mood: str | None = None) -> dict:
    admin = get_admin_client()
    offset = (page - 1) * page_size

    query = (
        admin.table("journals")
        .select("*", count="exact")
        .eq("user_id", user_id)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
    )
    if mood:
        query = query.eq("mood", mood)
    try:
        res = query.execute()
        return {"items": res.data, "total": res.count or 0, "page": page, "page_size": page_size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch entries: {e}")


async def get_entry(entry_id: str, user_id: str) -> dict:
    admin = get_admin_client()
    try:
        res = (
            admin.table("journals")
            .select("*")
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .single()
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Entry not found")
        return res.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def update_entry(entry_id: str, user_id: str, updates: dict) -> dict:
    admin = get_admin_client()
    cleaned = {k: v for k, v in updates.items() if v is not None}
    if not cleaned:
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        res = (
            admin.table("journals")
            .update(cleaned)
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Entry not found")
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def delete_entry(entry_id: str, user_id: str) -> None:
    """Soft-delete by setting deleted_at timestamp."""
    admin = get_admin_client()
    from datetime import datetime, timezone
    try:
        res = (
            admin.table("journals")
            .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Entry not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_daily_prompt() -> dict:
    """Return a pseudo-random daily prompt based on the day of year."""
    admin = get_admin_client()
    from datetime import date
    day_of_year = date.today().timetuple().tm_yday
    try:
        res = admin.table("prompts").select("*").eq("is_active", True).execute()
        if not res.data:
            return {"id": None, "text": "What is one thing you're grateful for today?", "category": "daily"}
        idx = day_of_year % len(res.data)
        return res.data[idx]
    except Exception:
        return {"id": None, "text": "What is one thing you're grateful for today?", "category": "daily"}


async def get_random_prompt() -> dict:
    admin = get_admin_client()
    import random
    try:
        res = admin.table("prompts").select("*").eq("is_active", True).execute()
        if not res.data:
            return {"id": None, "text": "What would you tell your past self?", "category": "daily"}
        return random.choice(res.data)
    except Exception:
        return {"id": None, "text": "What would you tell your past self?", "category": "daily"}
