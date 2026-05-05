from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from database.db import async_session
from database.models import Feedback
from utils.security import verify_internal_token

router = APIRouter(prefix="/api", tags=["feedback"])

class TgUserPayload(BaseModel):
    id: int
    username: Optional[str] = None
    full_name: str

class FeedbackPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    tg_user: TgUserPayload

@router.post("/feedback")
async def submit_feedback(payload: FeedbackPayload, x_internal_token: str | None = Header(default=None)):
    """Submit user feedback."""
    await verify_internal_token(x_internal_token)
    
    async with async_session() as session:
        # Ensure user exists
        from database.db import add_user
        await add_user(payload.tg_user.id, payload.tg_user.username, payload.tg_user.full_name)
        
        feedback = Feedback(user_id=payload.tg_user.id, text=payload.text.strip())
        session.add(feedback)
        await session.commit()
        return {"ok": True}
