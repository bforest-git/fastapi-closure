import asyncio
import re
import httpx
import io
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
import os
import logging
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Initialize bot and dispatcher
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

# Get FastAPI URL from environment variables
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

# Initialize logger
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# Create a router
router = Router()

# Add FastAPI app for webhook endpoint
from fastapi import FastAPI, Request
webhook_app = FastAPI()

@webhook_app.post("/webhook/notification")
async def handle_notification(request: Request):
    """Handle notification from backend service"""
    try:
        payload = await request.json()
        chat_id = payload["chat_id"]
        message_id = payload["message_id"]
        result = payload["result"]
        tracker_text = payload.get("tracker_text")
        
        if tracker_text:
            text = f"{result}\n{tracker_text}"
        else:
            text = result
        
        # Send reply to user
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id
        )
        
        return {"status": "success"}
    except Exception as e:
        logger.error("Ошибка при отправке уведомления: %s", e)
        return {"status": "error", "message": str(e)}

# Media group buffer and processing
media_group_buffer = defaultdict(list)
media_group_timers = {}
MEDIA_GROUP_TIMEOUT = 1.0  # seconds
@router.message(Command("start"))
async def command_start_handler(message: types.Message):
    """
    This handler receives messages with /start command
    """
    await message.answer("Привет! Я бот для отслеживания перекрытий дорог.")

@router.message(Command("help"))
async def command_help_handler(message: types.Message):
    """
    This handler receives messages with /help command
    """
    await message.answer("Отправь сообщение с хештегом #перекрытие, #roads или #closure")

def get_mime_type(filename: str) -> str:
    """Определяет MIME-тип по расширению файла."""
    MIME_MAP = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.mp4': 'video/mp4',
        '.mov': 'video/quicktime', '.pdf': 'application/pdf',
        '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg'
    }
    ext = os.path.splitext(filename.lower())[1]
    return MIME_MAP.get(ext, 'application/octet-stream')

