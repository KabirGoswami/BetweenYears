"""
Auth service — wraps Supabase Auth operations
"""
from fastapi import HTTPException, status
from supabase import Client
from database import get_anon_client, get_admin_client
from notifications.service import send_welcome_email


async def signup_user(email: str, password: str, display_name: str) -> dict:
    client = get_anon_client()
    try:
        res = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"display_name": display_name}}
        })
        if res.user is None:
            raise HTTPException(status_code=400, detail="Signup failed — check your email address")
        
        # Trigger welcome email asynchronously
        try:
            await send_welcome_email(str(res.user.id), email, display_name)
        except Exception as e:
            print(f"[Signup Email Error] {e}")
            
        return res
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "already exists" in msg.lower():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise HTTPException(status_code=400, detail=msg)


async def login_user(email: str, password: str) -> dict:
    client = get_anon_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.session is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")


async def refresh_session(refresh_token: str) -> dict:
    client = get_anon_client()
    try:
        res = client.auth.refresh_session(refresh_token)
        if res.session is None:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not refresh session")


async def logout_user(access_token: str) -> None:
    client = get_anon_client()
    try:
        client.auth.sign_out()
    except Exception:
        pass  # Session may already be expired


async def reset_password(email: str, redirect_url: str) -> None:
    client = get_anon_client()
    try:
        client.auth.reset_password_email(email, {"redirect_to": redirect_url})
    except Exception as e:
        # Don't reveal if email exists or not — prevent user enumeration
        pass


async def get_user_profile(user_id: str, access_token: str) -> dict:
    admin = get_admin_client()
    try:
        res = admin.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=404, detail="Profile not found")


async def update_user_profile(user_id: str, updates: dict) -> dict:
    admin = get_admin_client()
    cleaned = {k: v for k, v in updates.items() if v is not None}
    if not cleaned:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        res = admin.table("user_profiles").update(cleaned).eq("id", user_id).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile update failed: {e}")
