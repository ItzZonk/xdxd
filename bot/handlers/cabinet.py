from datetime import datetime, timedelta
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, Class, Teacher
from bot.keyboards import (
    role_selection_kb, 
    cabinet_controls_kb, 
    main_menu_kb,
    classes_in_grade_kb,
    teachers_list_kb
)
from bot.handlers.schedule import render_schedule

router = Router()

@router.callback_query(F.data == "personal_cabinet")
async def open_cabinet(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    
    # Get User
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        # Should exist due to middleware, but just in case
        user = User(telegram_id=user_id)
        session.add(user)
        await session.commit()

    # Check if configured
    if not user.role or (user.role == "student" and not user.class_id) or (user.role == "teacher" and not user.teacher_id):
        await callback.message.edit_text(
            "👋 *Добро пожаловать в Личный кабинет!*\n\n"
            "Давайте настроим ваш профиль. Вы учитесь или преподаете?",
            reply_markup=role_selection_kb(),
            parse_mode="Markdown"
        )
    else:
        # Render Cabinet View (Today)
        target_id = user.class_id if user.role == "student" else user.teacher_id
        target_mode = "class" if user.role == "student" else "teacher"
        
        today = datetime.now()
        await state.update_data(cabinet_date=today.timestamp())
        
        await render_schedule(
            callback.message, 
            session, 
            target_id, 
            today, 
            user.notification_enabled, 
            mode=target_mode,
            custom_kb=cabinet_controls_kb(target_mode)
        )

# --- Role Selection ---
@router.callback_query(F.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    role = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    # Update Role
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    user.role = role
    await session.commit()
    
    if role == "student":
        # Show Grade Selection (Reusing Logic? Or just direct)
        # We can simulate Main Menu "select_grade" flow but adapted?
        # Let's just show main_menu type grade selection but purely for setup
        # Or better: Just ask for grade 1-11.
        
        # Simple: Re-use the grade_1-4 etc callbacks if they are generic? 
        # They in start.py? They might be coupled to just viewing.
        # Let's create a specific one or reuse.
        
        # Actually, let's just use the `main_menu_kb`'s grade buttons logic.
        # But we need to make sure the callback handler for those knows we are in "setup" mode?
        # It's cleaner to just show those keys.
        from bot.keyboards import main_menu_kb # but we need the grade subset part
        # Let's just construct a simple temp KB for grades 
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="👶 1-4 классы", callback_data="setup_grade_1-4"))
        builder.row(InlineKeyboardButton(text="👦 5-9 классы", callback_data="setup_grade_5-9"))
        builder.row(InlineKeyboardButton(text="🎓 10-11 классы", callback_data="setup_grade_10-11"))
        builder.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="main_menu"))
        
        await callback.message.edit_text(
            "📚 *Выберите вашу параллель:*",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        
    elif role == "teacher":
        # Show Teacher List with cabinet-specific callbacks
        stmt = select(Teacher).order_by(Teacher.name)
        result = await session.execute(stmt)
        teachers = result.scalars().all()
        await show_setup_teachers(callback.message, teachers, page=0)

# --- Setup Callbacks ---
# Note: setup_grade handlers are defined below near show_setup_classes

@router.callback_query(F.data == "change_role")
async def change_role(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        user.role = None
        user.teacher_id = None
        user.class_id = None
        await session.commit()
    
    await open_cabinet(callback, session, None) # Recursively call open to show selection

# Let's implement specific setup handlers to avoid conflict
# For simplicity, if user selects "role_teacher", we can reuse `teachers_list_kb` but
# we need to interrupt the `sel_teach_` handler?
# Or just let them save `view_id` and we copy it to `teacher_id`?
# Cleaner: duplicate KB logic for cabinet setup.

# Actually, let's edit keys in `keyboards.py` to accept action prefix?
# Too much refactor.
# Let's just create a quick local builder for teachers here.
async def show_setup_teachers(message, teachers, page=0):
    # Copy of teachers_list_kb but with 'cab_set_teach_' prefix
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    limit = 20
    start = page * limit
    end = start + limit
    
    for t in teachers[start:end]:
        builder.button(text=t.name, callback_data=f"cab_set_teach_{t.id}")
    builder.adjust(2)
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"cab_teach_page_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"• {page+1} •", callback_data="ignore"))
    if end < len(teachers): nav.append(InlineKeyboardButton(text="➡️", callback_data=f"cab_teach_page_{page+1}"))
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="personal_cabinet")) # Back triggers role selection again
    
    await message.edit_text("👨‍🏫 *Выберите себя:*", reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("cab_teach_page_"))
