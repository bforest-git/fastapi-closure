import asyncio
import logging
import os
import aiohttp
from app.database import SessionLocal
from app.tracker import sync_tracker_issues

logger = logging.getLogger(__name__)

async def sync_loop():
    """Фоновая задача: синхронизация тикетов каждые 300 секунд"""
    while True:
        try:
            await asyncio.sleep(300)
            # Синхронизация в отдельном потоке (т.к. startrek-client синхронный)
            loop = asyncio.get_event_loop()
            db = SessionLocal()
            try:
                notifications = await loop.run_in_executor(
                    None, sync_tracker_issues, db
                )
                # Отправить уведомления
                for notif in notifications:
                    await send_notification(notif)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Sync error: {e}")

async def send_notification(notif: dict):
    """Отправить уведомление пользователю"""
    messenger = notif.get("messenger", "telegram")
    if messenger == "telegram":
        await send_telegram_notification(notif)

async def send_telegram_notification(notif: dict):
    """Отправить уведомление в Telegram через reply"""
    import os
    import aiohttp
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not set, cannot send notification")
        return
    
    chat_id = notif["chat_id"]
    message_id = notif["message_id"]
    result = notif["result"]
    tracker_text = notif.get("tracker_text")
    
    # Формат: {result}\n{tracker_text} если tracker_text не пустой, иначе {result}
    if tracker_text:
        text = f"{result}\n{tracker_text}"
    else:
        text = result
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": message_id
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"Failed to send Telegram notification: {resp.status} {body}")
            else:
                logger.info(f"Sent notification to chat_id={chat_id}")