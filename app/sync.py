"""Module for synchronizing tracker issues and sending notifications."""
import asyncio
import logging
import aiohttp
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models import Closure
from app.services.tracker_service import sync_tracker_issues
from app.config import settings

logger = logging.getLogger(__name__)

async def sync_loop():
    """Background task: sync tickets every 30 seconds"""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                notifications = await sync_tracker_issues(db)
                for notif in notifications:
                    await send_notification(notif, db)
                await db.commit()
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Ошибка в sync_loop: %s", e)
        await asyncio.sleep(30)

async def send_notification(notif: dict, db):
    """Send notification to user via bot webhook"""
    closure_id = notif.get("closure_id")
    if closure_id:
        # Use async SQLAlchemy
        result = await db.execute(
            select(Closure)
            .where(Closure.id == closure_id)
            .options(selectinload(Closure.author), selectinload(Closure.issue))
        )
        closure = result.scalar_one_or_none()
        if closure and closure.author:
            messenger = closure.author.messenger
            if messenger == "telegram":
                # Update notif with author data
                notif["chat_id"] = closure.author.chat_id
                success = await send_bot_notification(notif)
                if success:
                    # Update is_answered flag in Issue table
                    if closure.issue:
                        closure.issue.is_answered = True
                        await db.commit()
                return success
    return False

async def send_bot_notification(notif: dict):
    """Send notification to bot via webhook"""
    bot_url = settings.bot_url
    if not bot_url:
        logger.warning("BOT_URL not set, skipping notification")
        return False

    payload = {
        "chat_id": notif["chat_id"],
        "message_id": notif["message_id"],
        "result": notif["result"],
        "tracker_text": notif.get("tracker_text"),
        "closure_id": notif.get("closure_id")
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{bot_url}/webhook/notification", json=payload) as resp:
                if resp.status != 200:
                    logger.error("Bot notification failed with status %s", resp.status)
                    return False
                return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Ошибка отправки уведомления боту: %s", exc)
        return False
