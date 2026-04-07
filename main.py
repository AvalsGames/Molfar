import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from config import TELEGRAM_BOT_TOKEN
from database.db import init_db
from utils.scheduler import start_scheduler, stop_scheduler, scheduler
from handlers import general, notes, lists, reminders, ai, files

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # Initialize database
    await init_db()
    
    # Initialize scheduler
    await start_scheduler()
    
    # Initialize bot and dispatcher
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(general.router)
    dp.include_router(files.router)  # Move files before ai to handle FSM states correctly
    dp.include_router(notes.router)
    dp.include_router(lists.router)
    dp.include_router(reminders.router)
    dp.include_router(ai.router)
    
    # Pass bot to scheduler for jobs
    # We do this by passing bot instance to job context or just using global reference if needed
    # But for now, we pass it via args in reminders.py
    
    # Start polling
    try:
        logging.info("Cleaning up old sessions...")
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Starting bot...")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await stop_scheduler()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
