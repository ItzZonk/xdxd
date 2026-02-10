from datetime import datetime
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TelegramUser
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select
from database.models import User

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
            
            # Track user activity
            tg_user: TelegramUser = data.get("event_from_user")
            if tg_user:
                stmt = select(User).where(User.telegram_id == tg_user.id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    user = User(
                        telegram_id=tg_user.id,
                        username=tg_user.username,
                        last_active=datetime.now()
                    )
                    session.add(user)
                else:
                    user.last_active = datetime.now()
                    if user.username != tg_user.username:
                        user.username = tg_user.username
                
                await session.flush() # Ensure ID is available if needed, but here we just update
                
            return await handler(event, data)
