from aiogram import Router, types, Bot
from aiogram.filters import CommandStart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import main_menu_kb
from bot.states import UserStates
from database.models import User
from database.session import get_db_session
from bot.handlers.stats import delete_stats_message

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Clean up stats message if it exists
    await delete_stats_message(bot, user_id)
    
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(telegram_id=user_id, username=username)
        session.add(user)
        await session.commit()
        
    await message.answer(
        "✨ *Добро пожаловать в цифровое расписание Лицея «Солярис»!* ☀️\n\n"
        "Я помогу тебе всегда быть в курсе школьных событий.\n"
        "👇 _Выберите свою параллель, чтобы начать:_ ",
        reply_markup=main_menu_kb()
    )

@router.callback_query(lambda c: c.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery, bot: Bot):
    # Clean up stats message if it exists
    await delete_stats_message(bot, callback.from_user.id)
    
    await callback.message.edit_text(
        "✨ *Добро пожаловать в цифровое расписание Лицея «Солярис»!* ☀️\n\n"
        "Я помогу тебе всегда быть в курсе школьных событий.\n"
        "👇 _Выберите свою параллель, чтобы начать:_ ",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()
