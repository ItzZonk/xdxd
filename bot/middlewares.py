from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            
            # Update last_active if user is present
            if hasattr(event, "from_user") and event.from_user:
                from datetime import datetime
                from sqlalchemy import update
                from database.models import User
                
                try:
                    await session.execute(
                        update(User)
                        .where(User.telegram_id == event.from_user.id)
                        .values(last_active=datetime.now())
                    )
                    await session.commit()
                except Exception:
                    # Ignore errors during activity update to not block the bot
                    pass
            
            return await handler(event, data)
