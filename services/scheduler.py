"""
Scheduler setup using APScheduler.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import settings
from services.updater import run_update_cycle
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def ping_server():
    """Pings the server's own endpoint to prevent idle sleep on free hosting tiers (e.g. Render)."""
    url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("PING_URL")
    if not url:
        port = int(os.environ.get("PORT", 8080))
        url = f"http://localhost:{port}/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                logger.info(f"Pinged keep-alive endpoint: {url}, status: {response.status}")
    except Exception as e:
        logger.error(f"Failed to ping keep-alive endpoint: {e}")

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
    
    # Ping server to keep it alive every 5 minutes
    scheduler.add_job(
        ping_server,
        trigger=IntervalTrigger(minutes=5),
        id="ping_server",
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    logger.info(f"Scheduler started. Interval: {settings.check_interval_minutes} min")
    
    # Log scheduled jobs
    jobs = scheduler.get_jobs()
    for job in jobs:
        logger.info(f"Job: {job.name}, Next run time: {job.next_run_time}")
