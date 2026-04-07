import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")
FILES_STORAGE_PATH = os.getenv("FILES_STORAGE_PATH", "./data/files/")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Kyiv")
FILE_CHANNEL_ID = os.getenv("FILE_CHANNEL_ID") # Optional ID of a private channel to mirror files

# AI Model settings
GROQ_MODEL = "llama-3.1-8b-instant"  # Швидка та економна модель
