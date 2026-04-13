"""
Notifications Pydantic models
"""
from pydantic import BaseModel
from typing import Optional


class NotificationPreferences(BaseModel):
    email_reminders: bool = True
    reminder_time: str = "09:00"   # HH:MM local time
    timezone: str = "UTC"
    weekly_summary: bool = True
    badge_alerts: bool = True
    streak_alerts: bool = True


class UpdatePreferencesRequest(BaseModel):
    email_reminders: Optional[bool] = None
    reminder_time: Optional[str] = None
    timezone: Optional[str] = None
    weekly_summary: Optional[bool] = None
    badge_alerts: Optional[bool] = None
    streak_alerts: Optional[bool] = None
