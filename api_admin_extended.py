"""Extended admin API endpoints for dynamic content, roles, and mentor management."""

from typing import Any, Optional

from aiogram import Bot
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from database.db import (
    assign_role_to_mentor,
    check_mentor_exists,
    create_menu_button,
    create_mentor,
    delete_dynamic_content,
    delete_menu_button,
    get_all_dynamic_content,
    get_all_menu_buttons,
    get_all_mentors,
    get_all_roles,
    get_user_roles,
    remove_role_from_mentor,
    update_menu_button,
    upsert_dynamic_content,
)
from utils.dynamic_content_service import invalidate_content_cache
from utils.role_service import has_permission, is_admin


# ===== Request/Response Models =====

class AdminAuthRequest(BaseModel):
    tg_user_id: int


class DynamicContentItem(BaseModel):
    id: int
    key: str
    content: str
    content_type: str
    category: str
    description: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: str


class DynamicContentCreateRequest(BaseModel):
    tg_user_id: int
    key: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=10000)
    content_type: str = Field(default="text", max_length=32)
    category: str = Field(default="general", max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)


class DynamicContentUpdateRequest(BaseModel):
    tg_user_id: int
    content: str = Field(min_length=1, max_length=10000)
    content_type: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)


class MenuButtonItem(BaseModel):
    id: int
    text: str
    action_type: str
    action_value: str
    position: int
    icon: Optional[str] = None
    required_role: Optional[str] = None


class MenuButtonCreateRequest(BaseModel):
    tg_user_id: int
    text: str = Field(min_length=1, max_length=128)
    action_type: str = Field(min_length=1, max_length=32)
    action_value: str = Field(min_length=1, max_length=256)
    position: int = Field(default=0)
    icon: Optional[str] = Field(default=None, max_length=16)
    required_role: Optional[str] = Field(default=None, max_length=64)


class MenuButtonUpdateRequest(BaseModel):
    tg_user_id: int
    text: Optional[str] = Field(default=None, min_length=1, max_length=128)
    action_type: Optional[str] = Field(default=None, min_length=1, max_length=32)
    action_value: Optional[str] = Field(default=None, min_length=1, max_length=256)
    position: Optional[int] = None
    icon: Optional[str] = Field(default=None, max_length=16)
    required_role: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None


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

    # ===== Dynamic Content Endpoints =====

    @router.get("/content")
    async def list_dynamic_content(
        tg_user_id: int = Query(...),
        category: Optional[str] = Query(default=None),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """List all dynamic content."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_content")
        
        content_list = await get_all_dynamic_content(category=category)
        return {
            "items": [
                {
                    "id": c.id,
                    "key": c.key,
                    "content": c.content,
                    "content_type": c.content_type,
                    "category": c.category,
                    "description": c.description,
                    "updated_by": c.updated_by,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in content_list
            ]
        }

    @router.post("/content")
    async def create_dynamic_content(
        payload: DynamicContentCreateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Create or update dynamic content."""
        await verify_token(x_internal_token)
        await verify_admin_access(payload.tg_user_id, "can_manage_content")
        
        content_id = await upsert_dynamic_content(
            key=payload.key,
            content=payload.content,
            content_type=payload.content_type,
            category=payload.category,
            description=payload.description,
            updated_by=payload.tg_user_id,
        )
        invalidate_content_cache()
        return {"ok": True, "content_id": content_id}

    @router.put("/content/{key}")
    async def update_dynamic_content(
        key: str,
        payload: DynamicContentUpdateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Update existing dynamic content."""
        await verify_token(x_internal_token)
        await verify_admin_access(payload.tg_user_id, "can_manage_content")
        
        content_id = await upsert_dynamic_content(
            key=key,
            content=payload.content,
            content_type=payload.content_type or "text",
            category=payload.category or "general",
            description=payload.description,
            updated_by=payload.tg_user_id,
        )
        invalidate_content_cache()
        return {"ok": True, "content_id": content_id}

    @router.delete("/content/{key}")
    async def delete_content(
        key: str,
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        """Delete dynamic content."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_content")
        
        success = await delete_dynamic_content(key)
        if not success:
            raise HTTPException(status_code=404, detail="Content not found")
        invalidate_content_cache()
        return {"ok": True}

    # ===== Menu Button Endpoints =====

    @router.get("/menu-buttons")
    async def list_menu_buttons(
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """List all menu buttons."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_content")
        
        buttons = await get_all_menu_buttons()
        return {"items": buttons}

    @router.post("/menu-buttons")
    async def create_button(
        payload: MenuButtonCreateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Create a new menu button."""
        await verify_token(x_internal_token)
        await verify_admin_access(payload.tg_user_id, "can_manage_content")
        
        button_id = await create_menu_button(
            text=payload.text,
            action_type=payload.action_type,
            action_value=payload.action_value,
            position=payload.position,
            icon=payload.icon,
            required_role=payload.required_role,
        )
        invalidate_content_cache()
        return {"ok": True, "button_id": button_id}

    @router.put("/menu-buttons/{button_id}")
    async def update_button(
        button_id: int,
        payload: MenuButtonUpdateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        """Update a menu button."""
        await verify_token(x_internal_token)
        await verify_admin_access(payload.tg_user_id, "can_manage_content")
        
        success = await update_menu_button(
            button_id=button_id,
            text=payload.text,
            action_type=payload.action_type,
            action_value=payload.action_value,
            position=payload.position,
            icon=payload.icon,
            required_role=payload.required_role,
            is_active=payload.is_active,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Button not found")
        invalidate_content_cache()
        return {"ok": True}

    @router.delete("/menu-buttons/{button_id}")
    async def delete_button(
        button_id: int,
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        """Delete a menu button."""
        await verify_token(x_internal_token)
        await verify_admin_access(tg_user_id, "can_manage_content")
        
        success = await delete_menu_button(button_id)
        if not success:
            raise HTTPException(status_code=404, detail="Button not found")
        invalidate_content_cache()
        return {"ok": True}

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
