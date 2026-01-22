"""
Scheduler setup using APScheduler.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import settings
from services.updater import run_update_cycle
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def setup_scheduler(bot):
    """
    Configures and starts the scheduler.
    """
    scheduler.add_job(
        run_update_cycle,
        trigger=IntervalTrigger(minutes=settings.check_interval_minutes),
        args=[bot],
        id="check_schedule",
        replace_existing=True
    )

    from services.notifications import send_morning_brief
    from apscheduler.triggers.cron import CronTrigger
    
    # Hourly checks
    scheduler.add_job(
        send_morning_brief,
        trigger=CronTrigger(minute=0), 
        args=[bot],
        id="morning_brief",
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    logger.info(f"Scheduler started. Interval: {settings.check_interval_minutes} min")
