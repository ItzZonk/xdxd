
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from aiogram import Bot, types
from database.session import AsyncSessionLocal
from database.models import User, Schedule
try:
    from bot.utils import get_subject_emoji
except ImportError:
    # If bot.utils not found (might be structured differently in KRMTGBOT), fallback
    def get_subject_emoji(name): return "📘"

logger = logging.getLogger(__name__)

async def send_morning_brief(bot: Bot):
    """Sends morning briefing to users at 7:00 AM local time."""
    utc_now = datetime.utcnow()
    
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.notification_enabled == True)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        for user in users:
            offset = user.timezone_offset if user.timezone_offset else 0
            user_hour = (utc_now.hour + offset) % 24
            
            if user_hour == 7: # 7 AM
                # Prepare brief
                user_now = utc_now + timedelta(hours=offset)
                weekday = user_now.weekday()
                
                # Get schedule
                sch_stmt = select(Schedule).where(
                    Schedule.class_id == user.class_id,
                    Schedule.day_of_week == weekday
                ).order_by(Schedule.start_time)
                
                sch_res = await session.execute(sch_stmt)
                lessons = sch_res.scalars().all()
                
                if lessons:
                    count = len(lessons)
                    first = lessons[0]
                    last = lessons[-1]
                    
                    msg = (
                        f"🌅 **Магия утра!**\n"
                        f"Сегодня {count} уроков.\n"
                        f"Первый: {get_subject_emoji(first.subject_name)} {first.subject_name} в {first.start_time.strftime('%H:%M')}\n"
                        f"Заканчиваем в {last.end_time.strftime('%H:%M')}.\n\n"
                        f"Удачи сегодня! 🍀"
                    )
                    try:
                        await bot.send_message(user.telegram_id, msg, parse_mode="Markdown")
                    except Exception as e:
                        logger.error(f"Failed to send morning brief to {user.telegram_id}: {e}")


