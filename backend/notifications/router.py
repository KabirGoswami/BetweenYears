"""
Notifications router — /notifications endpoints
"""
import hmac
import hashlib
import base64
from fastapi import APIRouter, Depends, Query, HTTPException
from database import get_admin_client
from notifications.models import UpdatePreferencesRequest, NotificationPreferences
import notifications.service as svc
from dependencies import get_current_user
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/preferences", response_model=NotificationPreferences)
async def get_preferences(user=Depends(get_current_user)):
    """Get notification preferences for the current user."""
    admin = get_admin_client()
    res = admin.table("notification_preferences").select("*").eq("user_id", user["id"]).single().execute()
    data = res.data or {}
    return NotificationPreferences(
        email_reminders=data.get("email_reminders", True),
        reminder_time=str(data.get("reminder_time", "09:00"))[:5],
        timezone=data.get("timezone", "UTC"),
        weekly_summary=data.get("weekly_summary", True),
        badge_alerts=data.get("badge_alerts", True),
        streak_alerts=data.get("streak_alerts", True),
    )


@router.patch("/preferences")
async def update_preferences(body: UpdatePreferencesRequest, user=Depends(get_current_user)):
    """Update notification preferences."""
    admin = get_admin_client()
    cleaned = {k: v for k, v in body.model_dump().items() if v is not None}
    if not cleaned:
        raise HTTPException(status_code=400, detail="Nothing to update")
    admin.table("notification_preferences").update(cleaned).eq("user_id", user["id"]).execute()
    return {"message": "Preferences updated"}


@router.post("/send-test")
async def send_test(user=Depends(get_current_user)):
    """Send a test reminder email to the current user."""
    admin = get_admin_client()
    profile = admin.table("user_profiles").select("display_name").eq("id", user["id"]).single().execute()
    name = (profile.data or {}).get("display_name", "there")
    await svc.send_daily_reminder(user["id"], user["email"], name)
    return {"message": "Test email queued"}


@router.get("/unsubscribe")
async def unsubscribe(uid: str = Query(...), token: str = Query(...)):
    """One-click unsubscribe link handler (no auth required)."""
    expected = base64.urlsafe_b64encode(
        hmac.new(settings.secret_key.encode(), uid.encode(), hashlib.sha256).digest()
    ).decode()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=400, detail="Invalid unsubscribe token")

    admin = get_admin_client()
    admin.table("notification_preferences").update({
        "email_reminders": False,
        "weekly_summary": False,
        "badge_alerts": False,
        "streak_alerts": False,
    }).eq("user_id", uid).execute()
    return {"message": "You have been unsubscribed from all BetweenYears emails."}
