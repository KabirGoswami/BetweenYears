"""
Privacy router + service — GDPR compliance
Endpoints: data export, account deletion, privacy settings, data summary
"""
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_admin_client
from dependencies import get_current_user
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/privacy", tags=["Privacy"])


class PrivacySettingsUpdate(BaseModel):
    journal_private: Optional[bool] = None
    analytics_opt_in: Optional[bool] = None
    community_anonymous: Optional[bool] = None


@router.get("/settings")
async def get_privacy_settings(user=Depends(get_current_user)):
    """Get current privacy settings."""
    admin = get_admin_client()
    res = admin.table("user_profiles").select(
        "journal_private, analytics_opt_in, community_anonymous"
    ).eq("id", user["id"]).single().execute()
    return res.data or {}


@router.patch("/settings")
async def update_privacy_settings(body: PrivacySettingsUpdate, user=Depends(get_current_user)):
    """Update privacy preferences."""
    admin = get_admin_client()
    cleaned = {k: v for k, v in body.model_dump().items() if v is not None}
    if not cleaned:
        raise HTTPException(status_code=400, detail="Nothing to update")
    admin.table("user_profiles").update(cleaned).eq("id", user["id"]).execute()
    return {"message": "Privacy settings updated", "updated": cleaned}


@router.get("/data-summary")
async def data_summary(user=Depends(get_current_user)):
    """
    GDPR Article 15: Show user what data we hold.
    Returns counts — not raw data — for quick overview.
    """
    admin = get_admin_client()
    uid = user["id"]

    try:
        journals = admin.table("journals").select("id", count="exact").eq("user_id", uid).is_("deleted_at", "null").execute()
        insights = admin.table("ai_insights").select("id", count="exact").eq("user_id", uid).execute()
        stories  = admin.table("community_stories").select("id", count="exact").eq("user_id", uid).eq("status", "active").execute()
        badges   = admin.table("user_badges").select("id", count="exact").eq("user_id", uid).execute()
        streak   = admin.table("streaks").select("*").eq("user_id", uid).single().execute()
        notif    = admin.table("notification_preferences").select("*").eq("user_id", uid).single().execute()

        return {
            "data_held": {
                "journal_entries":      journals.count or 0,
                "ai_insights":          insights.count or 0,
                "community_stories":    stories.count or 0,
                "badges_earned":        badges.count or 0,
            },
            "streak_data":             streak.data or {},
            "notification_preferences": notif.data or {},
            "data_not_stored": [
                "Raw journal content is never sent to third parties",
                "Gemini AI receives anonymized reflections only — no name, email, or PII",
                "We do not sell or share your data",
                "Community stories are anonymous unless you opted out of anonymity",
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def request_export(user=Depends(get_current_user)):
    """
    GDPR Article 20: Queue a full data export.
    Returns a request ID — in production, an email with a download link is sent.
    """
    admin = get_admin_client()
    uid = user["id"]

    # Check for pending request to prevent duplicates
    existing = (
        admin.table("privacy_requests")
        .select("id, status")
        .eq("user_id", uid)
        .eq("type", "export")
        .in_("status", ["pending", "processing"])
        .execute()
    )
    if existing.data:
        return {"message": "Export already in progress", "request_id": existing.data[0]["id"]}

    req = admin.table("privacy_requests").insert({
        "user_id": uid,
        "type": "export",
        "status": "pending"
    }).execute()

    # In production: trigger async export worker
    # For now: generate inline and return
    try:
        export_data = await _build_export(uid)
        return {
            "message": "Your data export is ready",
            "request_id": req.data[0]["id"],
            "data": export_data,
            "note": "In production, a secure download link is emailed to you."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


@router.delete("/delete-account")
async def request_account_deletion(user=Depends(get_current_user)):
    """
    GDPR Article 17: Request full account and data deletion.
    Immediately deletes all user data. Auth account deleted last.
    This action is irreversible.
    """
    admin = get_admin_client()
    uid = user["id"]

    try:
        # Delete in order (cascade will handle most, but explicit is safer)
        for table in [
            "ai_insights", "xp_events", "user_badges",
            "story_flags", "story_reactions", "community_stories",
            "journals", "notification_preferences",
            "streaks", "privacy_requests", "user_profiles"
        ]:
            admin.table(table).delete().eq("user_id", uid).execute()

        # Delete the Supabase Auth account last
        admin.auth.admin.delete_user(uid)

        return {"message": "Your account and all associated data have been permanently deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")


async def _build_export(user_id: str) -> dict:
    """Build a full JSON export of all user data."""
    admin = get_admin_client()

    profile  = admin.table("user_profiles").select("*").eq("id", user_id).single().execute()
    journals = admin.table("journals").select("*").eq("user_id", user_id).is_("deleted_at", "null").execute()
    insights = admin.table("ai_insights").select("*").eq("user_id", user_id).execute()
    streak   = admin.table("streaks").select("*").eq("user_id", user_id).single().execute()
    badges   = admin.table("user_badges").select("*, badges(*)").eq("user_id", user_id).execute()
    stories  = admin.table("community_stories").select("*").eq("user_id", user_id).execute()
    notif    = admin.table("notification_preferences").select("*").eq("user_id", user_id).single().execute()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile":     profile.data,
        "journals":    journals.data,
        "ai_insights": insights.data,
        "streak":      streak.data,
        "badges":      badges.data,
        "community_stories": stories.data,
        "notification_preferences": notif.data,
    }
