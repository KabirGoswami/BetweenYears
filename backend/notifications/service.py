"""
Notifications service — email sending via Resend + APScheduler reminders
"""
import hmac
import hashlib
import base64
import resend
from datetime import datetime, timezone
from database import get_admin_client
from config import get_settings

settings = get_settings()
resend.api_key = settings.resend_api_key


# ── Email templates ────────────────────────────────────────────────────────────

def _unsubscribe_token(user_id: str) -> str:
    """HMAC-signed unsubscribe token (prevents enumeration)."""
    sig = hmac.new(settings.secret_key.encode(), user_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode()


def _unsubscribe_link(user_id: str) -> str:
    token = _unsubscribe_token(user_id)
    return f"{settings.frontend_url}/unsubscribe?uid={user_id}&token={token}"


def _build_email_base(user_id: str, body_html: str) -> str:
    unsubscribe = _unsubscribe_link(user_id)
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Georgia', serif; background: #FAF8F4; color: #2C2C2C; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 40px auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(44,44,44,0.08); }}
    .header {{ background: #4A6741; padding: 32px 40px; }}
    .logo {{ color: #F5F0E8; font-size: 22px; letter-spacing: -0.02em; margin: 0; }}
    .logo span {{ color: #E8A882; font-style: italic; }}
    .body {{ padding: 36px 40px; }}
    .footer {{ padding: 24px 40px; background: #F5F0E8; font-size: 12px; color: #6B6B6B; text-align: center; }}
    .footer a {{ color: #4A6741; text-decoration: none; }}
    h2 {{ font-size: 22px; line-height: 1.3; margin: 0 0 16px; }}
    p {{ line-height: 1.7; color: #6B6B6B; margin: 0 0 16px; }}
    .btn {{ display: inline-block; background: #4A6741; color: #F5F0E8 !important; padding: 12px 28px; border-radius: 100px; text-decoration: none; font-weight: 500; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><p class="logo">Between<span>Years</span></p></div>
    <div class="body">{body_html}</div>
    <div class="footer">
      <p>You're receiving this because you signed up for BetweenYears.</p>
      <p><a href="{unsubscribe}">Unsubscribe from emails</a> · <a href="{settings.frontend_url}/privacy">Privacy Policy</a></p>
    </div>
  </div>
</body>
</html>
"""


async def send_welcome_email(user_id: str, email: str, display_name: str):
    name = display_name or "there"
    body = f"""
<h2>Welcome to BetweenYears, {name} 🌱</h2>
<p>You've just taken a small but meaningful step — creating space to reflect on your own life.</p>
<p>BetweenYears isn't about finding answers quickly. It's about asking better questions, one day at a time.</p>
<p style="margin-top: 24px;"><a href="{settings.frontend_url}" class="btn">Start your first reflection →</a></p>
<p style="margin-top: 24px; font-style: italic; color: #8A9E85;">"Clarity doesn't come from thinking harder — it comes from thinking honestly."</p>
"""
    await _send_email(user_id, email, "Welcome to BetweenYears 🌱", _build_email_base(user_id, body), "welcome")


async def send_daily_reminder(user_id: str, email: str, display_name: str):
    name = display_name or "there"
    body = f"""
<h2>Time to reflect, {name} ✨</h2>
<p>Even 5 minutes of honest reflection can shift your whole day.</p>
<p>Your journal is waiting — and your streak depends on it 🔥</p>
<p style="margin-top: 24px;"><a href="{settings.frontend_url}#reflect" class="btn">Open my journal →</a></p>
"""
    await _send_email(user_id, email, "Your daily reflection reminder 📝", _build_email_base(user_id, body), "daily_reminder")


async def send_streak_at_risk(user_id: str, email: str, display_name: str, streak: int):
    name = display_name or "there"
    body = f"""
<h2>Don't break your {streak}-day streak, {name}! 🔥</h2>
<p>You've been reflecting for {streak} days in a row — that's something to be proud of.</p>
<p>You've got until midnight to keep it alive. Just one entry.</p>
<p style="margin-top: 24px;"><a href="{settings.frontend_url}#reflect" class="btn">Reflect now →</a></p>
"""
    await _send_email(user_id, email, f"Your {streak}-day streak is at risk! 🔥", _build_email_base(user_id, body), "streak_at_risk")


async def send_badge_earned(user_id: str, email: str, display_name: str, badge_name: str, badge_icon: str):
    name = display_name or "there"
    body = f"""
<h2>You earned a new badge, {name}! {badge_icon}</h2>
<p>You've unlocked: <strong>{badge_name}</strong></p>
<p>Every badge reflects real growth. Keep going.</p>
<p style="margin-top: 24px;"><a href="{settings.frontend_url}#progress" class="btn">See my badges →</a></p>
"""
    await _send_email(user_id, email, f"New badge: {badge_name} {badge_icon}", _build_email_base(user_id, body), "badge_earned")


async def send_weekly_summary(user_id: str, email: str, display_name: str,
                               entries: int, streak: int, level: str):
    name = display_name or "there"
    body = f"""
<h2>Your week in reflection, {name} 📊</h2>
<p>Here's how your week went:</p>
<ul style="color: #6B6B6B; line-height: 2;">
  <li>📝 <strong>{entries}</strong> journal entries</li>
  <li>🔥 Current streak: <strong>{streak} days</strong></li>
  <li>⭐ Level: <strong>{level}</strong></li>
</ul>
<p>Consistent reflection is one of the rarest and most valuable habits you can build.</p>
<p style="margin-top: 24px;"><a href="{settings.frontend_url}#progress" class="btn">View my progress →</a></p>
"""
    await _send_email(user_id, email, "Your weekly reflection summary 📊", _build_email_base(user_id, body), "weekly_summary")


async def _send_email(user_id: str, to: str, subject: str, html: str, template: str):
    """Send via Resend and log to DB."""
    resend_id = None
    status = "failed"
    try:
        params: resend.Emails.SendParams = {
            "from": f"{settings.email_from_name} <{settings.email_from}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        email = resend.Emails.send(params)
        resend_id = email.get("id")
        status = "sent"
    except Exception as e:
        print(f"[Email Error] {e}")
    finally:
        # Log attempt regardless of outcome
        try:
            admin = get_admin_client()
            admin.table("email_log").insert({
                "user_id": user_id,
                "email_address": to,
                "template": template,
                "status": status,
                "resend_id": resend_id
            }).execute()
        except Exception:
            pass
