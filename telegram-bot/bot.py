import asyncio
import logging
import re
import httpx
import io
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
import os
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

# Get FastAPI URL from environment variables
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# Create a router
router = Router()

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
    
    # If no message has hashtags, ignore the whole group
    if not first_message_with_hashtags:
        return
    
    try:
        # Get text from first message with hashtags
        text = first_message_with_hashtags.text or first_message_with_hashtags.caption or ""
        cleaned_text = remove_closure_hashtags(text)
        
        # Prepare data for FastAPI
        form_data = {
            "text": cleaned_text,
            "messenger": "telegram",
            "chat_id": first_message_with_hashtags.chat.id,
            "message_id": first_message_with_hashtags.message_id,
            "sent_at": first_message_with_hashtags.date.isoformat()
        }
        
        # Handle media files from all messages in the group
        files = []
        file_names = []
        
        for msg in messages:
            try:
                # Handle photos
                if msg.photo:
                    # Get the photo with the highest resolution (last in the list)
                    photo = msg.photo[-1]
                    file_info = await bot.get_file(photo.file_id)
                    file_content = await bot.download_file(file_info.file_path)
                    file_bytes = io.BytesIO()
                    file_content.seek(0)
                    file_bytes.write(file_content.read())
                    file_bytes.seek(0)
                    files.append(("files", ("photo_" + (photo.file_unique_id or "photo") + ".jpg", file_bytes, "image/jpeg")))
                    file_names.append("photo_" + (photo.file_unique_id or "photo") + ".jpg")
                
                # Handle videos
                elif msg.video:
                    video = msg.video
                    file_info = await bot.get_file(video.file_id)
                    file_content = await bot.download_file(file_info.file_path)
                    file_bytes = io.BytesIO()
                    file_content.seek(0)
                    file_bytes.write(file_content.read())
                    file_bytes.seek(0)
                    filename = video.file_name or ("video_" + (video.file_unique_id or "video") + ".mp4")
                    files.append(("files", (filename, file_bytes, video.mime_type or "video/mp4")))
                    file_names.append(filename)
                
                # Handle documents
                elif msg.document:
                    document = msg.document
                    file_info = await bot.get_file(document.file_id)
                    file_content = await bot.download_file(file_info.file_path)
                    file_bytes = io.BytesIO()
                    file_content.seek(0)
                    file_bytes.write(file_content.read())
                    file_bytes.seek(0)
                    filename = document.file_name or ("document_" + (document.file_unique_id or "document"))
                    files.append(("files", (filename, file_bytes, document.mime_type or "application/octet-stream")))
                    file_names.append(filename)
            
                    
            except Exception as e:
                logging.error(f"Error downloading media files from message {msg.message_id}: {e}")
                # Continue with other messages even if one fails
        
        # Send POST request to FastAPI
        async with httpx.AsyncClient(follow_redirects=True) as client:
            if files:
                # Send as multipart/form-data if files are present
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
                response = await client.post(
                    f"{FASTAPI_URL}/closures/",
                    data=form_data
                )
            
            if response.status_code == 201:
                if file_names:
                    await first_message_with_hashtags.answer(f"✅ Сообщение о перекрытии сохранено с {len(file_names)} файлами")
                else:
                    await first_message_with_hashtags.answer("✅ Сообщение о перекрытии сохранено")
            else:
                logging.error(f"FastAPI returned error: {response.status_code} - {response.text}")
                await first_message_with_hashtags.answer("❌ Ошибка при сохранении сообщения")
                
    except httpx.RequestError as e:
        # Handle network errors
        logging.error(f"Failed to connect to FastAPI: {e}")
        if first_message_with_hashtags:
            await first_message_with_hashtags.answer("❌ Ошибка при сохранении сообщения")
    except Exception as e:
        # Handle other errors
        logging.error(f"Unexpected error: {e}")
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
            # Check if any message in the group has hashtags
            has_hashtags = False
            for msg in media_group_buffer[message.media_group_id]:
                text = msg.text or msg.caption or ""
                if contains_closure_hashtags(text):
                    has_hashtags = True
                    break
            
            # Only process if there are hashtags
            if has_hashtags:
                # Start timer to process the group
                timer = asyncio.create_task(
                    asyncio.sleep(MEDIA_GROUP_TIMEOUT)
                )
                media_group_timers[message.media_group_id] = timer
                
                # Wait for timer and process the group
                try:
                    await timer
                    await process_media_group(message.media_group_id)
                except Exception as e:
                    logging.error(f"Error processing media group: {e}")
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
        
        # Prepare data for FastAPI
        form_data = {
            "text": cleaned_text,
            "messenger": "telegram",
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "sent_at": message.date.isoformat()
        }
        
        # Handle media files
        files = []
        file_names = []
        
        try:
            # Handle photos
            if message.photo:
                # Get the photo with the highest resolution (last in the list)
                photo = message.photo[-1]
                file_info = await bot.get_file(photo.file_id)
                file_content = await bot.download_file(file_info.file_path)
                file_bytes = io.BytesIO()
                file_content.seek(0)
                file_bytes.write(file_content.read())
                file_bytes.seek(0)
                files.append(("files", ("photo_" + (photo.file_unique_id or "photo") + ".jpg", file_bytes, "image/jpeg")))
                file_names.append("photo_" + (photo.file_unique_id or "photo") + ".jpg")
            
            # Handle videos
            elif message.video:
                video = message.video
                file_info = await bot.get_file(video.file_id)
                file_content = await bot.download_file(file_info.file_path)
                file_bytes = io.BytesIO()
                file_content.seek(0)
                file_bytes.write(file_content.read())
                file_bytes.seek(0)
                filename = video.file_name or ("video_" + (video.file_unique_id or "video") + ".mp4")
                files.append(("files", (filename, file_bytes, video.mime_type or "video/mp4")))
                file_names.append(filename)
            
            # Handle documents
            elif message.document:
                document = message.document
                file_info = await bot.get_file(document.file_id)
                file_content = await bot.download_file(file_info.file_path)
                file_bytes = io.BytesIO()
                file_content.seek(0)
                file_bytes.write(file_content.read())
                file_bytes.seek(0)
                filename = document.file_name or ("document_" + (document.file_unique_id or "document"))
                files.append(("files", (filename, file_bytes, document.mime_type or "application/octet-stream")))
                file_names.append(filename)
            
            # Handle audio
            elif message.audio:
                audio = message.audio
                file_info = await bot.get_file(audio.file_id)
                file_content = await bot.download_file(file_info.file_path)
                file_bytes = io.BytesIO()
                file_content.seek(0)
                file_bytes.write(file_content.read())
                file_bytes.seek(0)
                filename = audio.file_name or ("audio_" + (audio.file_unique_id or "audio") + ".mp3")
                files.append(("files", (filename, file_bytes, audio.mime_type or "audio/mpeg")))
                file_names.append(filename)
            
            # Handle voice messages
            elif message.voice:
                voice = message.voice
                file_info = await bot.get_file(voice.file_id)
                file_content = await bot.download_file(file_info.file_path)
                file_bytes = io.BytesIO()
                file_content.seek(0)
                file_bytes.write(file_content.read())
                file_bytes.seek(0)
                filename = "voice_" + (voice.file_unique_id or "voice") + ".ogg"
                files.append(("files", (filename, file_bytes, voice.mime_type or "audio/ogg")))
                file_names.append(filename)
                
        except Exception as e:
            logging.error(f"Error downloading media files: {e}")
            # Continue with text-only message if file download fails
            files = []
            file_names = []
        
        # Send POST request to FastAPI
        async with httpx.AsyncClient(follow_redirects=True) as client:
            if files:
                # Send as multipart/form-data if files are present
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
                response = await client.post(
                    f"{FASTAPI_URL}/closures/",
                    data=form_data
                )
            
            if response.status_code == 201:
                if file_names:
                    await message.answer(f"✅ Сообщение о перекрытии сохранено с {len(file_names)} файлами")
                else:
                    await message.answer("✅ Сообщение о перекрытии сохранено")
            else:
                logging.error(f"FastAPI returned error: {response.status_code} - {response.text}")
                await message.answer("❌ Ошибка при сохранении сообщения")
                
    except httpx.RequestError as e:
        # Handle network errors
        logging.error(f"Failed to connect to FastAPI: {e}")
        await message.answer("❌ Ошибка при сохранении сообщения")
    except Exception as e:
        # Handle other errors
        logging.error(f"Unexpected error: {e}")
        await message.answer("❌ Ошибка при сохранении сообщения")

async def main():
    """
    Main function to start the bot
    """
    # Include router
    dp.include_router(router)
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Starting bot...")
    asyncio.run(main())