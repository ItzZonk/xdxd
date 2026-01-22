import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User
from database.session import AsyncSessionLocal

router = Router()

# Global tracking for active stats messages
# user_id -> message_id
active_stats_messages: Dict[int, int] = {}
# user_id -> asyncio.Task
active_tasks: Dict[int, asyncio.Task] = {}

async def delete_stats_message(bot: Bot, user_id: int):
    """Deletes the active stats message for the user if it exists."""
    # Cancel background task
    if user_id in active_tasks:
        task = active_tasks.pop(user_id)
        task.cancel()
        
    # Delete message
    if user_id in active_stats_messages:
        msg_id = active_stats_messages.pop(user_id)
        try:
            await bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception:
            # Message might strictly be already deleted or too old
            pass

async def get_stats_text(session: AsyncSession) -> str:
    # Total users
    total_result = await session.execute(select(func.count(User.telegram_id)))
    total_users = total_result.scalar() or 0
    
    # Active users in the last 15 minutes
    time_threshold = datetime.now() - timedelta(minutes=15)
    active_result = await session.execute(
        select(func.count(User.telegram_id)).where(User.last_active >= time_threshold)
    )
    active_users = active_result.scalar() or 0
    
    return (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total users: {total_users}\n"
        f"🟢 Active (last 15m): {active_users}\n\n"
        f"🕒 Updated: {datetime.now().strftime('%H:%M:%S')}"
    )

async def auto_update_stats(message: types.Message, user_id: int):
    """Background task to update stats message every minute."""
    try:
        while True:
            await asyncio.sleep(60)  # Update every 60 seconds
            async with AsyncSessionLocal() as session:
                new_text = await get_stats_text(session)
                
            await message.edit_text(
                text=new_text,
                reply_markup=get_stats_keyboard()
            )
    except (TelegramBadRequest, asyncio.CancelledError):
        pass 
    except Exception:
        pass
    finally:
        # If task ends, ensure cleanup if not explicitly cancelled called
        pass

def get_stats_keyboard():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_stats")]
    ])

@router.message(Command("s_stats_x"))
async def cmd_stats(message: types.Message, session: AsyncSession, bot: Bot):
    user_id = message.from_user.id
    
    # Clean up previous instance if exists
    await delete_stats_message(bot, user_id)
    
    text = await get_stats_text(session)
    sent_msg = await message.answer(text, reply_markup=get_stats_keyboard())
    
    # Register new instance
    active_stats_messages[user_id] = sent_msg.message_id
    active_tasks[user_id] = asyncio.create_task(auto_update_stats(sent_msg, user_id))

@router.callback_query(F.data == "refresh_stats")
async def cb_refresh_stats(callback: types.CallbackQuery, session: AsyncSession):
    text = await get_stats_text(session)
    try:
        await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    except TelegramBadRequest:
        await callback.answer("Данные актуальны", show_alert=False)
    else:
        await callback.answer()
