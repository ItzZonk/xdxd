from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database.models import Teacher
from bot.keyboards import teachers_list_kb
from bot.handlers.schedule import render_schedule

router = Router()

@router.callback_query(F.data == "teachers_menu")
@router.callback_query(F.data == "back_to_teachers")
async def list_teachers(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    stmt = select(Teacher).order_by(Teacher.name)
    result = await session.execute(stmt)
    teachers = result.scalars().all()
    
    await callback.message.edit_text(
        "🎓 *Преподавательский состав*\n"
        f"🗓 _Всего учителей: {len(teachers)}_\n\n"
        "Выберите преподавателя, чтобы посмотреть персональное расписание:",
        reply_markup=teachers_list_kb(teachers, page=0),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("teach_page_"))
async def paginate_teachers(callback: types.CallbackQuery, session: AsyncSession):
    page = int(callback.data.split("_")[2])
    
    stmt = select(Teacher).order_by(Teacher.name)
    result = await session.execute(stmt)
    teachers = result.scalars().all()
    
    try:
        await callback.message.edit_reply_markup(
            reply_markup=teachers_list_kb(teachers, page=page)
        )
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("sel_teach_"))
async def select_teacher(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    teacher_id = int(callback.data.split("_")[2])
    
    await state.update_data(view_mode="teacher", view_id=teacher_id)
    
    today = datetime.now()
    await state.update_data(view_date=today.timestamp())
    
    await render_schedule(callback.message, session, teacher_id, today, is_subbed=False, mode="teacher")
    await callback.answer()
