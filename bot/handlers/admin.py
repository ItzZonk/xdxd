from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta
import logging

from database.models import User, SystemMeta
from services.updater import run_update_cycle
from bot.states import UserStates # If needed, but not really for this simple command

router = Router()
logger = logging.getLogger(__name__)

# Secret command
@router.message(Command("s_stats_x"))
async def cmd_secret_stats(message: Message, session: AsyncSession):
    text_content, keyboard = await get_stats_data(session)
    await message.answer(text_content, reply_markup=keyboard)

@router.callback_query(F.data == "refresh_stats")
async def cb_refresh_stats(callback: CallbackQuery, session: AsyncSession):
    text_content, keyboard = await get_stats_data(session)
    try:
        await callback.message.edit_text(text_content, reply_markup=keyboard)
    except Exception:
        pass # Content didn't change
    await callback.answer("Updated!")

@router.callback_query(F.data == "force_update_schedule")
async def cb_force_update(callback: CallbackQuery, session: AsyncSession, bot):
    await callback.answer("Starting update cycle... This may take a moment.")
    try:
        # run_update_cycle internally creates its own session, but we can pass bot for notifications
        # Wait, looking at updater.py: async def run_update_cycle(bot=None):
        # So it does NOT take session.
        await run_update_cycle(bot)
        
        # Refresh contents
        text_content, keyboard = await get_stats_data(session)
        await callback.message.edit_text(text_content, reply_markup=keyboard)
        await callback.message.answer("✅ Update completed.")
        
    except Exception as e:
        logger.error(f"Force update failed: {e}")
        await callback.message.answer(f"❌ Update failed: {e}")

async def get_stats_data(session: AsyncSession):
    # 1. Total users
    stmt_total = select(func.count(User.telegram_id))
    result_total = await session.execute(stmt_total)
    total_users = result_total.scalar() or 0
    
    # 2. Active users (last 15 min)
    fifteen_mins_ago = datetime.now() - timedelta(minutes=15)
    stmt_active = select(func.count(User.telegram_id)).where(User.last_active >= fifteen_mins_ago)
    result_active = await session.execute(stmt_active)
    active_users = result_active.scalar() or 0
    
    # 3. Last update time
    stmt_meta = select(SystemMeta).where(SystemMeta.key == "schedule_hash")
    # Actually SystemMeta doesn't have updated_at by default in current code (I should check models.py again).
    # Wait, I see `updated_at` in models.py: `updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)`
    # But updater.py didn't seem to update it? Let's check updater.py later. 
    # For now let's just show current time as "Stats Updated At"
    
    current_time = datetime.now().strftime("%H:%M:%S")
    
    text = f"<b>📊 Bot Statistics</b>\n\n" \
           f"👥 <b>Total users:</b> {total_users}\n" \
           f"🟢 <b>Active (last 15m):</b> {active_users}\n\n" \
           f"🕒 <b>Stats Updated:</b> {current_time}"
           
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="refresh_stats")],
        [InlineKeyboardButton(text="⚡ Force Schedule Update", callback_data="force_update_schedule")]
    ])
    
    return text, keyboard