async def get_or_create_author(chat_id: int, messenger: str = "telegram") -> dict | None:
    """Ищет или создаёт автора через API."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            search_response = await client.get(
                f"{FASTAPI_URL}/authors/search",
                params={
                    "messenger": messenger,
                    "chat_id": chat_id
                }
            )

            if search_response.status_code == 200:
                return search_response.json()
            elif search_response.status_code == 404:
                # Author not found, create new author
                create_response = await client.post(
                    f"{FASTAPI_URL}/authors/",
                    json={
                        "messenger": messenger,
                        "chat_id": chat_id
                    }
                )
                if create_response.status_code == 201:
                    return create_response.json()
                elif create_response.status_code == 409:
                    # Author already exists, get existing author
                    retry_response = await client.get(
                        f"{FASTAPI_URL}/authors/search",
                        params={"messenger": messenger, "chat_id": str(chat_id)}
                    )
                    if retry_response.status_code == 200:
                        return retry_response.json()
                    else:
                        logger.error(f"API error when searching for existing author: {retry_response.status_code} - {retry_response.text}")
                        return None
                else:
                    logger.error(f"API error when creating author: {create_response.status_code} - {create_response.text}")
                    return None
            else:
                logger.error(f"API error when searching for author: {search_response.status_code} - {search_response.text}")
                return None
    except Exception as e:
        logger.exception("Ошибка при поиске/создании автора: %s", e)
        return None

async def submit_closure(author: dict, text: str, message_id: int,
                         sent_at: str, files: list) -> int:
    """Отправляет closure в FastAPI. Возвращает HTTP status code."""
    try:
        # Prepare data for FastAPI with user_id instead of messenger and chat_id
        form_data = {
            "text": text,
            "user_id": author["id"],
            "message_id": message_id,
            "sent_at": sent_at
        }
        
        # Handle files
        file_names = []
        if files:
            # Send as multipart/form-data if files are present
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.post(
                    f"{FASTAPI_URL}/closures/",
                    data=form_data,
                    files=files
                )
                # Close file bytes
                for _, (filename, file_bytes, mime) in files:
                    file_bytes.close()
        else:
            # Send as form-data if no files
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.post(
                    f"{FASTAPI_URL}/closures/",
                    data=form_data
                )
        
        return response.status_code
    except Exception as e:
        logger.exception("Ошибка при отправке closure: %s", e)
        return -1

def contains_closure_hashtags(text):
    """
    Check if text contains any of the closure hashtags (case insensitive)
    """
    if not text:
        return False
    hashtags = ['#перекрытие', '#roads', '#closure']
    text_lower = text.lower()
    return any(hashtag in text_lower for hashtag in hashtags)

def remove_closure_hashtags(text):
    """
    Remove closure hashtags and extra spaces from text
    """
    if not text:
        return ""
    
    # Remove hashtags (case insensitive)
    text = re.sub(r'#перекрытие\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'#roads\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'#closure\s*', '', text, flags=re.IGNORECASE)
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

async def process_media_group(media_group_id):
    """
    Process all messages in a media group after timeout
    """
    # Get all messages for this media group
    messages = media_group_buffer.get(media_group_id, [])
    if not messages:
        return
    
    # Check if any message in the group has hashtags
    has_hashtags = False
    for msg in messages:
        text = msg.text or msg.caption or ""
        if contains_closure_hashtags(text):
            has_hashtags = True
            break
    
    # If no message has hashtags, clear buffer and ignore the whole group
    if not has_hashtags:
        media_group_buffer.pop(media_group_id, None)
        return
    
    # Remove timer reference
    media_group_timers.pop(media_group_id, None)
    
    # Clear buffer for this media group
    media_group_buffer.pop(media_group_id, None)
    
    # Find the first message with hashtags (usually the first message)
    first_message_with_hashtags = None
    for msg in messages:
        text = msg.text or msg.caption or ""
        if contains_closure_hashtags(text):
            first_message_with_hashtags = msg
            break
    
    try:
        # Get text from first message with hashtags
        text = first_message_with_hashtags.text or first_message_with_hashtags.caption or ""
        cleaned_text = remove_closure_hashtags(text)

        # If text is empty after removing hashtags, use a placeholder
        if not cleaned_text:
            cleaned_text = "(без описания)"

        # Get or create author
        author = await get_or_create_author(first_message_with_hashtags.chat.id, "telegram")
        if not author:
            await first_message_with_hashtags.answer("Произошла ошибка при отправке обращения. Попробуйте позже.")
            return
        
        # Check if author is banned
        if author and author.get("is_banned", False):
            await first_message_with_hashtags.answer("Вы заблокированы и не можете отправлять обращения.")
            return
        
        # Handle media files from all messages in the group
        files = []
        file_names = []
        
        for msg in messages:
            try:
                # Use the new download function
                downloaded_files = await download_message_files(msg, bot)
                for filename, file_bytes in downloaded_files:
                    # Determine MIME type based on file extension
                    mime_type = get_mime_type(filename)
                    
                    files.append(("files", (filename, file_bytes, mime_type)))
                    file_names.append(filename)
            
                     
            except Exception as e:
                pass
                # Continue with other messages even if one fails
        
        # Submit closure
        status_code = await submit_closure(
            author,
            cleaned_text,
            first_message_with_hashtags.message_id,
            first_message_with_hashtags.date.isoformat(),
            files
        )
        
        # Handle response
        if status_code == 201:
            if file_names:
                await first_message_with_hashtags.answer(f"✅ Сообщение о перекрытии сохранено с {len(file_names)} файлами")
            else:
                await first_message_with_hashtags.answer("✅ Сообщение о перекрытии сохранено")
        elif status_code == 403:
            await first_message_with_hashtags.answer("Вы заблокированы и не можете отправлять обращения.")
        else:
            logger.error(f"API error when creating closure: {status_code}")
            await first_message_with_hashtags.answer("Произошла ошибка при отправке обращения. Попробуйте позже.")
                
    except httpx.RequestError as e:
        # Handle network errors
        if first_message_with_hashtags:
            await first_message_with_hashtags.answer("❌ Ошибка при сохранении сообщения")
    except Exception as e:
        # Handle other errors
        if first_message_with_hashtags:
            await first_message_with_hashtags.answer("❌ Ошибка при сохранении сообщения")

@router.message()
async def closure_handler(message: types.Message):
    """
    Handler for processing messages with closure hashtags
    """
    # Handle media groups
    if message.media_group_id:
        # Add message to buffer
        media_group_buffer[message.media_group_id].append(message)
        
        # If this is the first message in the group, start timer
        if message.media_group_id not in media_group_timers:
            media_group_timers[message.media_group_id] = True
            asyncio.create_task(_schedule_media_group(message.media_group_id))
        return
    
    # Handle single messages (without media_group_id)
    # Get text from message or caption
    text = message.text or message.caption or ""
    
    # Check if message contains closure hashtags
    if not contains_closure_hashtags(text):
        # Ignore messages without hashtags
        return
    
    try:
        # Remove hashtags from text
        cleaned_text = remove_closure_hashtags(text)

        # If text is empty after removing hashtags, use a placeholder
        if not cleaned_text:
            cleaned_text = "(без описания)"

        # Get or create author
        author = await get_or_create_author(message.chat.id, "telegram")
        if not author:
            await message.answer("Произошла ошибка при отправке обращения. Попробуйте позже.")
            return
        
        # Check if author is banned
        if author and author.get("is_banned", False):
            await message.answer("Вы заблокированы и не можете отправлять обращения.")
            return
        
        # Handle media files
        files = []
        file_names = []
        
        try:
            # Use the new download function
            downloaded_files = await download_message_files(message, bot)
            for filename, file_bytes in downloaded_files:
                # Determine MIME type based on file extension
                mime_type = get_mime_type(filename)
                
                files.append(("files", (filename, file_bytes, mime_type)))
                file_names.append(filename)
                
        except Exception as e:
            # Continue with text-only message if file download fails
            files = []
            file_names = []
        
        # Submit closure
        status_code = await submit_closure(
            author,
            cleaned_text,
            message.message_id,
            message.date.isoformat(),
            files
        )
        
        # Handle response
        if status_code == 201:
            if file_names:
                await message.answer(f"✅ Сообщение о перекрытии сохранено с {len(file_names)} файлами")
            else:
                await message.answer("✅ Сообщение о перекрытии сохранено")
        elif status_code == 403:
            await message.answer("Вы заблокированы и не можете отправлять обращения.")
        else:
            logger.error(f"API error when creating closure: {status_code}")
            await message.answer("Произошла ошибка при отправке обращения. Попробуйте позже.")
                
    except httpx.RequestError as e:
        # Handle network errors
        await message.answer("❌ Ошибка при сохранении сообщения")
    except Exception as e:
        # Handle other errors
        await message.answer("❌ Ошибка при сохранении сообщения")

async def _schedule_media_group(media_group_id):
    await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
    await process_media_group(media_group_id)

async def download_message_files(msg: types.Message, bot):
    """Скачивает файлы из сообщения и возвращает список кортежей (filename, file_bytes)."""
    files = []
    if msg.photo:
        photo = msg.photo[-1]  # наибольшее разрешение
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        filename = "photo_" + (photo.file_unique_id or "photo") + ".jpg"
        files.append((filename, file_bytes))
    elif msg.video:
        file_info = await bot.get_file(msg.video.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        filename = msg.video.file_name or ("video_" + (msg.video.file_unique_id or "video") + ".mp4")
        files.append((filename, file_bytes))
    elif msg.document:
        file_info = await bot.get_file(msg.document.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        filename = msg.document.file_name or ("document_" + (msg.document.file_unique_id or "document"))
        files.append((filename, file_bytes))
    elif msg.audio:
        file_info = await bot.get_file(msg.audio.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        filename = msg.audio.file_name or ("audio_" + (msg.audio.file_unique_id or "audio") + ".mp3")
        files.append((filename, file_bytes))
    elif msg.voice:
        file_info = await bot.get_file(msg.voice.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        filename = "voice_" + (msg.voice.file_unique_id or "voice") + ".ogg"
        files.append((filename, file_bytes))
    return files

async def main():
    """
    Main function to start the bot
    """
    import uvicorn
    import asyncio
    
    # Include router
    dp.include_router(router)
    
    # Создаём конфиг и сервер uvicorn вручную
    config = uvicorn.Config(webhook_app, host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    
    try:
        # Run bot polling and webhook server concurrently
        async with asyncio.TaskGroup() as tg:
            # Start bot polling
            tg.create_task(dp.start_polling(bot))
            # Start webhook server — используем корутину server.serve()
            tg.create_task(server.serve())
    finally:
        await bot.session.close()  # корректно закрываем сессию Telegram

if __name__ == "__main__":
    asyncio.run(main())