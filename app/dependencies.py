"""Dependency injection functions for FastAPI routes."""
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=True)


def verify_admin_key(api_key: str = Depends(api_key_header)):
    """Verify that the provided API key matches the admin key."""
    admin_key = settings.admin_api_key
    if not admin_key or api_key != admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")
