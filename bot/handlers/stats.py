from datetime import datetime, timedelta
from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User

router = Router()

@router.message(Command("s_stats_x"))
async def get_stats(message: types.Message, session: AsyncSession):
    # Total users
    total_result = await session.execute(select(func.count(User.telegram_id)))
    total_users = total_result.scalar() or 0
    
    # Active users in the last 15 minutes (approx "right now")
    time_threshold = datetime.now() - timedelta(minutes=15)
    active_result = await session.execute(
        select(func.count(User.telegram_id)).where(User.last_active >= time_threshold)
    )
    active_users = active_result.scalar() or 0
    
    await message.answer(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total users: {total_users}\n"
        f"🟢 Active (last 15m): {active_users}"
    )
