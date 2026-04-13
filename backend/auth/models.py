"""
Auth Pydantic models — request/response schemas
"""
from pydantic import BaseModel, EmailStr, field_validator
import re


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("display_name")
    @classmethod
    def name_length(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Display name must be at least 2 characters")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    journal_private: bool
    analytics_opt_in: bool
    community_anonymous: bool
    created_at: str
