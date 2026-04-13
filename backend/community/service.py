"""
Community service — community stories CRUD
Privacy: stories are anonymous by default.
"""
from fastapi import HTTPException
from database import get_admin_client


async def list_stories(page: int = 1, page_size: int = 20, tag: str | None = None) -> dict:
    admin = get_admin_client()
    offset = (page - 1) * page_size
    try:
        query = (
            admin.table("community_stories")
            .select("*, user_profiles!inner(display_name)", count="exact")
            .eq("status", "active")
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
        )
        if tag:
            query = query.contains("tags", [tag])

        res = query.execute()
        items = []
        for s in (res.data or []):
            profile = s.get("user_profiles") or {}
            author_display = "Anonymous student" if s.get("is_anonymous") else (profile.get("display_name") or "A student")
            items.append({
                "id": s["id"],
                "content": s["content"],
                "context_label": s.get("context_label"),
                "tags": s.get("tags") or [],
                "is_anonymous": s.get("is_anonymous", True),
                "reaction_count": s.get("reaction_count", 0),
                "created_at": str(s["created_at"]),
                "author_display": author_display,
            })
        return {"items": items, "total": res.count or 0, "page": page, "page_size": page_size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_story(story_id: str) -> dict:
    admin = get_admin_client()
    try:
        res = (
            admin.table("community_stories")
            .select("*, user_profiles!inner(display_name)")
            .eq("id", story_id)
            .eq("status", "active")
            .single()
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Story not found")
        s = res.data
        profile = s.get("user_profiles") or {}
        author_display = "Anonymous student" if s.get("is_anonymous") else (profile.get("display_name") or "A student")
        return {**s, "author_display": author_display, "user_profiles": None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def create_story(user_id: str, data: dict) -> dict:
    admin = get_admin_client()
    payload = {
        "user_id": user_id,
        "content": data["content"],
        "context_label": data.get("context_label"),
        "tags": data.get("tags", []),
        "is_anonymous": data.get("is_anonymous", True),
        "journal_id": data.get("journal_id"),
    }
    try:
        res = admin.table("community_stories").insert(payload).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def react_to_story(story_id: str, user_id: str, emoji: str) -> dict:
    admin = get_admin_client()
    try:
        # Upsert reaction (one per user per story)
        admin.table("story_reactions").upsert(
            {"story_id": story_id, "user_id": user_id, "emoji": emoji},
            on_conflict="story_id,user_id"
        ).execute()

        # Recalculate reaction count
        count_res = (
            admin.table("story_reactions")
            .select("id", count="exact")
            .eq("story_id", story_id)
            .execute()
        )
        count = count_res.count or 0
        admin.table("community_stories").update({
            "reaction_count": count
        }).eq("id", story_id).execute()

        return {"story_id": story_id, "reaction_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def flag_story(story_id: str, user_id: str, reason: str | None) -> dict:
    admin = get_admin_client()
    try:
        admin.table("story_flags").upsert(
            {"story_id": story_id, "user_id": user_id, "reason": reason},
            on_conflict="story_id,user_id"
        ).execute()

        # Increment flag count
        story = admin.table("community_stories").select("flag_count").eq("id", story_id).single().execute()
        flag_count = (story.data or {}).get("flag_count", 0) + 1
        update_payload = {"flag_count": flag_count}
        # Auto-remove after 5 flags
        if flag_count >= 5:
            update_payload["status"] = "flagged"
        admin.table("community_stories").update(update_payload).eq("id", story_id).execute()

        return {"flagged": True, "flag_count": flag_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def delete_story(story_id: str, user_id: str) -> None:
    admin = get_admin_client()
    try:
        res = (
            admin.table("community_stories")
            .update({"status": "removed"})
            .eq("id", story_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Story not found or not yours")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
