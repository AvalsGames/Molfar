from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from config import DATABASE_URL, DEFAULT_TIMEZONE
import pytz

scheduler = AsyncIOScheduler(
    jobstores={'default': SQLAlchemyJobStore(url=DATABASE_URL.replace('sqlite+aiosqlite', 'sqlite'))},
    timezone=pytz.timezone(DEFAULT_TIMEZONE)
)

async def start_scheduler():
    if not scheduler.running:
        scheduler.start()

async def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
