from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func
from typing import List, Optional

from database.db import async_session
from database.models import GroupPoll, PollTopic, PollVote, User
from utils.security import verify_internal_token

router = APIRouter(prefix="/api", tags=["poll"])

class TgUserPayload(BaseModel):
    id: int
    username: Optional[str] = None
    full_name: str

class TopicSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    tg_user: TgUserPayload

class VotePayload(BaseModel):
    topic_id: int
    tg_user: TgUserPayload

class PollCreatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=256)

@router.get("/poll")
async def get_active_poll(x_internal_token: str | None = Header(default=None)):
    """Get the currently active poll, topics, and vote counts."""
    await verify_internal_token(x_internal_token)
    
    async with async_session() as session:
        # Find active poll
        result = await session.execute(select(GroupPoll).where(GroupPoll.is_active == True).order_by(GroupPoll.created_at.desc()).limit(1))
        poll = result.scalar_one_or_none()
        
        if not poll:
            return {"active": False, "poll": None}
            
        # Get topics for this poll
        topics_result = await session.execute(select(PollTopic).where(PollTopic.poll_id == poll.id))
        topics = topics_result.scalars().all()
        
        # Get votes count per topic
        votes_result = await session.execute(
            select(PollVote.topic_id, func.count(PollVote.id))
            .where(PollVote.poll_id == poll.id)
            .group_by(PollVote.topic_id)
        )
        votes_map = {row[0]: row[1] for row in votes_result.all()}
        
        topics_data = []
        for t in topics:
            topics_data.append({
                "id": t.id,
                "title": t.title,
                "votes": votes_map.get(t.id, 0),
                "suggested_by": t.suggested_by
            })
            
        return {
            "active": True,
            "poll": {
                "id": poll.id,
                "title": poll.title,
                "topics": sorted(topics_data, key=lambda x: x["votes"], reverse=True)
            }
        }

@router.post("/poll/topic")
async def suggest_topic(payload: TopicSuggestion, x_internal_token: str | None = Header(default=None)):
    """Suggest a new topic for the active poll."""
    await verify_internal_token(x_internal_token)
    
    async with async_session() as session:
        # Ensure user exists
        from database.db import add_user
        await add_user(payload.tg_user.id, payload.tg_user.username, payload.tg_user.full_name)
        
        # Get active poll
        result = await session.execute(select(GroupPoll).where(GroupPoll.is_active == True).limit(1))
        poll = result.scalar_one_or_none()
        
        if not poll:
            raise HTTPException(status_code=400, detail="Нет активного опроса")
            
        topic = PollTopic(poll_id=poll.id, title=payload.title, suggested_by=payload.tg_user.id)
        session.add(topic)
        await session.commit()
        return {"ok": True, "topic_id": topic.id}

@router.post("/poll/vote")
async def vote_topic(payload: VotePayload, x_internal_token: str | None = Header(default=None)):
    """Vote for a topic in the active poll."""
    await verify_internal_token(x_internal_token)
    
    async with async_session() as session:
        # Ensure user exists
        from database.db import add_user
        await add_user(payload.tg_user.id, payload.tg_user.username, payload.tg_user.full_name)
        
        # Check topic exists and get poll_id
        result = await session.execute(select(PollTopic).where(PollTopic.id == payload.topic_id))
        topic = result.scalar_one_or_none()
        if not topic:
            raise HTTPException(status_code=404, detail="Тема не найдена")
            
        # Check if already voted
        vote_result = await session.execute(
            select(PollVote).where(PollVote.poll_id == topic.poll_id, PollVote.user_id == payload.tg_user.id)
        )
        existing_vote = vote_result.scalar_one_or_none()
        
        if existing_vote:
            # Change vote
            existing_vote.topic_id = payload.topic_id
        else:
            # New vote
            vote = PollVote(poll_id=topic.poll_id, topic_id=payload.topic_id, user_id=payload.tg_user.id)
            session.add(vote)
            
        await session.commit()
        return {"ok": True}

@router.post("/admin/poll/create")
async def create_poll(payload: PollCreatePayload, x_internal_token: str | None = Header(default=None)):
    """Create a new poll (Admin only)"""
    await verify_internal_token(x_internal_token)
    
    async with async_session() as session:
        # End any existing active polls
        await session.execute(update(GroupPoll).where(GroupPoll.is_active == True).values(is_active=False))
        
        new_poll = GroupPoll(title=payload.title, is_active=True)
        session.add(new_poll)
        await session.commit()
        return {"ok": True, "poll_id": new_poll.id}

@router.post("/admin/poll/close")
async def close_poll(x_internal_token: str | None = Header(default=None)):
    """Close the active poll (Admin only)"""
    await verify_internal_token(x_internal_token)
    
    async with async_session() as session:
        await session.execute(update(GroupPoll).where(GroupPoll.is_active == True).values(is_active=False))
        await session.commit()
        return {"ok": True}
