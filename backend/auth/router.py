"""
Auth router — /auth endpoints
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth.models import (
    SignupRequest, LoginRequest, TokenResponse, RefreshRequest,
    ResetPasswordRequest, UpdateProfileRequest, UserProfile
)
import auth.service as svc
from config import get_settings
from dependencies import get_current_user

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer(auto_error=False)


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest):
    """Register a new account. Returns JWT tokens on success."""
    res = await svc.signup_user(body.email, body.password, body.display_name)
    session = res.session
    # session may be None if email confirmation is required
    if session is None:
        return TokenResponse(
            access_token="", refresh_token="", user_id=str(res.user.id),
            display_name=body.display_name
        )
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=str(res.user.id),
        display_name=body.display_name
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Login with email and password. Returns JWT tokens."""
    res = await svc.login_user(body.email, body.password)
    session = res.session
    profile = await svc.get_user_profile(str(res.user.id), session.access_token)
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=str(res.user.id),
        display_name=profile.get("display_name") if profile else None
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """Refresh an expired access token."""
    res = await svc.refresh_session(body.refresh_token)
    session = res.session
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=str(res.user.id)
    )


@router.post("/logout", status_code=204)
async def logout(user=Depends(get_current_user), creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Invalidate the current session."""
    token = creds.credentials if creds else ""
    await svc.logout_user(token)


@router.post("/reset-password", status_code=202)
async def reset_password(body: ResetPasswordRequest):
    """Send a password reset email. Always returns 202 (prevents user enumeration)."""
    await svc.reset_password(
        body.email,
        redirect_url=f"{settings.frontend_url}/reset-confirm"
    )
    return {"message": "If that email is registered, a reset link has been sent."}


@router.get("/me", response_model=UserProfile)
async def get_me(user=Depends(get_current_user), creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Get the current user's profile."""
    token = creds.credentials if creds else ""
    profile = await svc.get_user_profile(user["id"], token)
    return UserProfile(
        id=user["id"],
        email=user["email"],
        display_name=profile.get("display_name"),
        bio=profile.get("bio"),
        avatar_url=profile.get("avatar_url"),
        journal_private=profile.get("journal_private", True),
        analytics_opt_in=profile.get("analytics_opt_in", False),
        community_anonymous=profile.get("community_anonymous", True),
        created_at=str(profile.get("created_at", ""))
    )


@router.patch("/me", response_model=dict)
async def update_me(body: UpdateProfileRequest, user=Depends(get_current_user)):
    """Update display name, bio, or avatar."""
    updated = await svc.update_user_profile(user["id"], body.model_dump(exclude_none=True))
    return {"message": "Profile updated", "data": updated}