async def setup_teach_page(call: types.CallbackQuery, session: AsyncSession):
    page = int(call.data.split("_")[3])
    stmt = select(Teacher).order_by(Teacher.name)
    res = await session.execute(stmt)
    teachers = res.scalars().all()
    await show_setup_teachers(call.message, teachers, page)

@router.callback_query(F.data.startswith("cab_set_teach_"))
async def finalize_teacher_setup(call: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    tid = int(call.data.split("_")[3])
    uid = call.from_user.id
    
    stmt = select(User).where(User.telegram_id == uid)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    user.teacher_id = tid
    await session.commit()
    
    await call.answer("Роль учителя сохранена!", show_alert=True)
    await open_cabinet(call, session, state)

# Similarly for Classes
async def show_setup_classes(message, grade, min_g, max_g, classes):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    
    grade_classes = sorted([c for c in classes if c.grade_level == grade], key=lambda x: x.name)
    row = []
    for c in grade_classes:
        row.append(InlineKeyboardButton(text=c.name, callback_data=f"cab_set_cls_{c.id}"))
        if len(row)==3:
            builder.row(*row)
            row=[]
    if row: builder.row(*row)
    
    # Nav
    nav = []
    if grade > min_g: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"cab_cls_g_{grade-1}_{min_g}_{max_g}"))
    else: nav.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
    nav.append(InlineKeyboardButton(text=f"📂 {grade}-е", callback_data="ignore"))
    if grade < max_g: nav.append(InlineKeyboardButton(text="➡️", callback_data=f"cab_cls_g_{grade+1}_{min_g}_{max_g}"))
    else: nav.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="personal_cabinet"))
    
    await message.edit_text(f"📂 *Выберите свой класс* ({grade}-е):", reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("setup_grade_"))
async def setup_grade_entry(call: types.CallbackQuery, session: AsyncSession):
    # "setup_grade_1-4"
    rng = call.data.split("_")[2]
    min_g, max_g = map(int, rng.split("-"))
    # Start at min_g
    stmt = select(Class)
    res = await session.execute(stmt)
    classes = res.scalars().all()
    await show_setup_classes(call.message, min_g, min_g, max_g, classes)

@router.callback_query(F.data.startswith("cab_cls_g_"))
async def setup_cls_nav(call: types.CallbackQuery, session: AsyncSession):
    # cab_cls_g_GRADE_MIN_MAX
    parts = call.data.split("_")
    g, mn, mx = int(parts[3]), int(parts[4]), int(parts[5])
    stmt = select(Class)
    res = await session.execute(stmt)
    classes = res.scalars().all()
    await show_setup_classes(call.message, g, mn, mx, classes)

@router.callback_query(F.data.startswith("cab_set_cls_"))
async def finalize_class_setup(call: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    cid = int(call.data.split("_")[3])
    uid = call.from_user.id
    
    stmt = select(User).where(User.telegram_id == uid)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    user.class_id = cid
    await session.commit()
    
    await call.answer("Класс сохранен!", show_alert=True)
    await open_cabinet(call, session, state)

# --- Cabinet Navigation ---
@router.callback_query(F.data.in_({"cab_prev", "cab_next", "cab_today"}))
async def cab_nav(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    ts = data.get("cabinet_date", datetime.now().timestamp())
    dt = datetime.fromtimestamp(ts)
    
    if call.data == "cab_prev": dt -= timedelta(days=1)
    elif call.data == "cab_next": dt += timedelta(days=1)
    else: dt = datetime.now()
    
    await state.update_data(cabinet_date=dt.timestamp())
    
    # Render with user Settings
    uid = call.from_user.id
    stmt = select(User).where(User.telegram_id == uid)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user: return
    
    target_id = user.class_id if user.role == "student" else user.teacher_id
    mode = "class" if user.role == "student" else "teacher"
    
    await render_schedule(
        call.message, session, target_id, dt, 
        user.notification_enabled, mode=mode, 
        custom_kb=cabinet_controls_kb(mode)
    )
    await call.answer()
