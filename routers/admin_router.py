"""Router for admin-related endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from services.container import get_services
from services.audit_service import AuditService
from utils.security import (
    verify_internal_token,
    verify_admin_access,
    rate_limit,
    get_api_rate_limiter,
    get_broadcast_rate_limiter,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])


# Request/Response models
class AdminResolveRequest(BaseModel):
    tg_user_id: int


class AdminReplyRequest(BaseModel):
    tg_user_id: int
    text: str = Field(min_length=1, max_length=3500)


class AdminEventCreateRequest(BaseModel):
    tg_user_id: int
    title: str = Field(min_length=2, max_length=256)
    place: str = Field(min_length=2, max_length=256)
    description: str = Field(min_length=5, max_length=3500)


class AdminEventCreateResponse(BaseModel):
    ok: bool
    event_id: int
    delivered: int
    total: int


class AdminBroadcastRequest(BaseModel):
    tg_user_id: int
    text: str = Field(min_length=1, max_length=3900)


class AdminRequestItem(BaseModel):
    id: int
    user_id: int
    user_full_name: str
    user_username: Optional[str] = None
    request_type: str
    content: str
    status: str
    created_at: datetime


class AdminRequestsResponse(BaseModel):
    items: list[AdminRequestItem]


class AdminUserItem(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    full_name: str
    joined_at: datetime
    is_blocked: bool


class AdminUsersResponse(BaseModel):
    items: list[AdminUserItem]


class AdminUserActionRequest(BaseModel):
    tg_user_id: int
    reason: Optional[str] = None


# Endpoints
@router.get("/requests", response_model=AdminRequestsResponse)
@rate_limit(get_api_rate_limiter())
async def list_admin_requests(
    tg_user_id: int = Query(...),
    request_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    x_internal_token: str | None = Header(default=None),
) -> AdminRequestsResponse:
    """List requests for admin dashboard."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(tg_user_id)
    
    services = get_services()
    rows = await services.request_service.get_admin_requests(
        request_type=request_type,
        status=status,
        limit=300,
    )
    
    items = [
        AdminRequestItem(
            id=req.id,
            user_id=req.user_id,
            user_full_name=full_name,
            user_username=username,
            request_type=req.request_type,
            content=req.content,
            status=req.status,
            created_at=req.created_at,
        )
        for req, full_name, username in rows
    ]
    
    return AdminRequestsResponse(items=items)


@router.post("/requests/{request_id}/resolve")
@rate_limit(get_api_rate_limiter())
async def resolve_admin_request(
    request_id: int,
    payload: AdminResolveRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Resolve a request."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    services = get_services()
    success = await services.request_service.resolve_user_request(
        request_id,
        notify_user=True,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="resolve_request",
        entity_type="request",
        entity_id=str(request_id),
    )
    
    return {"ok": True}


@router.post("/requests/{request_id}/reply")
@rate_limit(get_api_rate_limiter())
async def reply_admin_request(
    request_id: int,
    payload: AdminReplyRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Reply to a request."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    services = get_services()
    success = await services.request_service.reply_to_request(
        request_id,
        payload.text,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="reply_to_request",
        entity_type="request",
        entity_id=str(request_id),
        details={"reply_length": len(payload.text)},
    )
    
    return {"ok": True}


@router.post("/events", response_model=AdminEventCreateResponse)
@rate_limit(get_broadcast_rate_limiter())
async def create_admin_event(
    payload: AdminEventCreateRequest,
    x_internal_token: str | None = Header(default=None),
) -> AdminEventCreateResponse:
    """Create and broadcast an event."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    services = get_services()
    
    try:
        event_id, delivered, total = await services.broadcast_service.create_and_broadcast_event(
            title=payload.title,
            place=payload.place,
            description=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="create_event",
        entity_type="event",
        entity_id=str(event_id),
        details={
            "title": payload.title,
            "delivered": delivered,
            "total": total,
        },
    )
    
    return AdminEventCreateResponse(
        ok=True,
        event_id=event_id,
        delivered=delivered,
        total=total,
    )


@router.post("/broadcast")
@rate_limit(get_broadcast_rate_limiter())
async def admin_broadcast(
    payload: AdminBroadcastRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool | int]:
    """Broadcast a message to all users."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    services = get_services()
    
    try:
        delivered, total = await services.broadcast_service.broadcast_text(payload.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="broadcast_message",
        entity_type="broadcast",
        details={
            "text_length": len(payload.text),
            "delivered": delivered,
            "total": total,
        },
    )
    
    return {"ok": True, "delivered": delivered, "total": total}


@router.get("/users", response_model=AdminUsersResponse)
@rate_limit(get_api_rate_limiter())
async def list_admin_users(
    tg_user_id: int = Query(...),
    x_internal_token: str | None = Header(default=None),
) -> AdminUsersResponse:
    """List all users."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(tg_user_id)
    
    from database.db import get_all_users, get_blocked_user_ids
    
    users = await get_all_users(limit=1000)
    blocked_ids = await get_blocked_user_ids()
    
    items = [
        AdminUserItem(
            telegram_id=user.telegram_id,
            username=user.username,
            full_name=user.full_name,
            joined_at=user.joined_at,
            is_blocked=user.telegram_id in blocked_ids,
        )
        for user in users
    ]
    
    return AdminUsersResponse(items=items)


@router.post("/users/{telegram_id}/block")
@rate_limit(get_api_rate_limiter())
async def block_admin_user(
    telegram_id: int,
    payload: AdminUserActionRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Block a user."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    import os
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if telegram_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot block admin")
    
    from database.db import block_user
    await block_user(telegram_id, payload.reason)
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="block_user",
        entity_type="user",
        entity_id=str(telegram_id),
        details={"reason": payload.reason},
    )
    
    return {"ok": True}


@router.post("/users/{telegram_id}/unblock")
@rate_limit(get_api_rate_limiter())
async def unblock_admin_user(
    telegram_id: int,
    payload: AdminUserActionRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Unblock a user."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    from database.db import unblock_user
    await unblock_user(telegram_id)
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="unblock_user",
        entity_type="user",
        entity_id=str(telegram_id),
    )
    
    return {"ok": True}
