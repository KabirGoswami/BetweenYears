"""
Shared FastAPI dependency — authenticate every protected endpoint.
Extracts and validates the Supabase JWT from the Authorization header.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_anon_client

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Validates the bearer token via Supabase Auth and returns the user payload.
    Raises 401 if token is missing, invalid, or expired.
    """
    token = creds.credentials
    client = get_anon_client()
    try:
        res = client.auth.get_user(token)
        if res.user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        user = res.user
        return {
            "id": str(user.id),
            "email": user.email,
            "access_token": token,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
