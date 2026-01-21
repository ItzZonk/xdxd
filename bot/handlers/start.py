from aiogram import Router, types
from aiogram.filters import CommandStart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import main_menu_kb
from bot.states import UserStates
from database.models import User
from database.session import get_db_session

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    
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
