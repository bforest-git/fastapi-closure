import asyncio
import logging
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Create a router
router = Router()

@router.message(Command("start"))
async def command_start_handler(message: types.Message):
    """
    This handler receives messages with /start command
    """
    await message.answer("Привет! Я простой Telegram бот. Напиши мне что-нибудь!")

@router.message(Command("help"))
async def command_help_handler(message: types.Message):
    """
    This handler receives messages with /help command
    """
    help_text = (
        "Доступные команды:\n"
        "/start - Запустить бота\n"
        "/help - Показать это сообщение помощи\n"
        "Любое текстовое сообщение - Получить эхо-ответ"
    )
    await message.answer(help_text)

@router.message()
async def echo_handler(message: types.Message):
    """
    Handler will forward received message back to the sender
    """
    if message.text:
        await message.answer(f"Эхо: {message.text}")
    else:
        await message.answer("Извините, я могу обрабатывать только текстовые сообщения.")

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