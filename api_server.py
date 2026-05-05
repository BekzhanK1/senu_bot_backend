"""
Refactored API server with service layer and modular routers.

This file now serves as the main FastAPI application factory,
delegating business logic to services and routing to dedicated routers.
"""

import os
from aiogram import Bot
from fastapi import FastAPI

from services.container import init_services
from routers.requests_router import router as requests_router
from routers.admin_router import router as admin_router
from routers.meetings_router import router as meetings_router
from routers.settings_router import router as settings_router
from routers.poll_router import router as poll_router
from routers.feedback_router import router as feedback_router
from api_admin_extended import create_admin_extended_router


def create_api_app(bot: Bot) -> FastAPI:
    """
    Create and configure FastAPI application.
    
    This factory function:
    1. Initializes the service container
    2. Registers all API routers
    3. Configures health check endpoint
    4. Returns configured FastAPI app
    """
    app = FastAPI(
        title="SENU Bot API",
        version="2.0.0",
        description="Refactored API with service layer architecture",
    )
    
    # Initialize services
    init_services(bot)
    
    # Health check endpoint
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "version": "2.0.0"}
    
    # Register routers
    app.include_router(requests_router)
    app.include_router(admin_router)
    app.include_router(meetings_router)
    app.include_router(settings_router)
    app.include_router(poll_router)
    app.include_router(feedback_router)
    
    # Include extended admin router (mentors, roles, etc.)
    internal_token = os.getenv("INTERNAL_API_TOKEN")
    extended_router = create_admin_extended_router(bot, internal_token)
    app.include_router(extended_router)
    
    return app
