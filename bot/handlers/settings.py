
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User

router = Router()

@router.message(Command("settings"))
async def cmd_settings(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        return
        
    text = (
        "⚙️ **Настройки**\n\n"
        f"🔔 Уведомления: {'ВКЛ' if user.notification_enabled else 'ВЫКЛ'}\n"
        f"🌍 Часовой пояс: UTC{user.timezone_offset:+d}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔔 {'Выключить' if user.notification_enabled else 'Включить'}", callback_data="toggle_notify")
    builder.button(text="🌍 + Час", callback_data="tz_inc")
    builder.button(text="🌍 - Час", callback_data="tz_dec")
    builder.button(text="↩️ Меню", callback_data="main_menu")
    builder.adjust(1, 2, 1)
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "toggle_notify")
async def cb_toggle_notify(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        user.notification_enabled = not user.notification_enabled
        await session.commit()
        await cmd_settings(callback.message, session)
    await callback.answer()

@router.callback_query(F.data.in_({"tz_inc", "tz_dec"}))
async def cb_tz_change(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        current = user.timezone_offset if user.timezone_offset else 0
        if callback.data == "tz_inc":
            user.timezone_offset = min(current + 1, 14)
        else:
            user.timezone_offset = max(current - 1, -12)
        await session.commit()
        await cmd_settings(callback.message, session)
    await callback.answer()
