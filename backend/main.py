"""
BetweenYears — FastAPI Application Entry Point
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from middleware.security import setup_cors, SecurityHeadersMiddleware
from notifications.scheduler import start_scheduler

# Routers
from auth.router import router as auth_router
from journal.router import router as journal_router
from ai.router import router as ai_router
from streaks.router import router as streaks_router
from community.router import router as community_router
from notifications.router import router as notifications_router
from privacy.router import router as privacy_router

settings = get_settings()

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="BetweenYears API",
    description="""
**BetweenYears** — a private reflection and journaling backend for teens and college students.

## Features
- 🔐 **Auth** — Signup, login, JWT refresh, password reset
- 📝 **Journal** — Save, list, update, delete entries with mood tracking
- 🤖 **AI** — Gemini-powered entry analysis, pattern detection, personalized prompts
- 🔥 **Streaks** — Daily streaks, XP, levels, achievement badges
- 🌱 **Community** — Anonymous stories, reactions, moderation
- 📧 **Notifications** — Email reminders, streak alerts, weekly summaries
- 🛡️ **Privacy** — GDPR export, account deletion, data transparency
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
setup_cors(app)
app.add_middleware(SecurityHeadersMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(journal_router)
app.include_router(ai_router)
app.include_router(streaks_router)
app.include_router(community_router)
app.include_router(notifications_router)
app.include_router(privacy_router)

# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    if settings.is_production:
        start_scheduler()
    print(f"[BetweenYears] API started — {settings.environment} mode")


@app.on_event("shutdown")
async def shutdown():
    from notifications.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown()


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0", "app": "BetweenYears"}


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": "BetweenYears API",
        "docs": "/docs",
        "health": "/health"
    }
