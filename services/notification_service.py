"""Service for sending notifications to users."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via Telegram bot."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_message(
        self,
        user_id: int,
        text: str,
        parse_mode: Optional[str] = "HTML",
        reply_markup=None,
    ) -> bool:
        """
        Send message to user.
        
        Returns:
            True if message was sent successfully, False otherwise.
        """
        try:
            await self.bot.send_message(
                user_id,
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return True
        except TelegramAPIError as e:
            logger.warning(f"Failed to send message to user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message to user {user_id}: {e}")
            return False
    
    async def broadcast_message(
        self,
        user_ids: list[int],
        text: str,
        parse_mode: Optional[str] = "HTML",
        batch_size: int = 30,
        delay_between_batches: float = 1.0,
    ) -> tuple[int, int]:
        """
        Broadcast message to multiple users with rate limiting.
        
        Args:
            user_ids: List of user IDs to send to
            text: Message text
            parse_mode: Parse mode (HTML, Markdown, etc.)
            batch_size: Number of messages to send per batch
            delay_between_batches: Delay in seconds between batches
        
        Returns:
            Tuple of (delivered_count, total_count)
        """
        delivered = 0
        total = len(user_ids)
        
        # Process in batches to avoid rate limits
        for i in range(0, total, batch_size):
            batch = user_ids[i:i + batch_size]
            
            # Send messages concurrently within batch
            tasks = [
                self.send_message(user_id, text, parse_mode)
                for user_id in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful deliveries
            delivered += sum(1 for result in results if result is True)
            
            # Delay between batches (except for last batch)
            if i + batch_size < total:
                await asyncio.sleep(delay_between_batches)
        
        logger.info(f"Broadcast completed: {delivered}/{total} messages delivered")
        return delivered, total
    
    async def send_photo(
        self,
        user_id: int,
        photo: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> bool:
        """
        Send photo to user.
        
        Returns:
            True if photo was sent successfully, False otherwise.
        """
        try:
            await self.bot.send_photo(
                user_id,
                photo=photo,
                caption=caption,
                parse_mode=parse_mode,
            )
            return True
        except TelegramAPIError as e:
            logger.warning(f"Failed to send photo to user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending photo to user {user_id}: {e}")
            return False
