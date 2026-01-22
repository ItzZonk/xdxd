import asyncio
import logging
import sys
import os
import aiohttp
from aiohttp import web

# Ensure the current directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import main

async def health_check(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

async def keep_alive_loop():
    """Pings the bot's own URL every 14 minutes to prevent sleep."""
    external_url = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not external_url:
        logging.warning("RENDER_EXTERNAL_HOSTNAME not found, keep-alive loop disabled")
        return

    url = f"https://{external_url}/health"
    logging.info(f"Starting keep-alive loop for {url}")
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await asyncio.sleep(14 * 60) # 14 minutes
                async with session.get(url) as response:
                    logging.info(f"Keep-alive ping status: {response.status}")
            except Exception as e:
                logging.error(f"Keep-alive ping failed: {e}")
            

async def run_app():
    # Start web server for Render (to satisfy port binding requirement)
    await start_web_server()
    
    # Start keep-alive loop in background
    asyncio.create_task(keep_alive_loop())
    
    # Start the bot
    await main()

if __name__ == "__main__":
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        pass
