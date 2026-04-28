"""Extended admin API endpoints for roles and mentor management."""

from typing import Any, Optional

from aiogram import Bot
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from database.db import (
    assign_role_to_mentor,
    create_mentor,
    get_all_mentors,
    get_all_roles,
    get_user_roles,
    remove_role_from_mentor,
)
from utils.role_service import has_permission


# ===== Request/Response Models =====

class AdminAuthRequest(BaseModel):
    tg_user_id: int


class MentorItem(BaseModel):
    user_id: int
    display_name: str
    full_name: str
    username: Optional[str] = None
    is_active: bool
    languages: Optional[str] = None
    skills: Optional[str] = None
    roles: list[str]


class MentorCreateRequest(BaseModel):
    tg_user_id: int
    target_user_id: int
    display_name: str = Field(min_length=1, max_length=128)
    languages: Optional[str] = Field(default=None, max_length=255)
    skills: Optional[str] = Field(default=None, max_length=1000)


class RoleAssignRequest(BaseModel):
    tg_user_id: int
    target_user_id: int
    role_name: str = Field(min_length=1, max_length=64)


class RoleItem(BaseModel):
    id: int
    name: str
    permissions: Optional[str] = None


def create_admin_extended_router(bot: Bot, internal_token: str | None) -> APIRouter:
    """Create extended admin API router."""
    router = APIRouter(prefix="/api/admin", tags=["admin-extended"])

    async def verify_token(x_internal_token: str | None) -> None:
        if internal_token and x_internal_token != internal_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

    async def verify_admin_access(user_id: int, permission: str = "is_admin") -> None:
        """Verify user has admin access or specific permission."""
        if not await has_permission(user_id, permission):
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")

    # ===== Mentor Management Endpoints =====

    @router.get("/mentors")
    async def list_mentors(
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """List all mentors."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_users")
        
        mentors = await get_all_mentors()
        items = []
        for mentor, full_name, username in mentors:
            roles = await get_user_roles(mentor.user_id)
            items.append({
                "user_id": mentor.user_id,
                "display_name": mentor.display_name,
                "full_name": full_name,
                "username": username,
                "is_active": mentor.is_active,
                "languages": mentor.languages,
                "skills": mentor.skills,
                "roles": [r["name"] for r in roles],
            })
        return {"items": items}

    @router.post("/mentors")
    async def create_new_mentor(
        payload: MentorCreateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Create a new mentor."""
        await verify_token(x_internal_token)
        await verify_admin_access(payload.tg_user_id, "can_manage_users")
        
        success = await create_mentor(
            user_id=payload.target_user_id,
            display_name=payload.display_name,
            languages=payload.languages,
            skills=payload.skills,
        )
        if not success:
            raise HTTPException(status_code=400, detail="User not found or already a mentor")
        
        # Assign default mentor role
        await assign_role_to_mentor(payload.target_user_id, "mentor")
        
        return {"ok": True, "user_id": payload.target_user_id}

    @router.post("/mentors/{user_id}/roles")
    async def assign_role(
        user_id: int,
        payload: RoleAssignRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        """Assign a role to a mentor."""
        await verify_token(x_internal_token)
        await verify_admin_access(payload.tg_user_id, "can_manage_users")
        
        if user_id != payload.target_user_id:
            raise HTTPException(status_code=400, detail="User ID mismatch")
        
        success = await assign_role_to_mentor(user_id, payload.role_name)
        if not success:
            raise HTTPException(status_code=400, detail="User is not a mentor")
        
        return {"ok": True}

    @router.delete("/mentors/{user_id}/roles/{role_name}")
    async def remove_role(
        user_id: int,
        role_name: str,
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        """Remove a role from a mentor."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_users")
        
        success = await remove_role_from_mentor(user_id, role_name)
        if not success:
            raise HTTPException(status_code=404, detail="Role not found")
        
        return {"ok": True}

    @router.get("/roles")
    async def list_roles(
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """List all available roles."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_users")
        
        roles = await get_all_roles()
        return {
            "items": [
                {
                    "id": role.id,
                    "name": role.name,
                    "permissions": role.permissions,
                }
                for role in roles
            ]
        }

    return router
