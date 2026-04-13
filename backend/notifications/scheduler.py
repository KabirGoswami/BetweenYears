"""
APScheduler background jobs — daily reminders, weekly summaries
Started by main.py on app startup.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import get_admin_client
import notifications.service as email_svc

scheduler = AsyncIOScheduler()


async def send_daily_reminders():
    """
    Runs every hour. Finds users whose preferred reminder time matches
    the current UTC hour and who haven't journaled today.
    """
    from datetime import date, datetime, timezone
    import pytz

    admin = get_admin_client()
    now_utc = datetime.now(timezone.utc)

    try:
        prefs_res = admin.table("notification_preferences").select(
            "user_id, reminder_time, timezone, email_reminders"
        ).eq("email_reminders", True).execute()

        for pref in (prefs_res.data or []):
            try:
                tz = pytz.timezone(pref.get("timezone", "UTC"))
                user_now = now_utc.astimezone(tz)
                reminder_hour = int(str(pref.get("reminder_time", "09:00"))[:2])

                if user_now.hour != reminder_hour:
                    continue

                # Check if already journaled today
                today = date.today().isoformat()
                journal_check = (
                    admin.table("journals")
                    .select("id", count="exact")
                    .eq("user_id", pref["user_id"])
                    .gte("created_at", today)
                    .is_("deleted_at", "null")
                    .execute()
                )
                if (journal_check.count or 0) > 0:
                    continue  # Already reflected today

                # Get user email and name
                user_res = admin.auth.admin.get_user_by_id(pref["user_id"])
                if not user_res.user:
                    continue
                profile_res = admin.table("user_profiles").select("display_name").eq(
                    "id", pref["user_id"]
                ).single().execute()
                name = (profile_res.data or {}).get("display_name", "there")

                await email_svc.send_daily_reminder(
                    pref["user_id"], user_res.user.email, name
                )
            except Exception:
                continue
    except Exception as e:
        print(f"[Scheduler] daily_reminders error: {e}")


async def send_streak_risk_alerts():
    """
    Runs at 20:00 UTC. Warns users with a streak ≥ 3 who haven't journaled today.
    """
    from datetime import date, timezone, datetime

    admin = get_admin_client()
    today = date.today().isoformat()

    try:
        streaks_res = admin.table("streaks").select(
            "user_id, current_streak"
        ).gte("current_streak", 3).execute()

        for row in (streaks_res.data or []):
            try:
                uid = row["user_id"]
                prefs = admin.table("notification_preferences").select(
                    "streak_alerts"
                ).eq("user_id", uid).single().execute()
                if not (prefs.data or {}).get("streak_alerts", True):
                    continue

                journal_check = (
                    admin.table("journals")
                    .select("id", count="exact")
                    .eq("user_id", uid)
                    .gte("created_at", today)
                    .is_("deleted_at", "null")
                    .execute()
                )
                if (journal_check.count or 0) > 0:
                    continue

                user_res = admin.auth.admin.get_user_by_id(uid)
                if not user_res.user:
                    continue
                profile_res = admin.table("user_profiles").select("display_name").eq("id", uid).single().execute()
                name = (profile_res.data or {}).get("display_name", "there")

                await email_svc.send_streak_at_risk(
                    uid, user_res.user.email, name, row["current_streak"]
                )
            except Exception:
                continue
    except Exception as e:
        print(f"[Scheduler] streak_risk error: {e}")


async def send_weekly_summaries():
    """Runs every Monday at 08:00 UTC."""
    from datetime import date, timedelta

    admin = get_admin_client()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    try:
        profiles_res = admin.table("user_profiles").select("id, display_name").execute()
        for profile in (profiles_res.data or []):
            uid = profile["id"]
            try:
                prefs = admin.table("notification_preferences").select(
                    "weekly_summary, email_reminders"
                ).eq("user_id", uid).single().execute()
                pref_data = prefs.data or {}
                if not pref_data.get("weekly_summary", True) or not pref_data.get("email_reminders", True):
                    continue

                entries_res = (
                    admin.table("journals")
                    .select("id", count="exact")
                    .eq("user_id", uid)
                    .gte("created_at", week_ago)
                    .is_("deleted_at", "null")
                    .execute()
                )
                entries = entries_res.count or 0
                if entries == 0:
                    continue

                streak_res = admin.table("streaks").select(
                    "current_streak, level"
                ).eq("user_id", uid).single().execute()
                streak_data = streak_res.data or {}

                user_res = admin.auth.admin.get_user_by_id(uid)
                if not user_res.user:
                    continue

                await email_svc.send_weekly_summary(
                    uid, user_res.user.email, profile.get("display_name", "there"),
                    entries, streak_data.get("current_streak", 0), streak_data.get("level", "Beginner")
                )
            except Exception:
                continue
    except Exception as e:
        print(f"[Scheduler] weekly_summary error: {e}")


def start_scheduler():
    scheduler.add_job(send_daily_reminders, CronTrigger(minute=0))              # Every hour
    scheduler.add_job(send_streak_risk_alerts, CronTrigger(hour=20, minute=0))  # 8pm UTC daily
    scheduler.add_job(send_weekly_summaries, CronTrigger(day_of_week="mon", hour=8, minute=0))
    scheduler.start()
    print("[Scheduler] Started background jobs")
