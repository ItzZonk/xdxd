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
    # Check schedule every X minutes
    scheduler.add_job(
        run_update_cycle,
        trigger=IntervalTrigger(minutes=settings.check_interval_minutes),
        args=[bot],
        id="check_schedule",
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    logger.info(f"Scheduler started. Interval: {settings.check_interval_minutes} min")
    
    # Log scheduled jobs
    jobs = scheduler.get_jobs()
    for job in jobs:
        logger.info(f"Job: {job.name}, Next run time: {job.next_run_time}")
