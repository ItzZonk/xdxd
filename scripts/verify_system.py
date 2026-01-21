
import asyncio
import logging
import sys
from sqlalchemy import select, func

from database.session import init_db
from database.models import Class, Schedule, User
from services.updater import run_update_cycle
from database.session import AsyncSessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

async def verify_system():
    logger.info("--- Starting System Verification ---")
    
    # 1. Init DB
    logger.info("1. Initializing Database...")
    await init_db()
    
    # 2. Run Update Cycle (simulate scheduler)
    logger.info("2. Running Update Cycle...")
    await run_update_cycle(bot=None) # Pass None as bot to skip notifications
    
    # 3. Check DB Content
    logger.info("3. Verifying Database Content...")
    async with AsyncSessionLocal() as session:
        # Check Classes
        class_count = await session.scalar(select(func.count(Class.id)))
        logger.info(f"   Classes found: {class_count}")
        
        # Check Schedule
        schedule_count = await session.scalar(select(func.count(Schedule.id)))
        logger.info(f"   Schedule entries found: {schedule_count}")
        
        if class_count > 0 and schedule_count > 0:
            logger.info("✅ SUCCESS: Database populated successfully!")
            
            # Print sample
            stmt = select(Schedule).limit(1)
            sample = await session.scalar(stmt)
            logger.info(f"   Sample schedule: {sample}")
            
        else:
            logger.error("❌ FAILURE: Database is empty!")

if __name__ == "__main__":
    asyncio.run(verify_system())
