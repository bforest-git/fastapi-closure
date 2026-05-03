import asyncio
import logging
import os
import aiohttp
from app.database import SessionLocal
from app.models import Closure
from app.tracker import sync_tracker_issues

logger = logging.getLogger(__name__)

async def sync_loop():
    """Фоновая задача: синхронизация тикетов каждые 30 секунд"""
    while True:
        try:
            loop = asyncio.get_running_loop()
            db = SessionLocal()
            try:
                notifications = await loop.run_in_executor(
                    None, sync_tracker_issues, db
                )
                for notif in notifications:
                    await send_notification(notif, db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
        await asyncio.sleep(30)

async def send_notification(notif: dict, db):
    """Отправить уведомление пользователю"""
    closure_id = notif.get("closure_id")
    messenger = notif.get("messenger", "telegram")
    if messenger == "telegram":
        success = await send_telegram_notification(notif)
        if success:
            if closure_id:
                closure = db.query(Closure).filter(Closure.id == closure_id).first()
                if closure:
                    closure.is_answered = True
                    db.commit()
        return success
    return False

async def send_telegram_notification(notif: dict):
    """Отправить уведомление в Telegram через reply"""
    import ssl

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("[send_telegram_notification] BOT_TOKEN not set")
        return False

    chat_id = notif["chat_id"]
    message_id = notif["message_id"]
    result = notif["result"]
    tracker_text = notif.get("tracker_text")

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

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as resp:
                body = await resp.text()
                if resp.status != 200:
                    logger.error(
                        f"[send_telegram_notification] HTTP {resp.status}: {body}"
                    )
                    return False
                return True
    except Exception as exc:
        logger.error(
            f"[send_telegram_notification] Exception: {exc!r}",
            exc_info=True
        )
        return False
