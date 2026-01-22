
from datetime import datetime, timedelta, time
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
try:
    from bot.utils import get_subject_emoji
except ImportError:
    def get_subject_emoji(name): return "📘"
    
from database.models import User, Schedule
from bot.keyboards import main_menu_kb

router = Router()

def get_time_diff(t1: time, t2: time) -> int:
    """Returns difference in minutes between two times."""
    now_date = datetime.now().date()
    dt1 = datetime.combine(now_date, t1)
    dt2 = datetime.combine(now_date, t2)
    return int((dt2 - dt1).total_seconds() / 60)

@router.message(Command("status"))
@router.message(F.text == "⚡ Статус")
@router.callback_query(F.data == "status_dashboard")
async def cmd_status(event: types.Message | types.CallbackQuery, session: AsyncSession):
    if isinstance(event, types.CallbackQuery):
        message = event.message
        user_id = event.from_user.id
        await event.answer()
    else:
        message = event
        user_id = message.from_user.id
    
    # Fetch user settings
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.class_id:
        if isinstance(event, types.CallbackQuery):
             await message.answer("⚠️ Вы не выбрали класс.", reply_markup=main_menu_kb())
        else:
             await message.answer("⚠️ Вы не выбрали класс. Пожалуйста, выберите класс в меню.", reply_markup=main_menu_kb())
        return

    # Calculate current user time
    utc_now = datetime.utcnow()
    offset = user.timezone_offset if user.timezone_offset else 0 
    user_now = utc_now + timedelta(hours=offset)
    
    current_time = user_now.time()
    current_weekday = user_now.weekday()
    
    # Fetch schedule for today
    stmt = select(Schedule).where(
        Schedule.class_id == user.class_id,
        Schedule.day_of_week == current_weekday
    ).order_by(Schedule.start_time)
    
    result = await session.execute(stmt)
    schedules = result.scalars().all()
    
    found_status = False
    
    if not schedules:
         status_text = "📅 На сегодня уроков нет/выходной."
         found_status = True
    else:
        status_text = ""
        # Sort by start_time
        schedules.sort(key=lambda s: s.start_time)

        first_start = schedules[0].start_time
        last_end = schedules[-1].end_time

        if current_time < first_start:
             diff = get_time_diff(current_time, first_start)
             status_text = f"🌅 **Доброе утро!**\nДо начала уроков осталось {diff} мин.\n\nПервый урок: {get_subject_emoji(schedules[0].subject_name)} {schedules[0].subject_name} ({schedules[0].room_number})"
             found_status = True
        elif current_time > last_end:
             status_text = "🌙 **Уроки на сегодня закончились.**\nОтдыхайте!"
             found_status = True
        else:
            for i, lesson in enumerate(schedules):
                if lesson.start_time <= current_time <= lesson.end_time:
                    # Active lesson
                    time_left = get_time_diff(current_time, lesson.end_time)
                    status_text = (
                        f"🔴 **СЕЙЧАС ИДЕТ УРОК**\n"
                        f"{get_subject_emoji(lesson.subject_name)} **{lesson.subject_name}**\n"
                        f"🚪 Кабинет: {lesson.room_number}\n"
                        f"⏳ До конца: **{time_left} мин.**"
                    )
                    
                    if i + 1 < len(schedules):
                        next_lesson = schedules[i+1]
                        status_text += f"\n\n🔜 **Далее:** {next_lesson.subject_name} ({next_lesson.room_number})"
                    
                    found_status = True
                    break
                
                # Check for break
                if i + 1 < len(schedules):
                    if lesson.end_time < current_time < schedules[i+1].start_time:
                        next_lesson = schedules[i+1]
                        time_to_start = get_time_diff(current_time, next_lesson.start_time)
                        status_text = (
                            f"☕ **ПЕРЕМЕНА**\n"
                            f"Следующий урок через **{time_to_start} мин.**\n\n"
                            f"🔜 **{next_lesson.subject_name}**\n"
                            f"🚪 Идите в кабинет: **{next_lesson.room_number}**"
                        )
                        found_status = True
                        break

    if not found_status:
        status_text = "🤔 Не удалось определить текущий статус расписания."

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="status_dashboard")],
        [types.InlineKeyboardButton(text="↩️ В меню", callback_data="main_menu")]
    ])

    if isinstance(event, types.CallbackQuery):
        # Edit existing message
        try:
            await event.message.edit_text(status_text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            # If content is same, ignore
            pass
    else:
        # Send new message
        await message.answer(status_text, parse_mode="Markdown", reply_markup=kb)
