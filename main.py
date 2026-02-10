import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from database.session import init_db, AsyncSessionLocal
from services.scheduler import setup_scheduler
from services.updater import run_update_cycle
from bot.middlewares import DbSessionMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    dp.update.middleware(DbSessionMiddleware(session_pool=AsyncSessionLocal))
    
    from bot.handlers import start, schedule, teachers, cabinet
    
    dp.include_router(start.router)
    dp.include_router(schedule.router)
    dp.include_router(teachers.router)
    dp.include_router(cabinet.router)
    
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Fetching initial schedule data...")
    try:
        await run_update_cycle(bot)
    except Exception as e:
        logger.error(f"Initial update failed: {e}")
    
    setup_scheduler(bot)
    
    # Start simple keep-alive server for Render
    import os
    from aiohttp import web
    
    async def health_check(request):
        return web.Response(text="Bot is alive!")
        
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Keep-alive server started on port {port}")
    
    logger.info("Starting bot polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
