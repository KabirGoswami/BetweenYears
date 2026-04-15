"""
Streaks & Gamification service
Handles: streak tracking, XP awards, badge unlocking, levels
"""
from datetime import date, datetime, timezone, timedelta
from fastapi import HTTPException
from database import get_admin_client


# ── XP values ──────────────────────────────────────────────────────────────
XP_JOURNAL_ENTRY   = 10
XP_MOOD_LOG        = 5
XP_STREAK_3        = 30
XP_STREAK_10       = 75
XP_STREAK_30       = 200
XP_BADGE           = 50


def _xp_to_level(xp: int) -> str:
    if xp < 100:  return "Beginner"
    if xp < 500:  return "Explorer"
    if xp < 1500: return "Discoverer"
    if xp < 4000: return "Thinker"
    return "Sage"


def _next_level_xp(xp: int) -> int:
    thresholds = [100, 500, 1500, 4000]
    for t in thresholds:
        if xp < t:
            return t
    return xp  # Already Sage


async def record_journal_entry(user_id: str, journal_id: str):
    """
    Called after every new journal entry:
    1. Update streak
    2. Award journal XP
    3. Check badges
    """
    admin = get_admin_client()
    today = date.today()

    try:
        streak_res = admin.table("streaks").select("*").eq("user_id", user_id).single().execute()
        streak = streak_res.data or {}
    except Exception:
        streak = {}

    last_date_str = streak.get("last_entry_date")
    current_streak = streak.get("current_streak", 0)
    longest_streak = streak.get("longest_streak", 0)
    total_entries  = streak.get("total_entries", 0)
    total_xp       = streak.get("total_xp", 0)

    # Streak logic
    if last_date_str:
        last_date = date.fromisoformat(str(last_date_str))
        delta = (today - last_date).days
        if delta == 0:
            # Already journaled today — no streak change
            pass
        elif delta == 1:
            # Consecutive day
            current_streak += 1
        elif delta <= 2:
            # Grace period (missed 1 day) — keep streak but don't increment
            pass
        else:
            # Streak broken
            current_streak = 1
    else:
        current_streak = 1

    total_entries += 1
    longest_streak = max(longest_streak, current_streak)

    # Award XP for the entry
    total_xp += XP_JOURNAL_ENTRY
    xp_source_payload = {
        "user_id": user_id, "source": "journal_entry",
        "amount": XP_JOURNAL_ENTRY, "metadata": {"journal_id": journal_id}
    }

    # Streak milestone XP
    streak_xp_awarded = 0
    if current_streak == 3:
        streak_xp_awarded = XP_STREAK_3
    elif current_streak == 10:
        streak_xp_awarded = XP_STREAK_10
    elif current_streak == 30:
        streak_xp_awarded = XP_STREAK_30

    if streak_xp_awarded:
        total_xp += streak_xp_awarded

    level = _xp_to_level(total_xp)

    # Upsert streak record
    admin.table("streaks").upsert({
        "user_id": user_id,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_entry_date": today.isoformat(),
        "total_entries": total_entries,
        "total_xp": total_xp,
        "level": level,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    # Log XP events
    xp_events = [xp_source_payload]
    if streak_xp_awarded:
        xp_events.append({
            "user_id": user_id, "source": "streak_milestone",
            "amount": streak_xp_awarded, "metadata": {"streak": current_streak}
        })
    admin.table("xp_events").insert(xp_events).execute()

    # Check badges
    await _check_and_award_badges(user_id, current_streak, total_entries)


async def record_mood_log(user_id: str):
    """Award XP for logging a mood."""
    admin = get_admin_client()
    try:
        streak = admin.table("streaks").select("total_xp").eq("user_id", user_id).single().execute()
        current_xp = (streak.data or {}).get("total_xp", 0)
        new_xp = current_xp + XP_MOOD_LOG
        admin.table("xp_events").insert({
            "user_id": user_id, "source": "mood_log", "amount": XP_MOOD_LOG
        }).execute()
        admin.table("streaks").update({
            "total_xp": new_xp, "level": _xp_to_level(new_xp)
        }).eq("user_id", user_id).execute()
    except Exception:
        pass


async def _check_and_award_badges(user_id: str, current_streak: int, total_entries: int):
    admin = get_admin_client()

    # Determine which badges to check
    candidates = []
    if total_entries == 1:
        candidates.append("first_reflection")
    if total_entries >= 10:
        candidates.append("mind_dump")
    if current_streak >= 3:
        candidates.append("streak_3")
    if current_streak >= 10:
        candidates.append("streak_10")
    if current_streak >= 30:
        candidates.append("streak_30")

    # Check word count for deep_diver
    try:
        latest = (
            admin.table("journals")
            .select("word_count")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if latest.data and (latest.data[0].get("word_count") or 0) >= 200:
            candidates.append("deep_diver")
    except Exception:
        pass

    for slug in candidates:
        await _award_badge_if_not_earned(user_id, slug)


async def _award_badge_if_not_earned(user_id: str, slug: str):
    admin = get_admin_client()
    try:
        badge = admin.table("badges").select("id,xp_reward").eq("slug", slug).single().execute()
        if not badge.data:
            return
        badge_id = badge.data["id"]
        xp_reward = badge.data.get("xp_reward", 50)

        # Check if already earned
        existing = (
            admin.table("user_badges")
            .select("id")
            .eq("user_id", user_id)
            .eq("badge_id", badge_id)
            .execute()
        )
        if existing.data:
            return

        # Award badge
        admin.table("user_badges").insert({
            "user_id": user_id, "badge_id": badge_id
        }).execute()

        # Award XP
        streak = admin.table("streaks").select("total_xp").eq("user_id", user_id).single().execute()
        current_xp = (streak.data or {}).get("total_xp", 0) + xp_reward
        admin.table("xp_events").insert({
            "user_id": user_id, "source": "badge_earned",
            "amount": xp_reward, "metadata": {"badge_slug": slug}
        }).execute()
        admin.table("streaks").update({
            "total_xp": current_xp, "level": _xp_to_level(current_xp)
        }).eq("user_id", user_id).execute()
    except Exception:
        pass


async def get_streak_data(user_id: str) -> dict:
    admin = get_admin_client()
    try:
        streak = admin.table("streaks").select("*").eq("user_id", user_id).single().execute()
        data = streak.data or {}
        xp = data.get("total_xp", 0)
        return {
            **data,
            "next_level_xp": _next_level_xp(xp),
            "xp_progress_pct": round((xp / max(_next_level_xp(xp), 1)) * 100, 1)
        }
    except Exception:
        return {"current_streak": 0, "longest_streak": 0, "total_xp": 0, "level": "Beginner"}


async def get_badges(user_id: str) -> list:
    admin = get_admin_client()
    try:
        # All badge definitions
        all_badges = admin.table("badges").select("*").eq("is_active", True).execute()
        # User's earned badges
        earned = admin.table("user_badges").select("badge_id,earned_at").eq("user_id", user_id).execute()
        earned_ids = {e["badge_id"]: e["earned_at"] for e in (earned.data or [])}

        result = []
        for b in (all_badges.data or []):
            result.append({
                **b,
                "earned": b["id"] in earned_ids,
                "earned_at": earned_ids.get(b["id"])
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def award_values_badge(user_id: str):
    await _award_badge_if_not_earned(user_id, "values_explorer")

    admin = get_admin_client()
    try:
        admin.table("xp_events").insert({
            "user_id": user_id, "source": "values_test", "amount": 20
        }).execute()
    except Exception:
        pass


async def dev_reset_progress(user_id: str):
    """Dev tool: Reset user streaks, XP, and badges to 0."""
    admin = get_admin_client()
    try:
        admin.table("xp_events").delete().eq("user_id", user_id).execute()
        admin.table("user_badges").delete().eq("user_id", user_id).execute()
        
        reset_data = {
            "current_streak": 0,
            "longest_streak": 0,
            "total_entries": 0,
            "total_xp": 0,
            "level": "Beginner",
            "last_entry_date": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert in case streak record doesn't exist yet
        try:
            admin.table("streaks").update(reset_data).eq("user_id", user_id).execute()
        except Exception:
            # If update fails, insert it
            reset_data["user_id"] = user_id
            admin.table("streaks").insert(reset_data).execute()

        return {"status": "success", "message": "Gamification progress reset to 0"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def dev_increment_streak(user_id: str):
    """Dev tool: Increment current streak by 1 and update longest streak."""
    admin = get_admin_client()
    try:
        try:
            streak_res = admin.table("streaks").select("*").eq("user_id", user_id).single().execute()
            streak = streak_res.data or {}
        except Exception:
            streak = {}

        current_streak = streak.get("current_streak", 0) + 1
        longest_streak = max(streak.get("longest_streak", 0), current_streak)
        
        upsert_data = {
            "user_id": user_id,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Don't overwrite other fields if inserting
        if not streak:
            upsert_data.update({
                "total_entries": 0,
                "total_xp": 0,
                "level": "Beginner"
            })
            admin.table("streaks").insert(upsert_data).execute()
        else:
            admin.table("streaks").update({
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("user_id", user_id).execute()

        return {"status": "success", "message": f"Streak incremented to {current_streak}", "new_streak": current_streak}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
