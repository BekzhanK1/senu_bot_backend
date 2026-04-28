"""Router for settings and profile endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from database.db import get_app_settings, get_user, get_user_requests, update_app_settings, add_user
from services.audit_service import AuditService
from utils.app_settings_service import invalidate_app_settings_cache
from utils.security import verify_internal_token, verify_admin_access, rate_limit, get_api_rate_limiter


router = APIRouter(prefix="/api", tags=["settings"])


# Request/Response models
class AppSettingsData(BaseModel):
    welcome_message: str = Field(min_length=10, max_length=4096)
    mentor_about_text: str = Field(min_length=10, max_length=4096)
    mentor_photo_url: str = Field(default="", max_length=1000)
    support_bot_username: str = Field(default="@pcs_nu_bot", min_length=3, max_length=128)
    support_hotline: str = Field(default="111", min_length=1, max_length=64)
    miniapp_home_title: str = Field(min_length=3, max_length=256)
    miniapp_home_footer: str = Field(min_length=3, max_length=256)


class AdminSettingsUpdateRequest(BaseModel):
    tg_user_id: int
    settings: AppSettingsData


class AdminSettingsResponse(BaseModel):
    settings: AppSettingsData
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None


class ProfileRequest(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None


class UserRequestItem(BaseModel):
    id: int
    request_type: str
    content: str
    status: str
    created_at: datetime


class UserProfileResponse(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    full_name: str
    is_blocked: bool
    requests: list[UserRequestItem]


@router.get("/settings/public")
@rate_limit(get_api_rate_limiter())
async def public_settings(
    x_internal_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Get public settings (no auth required)."""
    await verify_internal_token(x_internal_token)
    
    settings, _, _ = await get_app_settings()
    return {
        "miniapp_home_title": settings["miniapp_home_title"],
        "miniapp_home_footer": settings["miniapp_home_footer"],
    }


@router.get("/admin/settings", response_model=AdminSettingsResponse)
@rate_limit(get_api_rate_limiter())
async def admin_settings_get(
    tg_user_id: int = Query(...),
    x_internal_token: str | None = Header(default=None),
) -> AdminSettingsResponse:
    """Get app settings."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(tg_user_id)
    
    settings, updated_by, updated_at = await get_app_settings()
    return AdminSettingsResponse(
        settings=AppSettingsData(**settings),
        updated_by=updated_by,
        updated_at=updated_at,
    )


@router.put("/admin/settings", response_model=AdminSettingsResponse)
@rate_limit(get_api_rate_limiter())
async def admin_settings_put(
    payload: AdminSettingsUpdateRequest,
    x_internal_token: str | None = Header(default=None),
) -> AdminSettingsResponse:
    """Update app settings."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    settings, updated_by, updated_at = await update_app_settings(
        payload.settings.model_dump(),
        updated_by=payload.tg_user_id,
    )
    invalidate_app_settings_cache()
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="update_settings",
        entity_type="settings",
        details={"fields_updated": list(payload.settings.model_dump().keys())},
    )
    
    return AdminSettingsResponse(
        settings=AppSettingsData(**settings),
        updated_by=updated_by,
        updated_at=updated_at,
    )


@router.post("/profile/me", response_model=UserProfileResponse)
@rate_limit(get_api_rate_limiter())
async def get_my_profile(
    payload: ProfileRequest,
    x_internal_token: str | None = Header(default=None),
) -> UserProfileResponse:
    """Get user profile."""
    await verify_internal_token(x_internal_token)
    
    user = await get_user(payload.tg_user_id)
    if not user:
        if not payload.full_name:
            raise HTTPException(status_code=404, detail="User not found")
        await add_user(payload.tg_user_id, payload.username, payload.full_name)
        user = await get_user(payload.tg_user_id)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create user profile")
    
    from database.db import is_user_blocked
    requests = await get_user_requests(payload.tg_user_id, limit=100)
    
    return UserProfileResponse(
        tg_user_id=user.telegram_id,
        username=user.username,
        full_name=user.full_name,
        is_blocked=await is_user_blocked(user.telegram_id),
        requests=[
            UserRequestItem(
                id=req.id,
                request_type=req.request_type,
                content=req.content,
                status=req.status,
                created_at=req.created_at,
            )
            for req in requests
        ],
    )
