import asyncio
import logging
import re
import httpx
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

# Get FastAPI URL from environment variables
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8001")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Create a router
router = Router()

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

@router.message()
async def closure_handler(message: types.Message):
    """
    Handler for processing messages with closure hashtags
    """
    # Check if message has text and contains closure hashtags
    if not message.text or not contains_closure_hashtags(message.text):
        # Ignore messages without hashtags
        return
    
    try:
        # Remove hashtags from text
        cleaned_text = remove_closure_hashtags(message.text)
        
        # Prepare data for FastAPI
        closure_data = {
            "text": cleaned_text,
            "messenger": "telegram",
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "sent_at": message.date.isoformat()
        }
        
        # Send POST request to FastAPI
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                f"{FASTAPI_URL}/closures/",
                json=closure_data
            )
            
            if response.status_code == 201:
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