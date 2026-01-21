"""
Schedule navigation handlers.
"""
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import classes_in_grade_kb, schedule_controls_kb, main_menu_kb
from bot.states import UserStates
from database.models import Class, User, Schedule

router = Router()

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "✨ *Выберите вашу параллель:*",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("grade_"))
async def select_grade(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    grade_range = callback.data.split("_")[1]
    start_grade, end_grade = map(int, grade_range.split('-'))
    
    # Start with the specific grade views
    await render_grade_view(callback, session, start_grade, start_grade, end_grade)

@router.callback_query(F.data.startswith("view_grade:"))
async def switch_grade_view(callback: types.CallbackQuery, session: AsyncSession):
    # data format: view_grade:current:min:max
    parts = callback.data.split(":")
    current_grade = int(parts[1])
    min_grade = int(parts[2])
    max_grade = int(parts[3])
    
    await render_grade_view(callback, session, current_grade, min_grade, max_grade)

async def render_grade_view(callback: types.CallbackQuery, session: AsyncSession, current_grade: int, min_grade: int, max_grade: int):
    await callback.answer()
    # Fetch classes
    stmt = select(Class)
    result = await session.execute(stmt)
    all_classes = result.scalars().all()
    
    await callback.message.edit_text(
        f"📂 *Выберите класс* (Параллель {current_grade}-х):",
        reply_markup=classes_in_grade_kb(current_grade, min_grade, max_grade, all_classes),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("set_cls_"))
async def select_class(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    try:
        class_id = int(callback.data.split("_")[2])
        
        # Update user choice
        user_id = callback.from_user.id
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.class_id = class_id
            await session.commit()
        
        # Show schedule for today
        today = datetime.now()
        # Update default view date in state
        await state.update_data(view_date=today.timestamp())
        
        await render_schedule(callback.message, session, class_id, today, user.notification_enabled if user else False)
        # Attempt to answer callback to stop loading animation, though edit_text might suffice
        await callback.answer() 
    except Exception:
        await callback.answer("Ошибка выбора класса", show_alert=True)

@router.callback_query(F.data.in_({"prev_day", "next_day", "today"}))
async def navigate_schedule(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    # default to today
    current_date_ts = data.get("view_date", datetime.now().timestamp())
    current_date = datetime.fromtimestamp(current_date_ts)
    
    if callback.data == "prev_day":
        target_date = current_date - timedelta(days=1)
    elif callback.data == "next_day":
        target_date = current_date + timedelta(days=1)
    else:
        target_date = datetime.now()
        
    await state.update_data(view_date=target_date.timestamp())
    
    # Determine target ID and mode
    view_mode = data.get("view_mode", "class")
    target_id = data.get("view_id")
    
    # Needs user for notification status (only relevant for class mode basically)
    # But let's fetch user anyway
    user_id = callback.from_user.id
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if view_mode == "class":
        # If accessing class, prefer state ID, fallback to user profile default
        if not target_id:
             target_id = user.class_id if user else None
             
        if not target_id:
            await callback.answer("Сначала выберите класс!")
            return
    elif view_mode == "teacher":
        if not target_id:
            await callback.answer("Учитель не выбран!")
            return

    await render_schedule(callback.message, session, target_id, target_date, user.notification_enabled if user else False, mode=view_mode)

from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import classes_in_grade_kb, schedule_controls_kb


from database.models import Class, User, Schedule, Substitution, Teacher
from bot.utils import get_subject_emoji

def format_room(room: str) -> str:
    """Форматирует номер кабинета: '1 Б311' -> 'Б311 (корп. 1)'"""
    if not room:
        return ""
    parts = room.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return f"{parts[1]} (корп. {parts[0]})"
    return room

async def render_schedule(
    message: types.Message, 
    session: AsyncSession, 
    target_id: int, 
    date: datetime, 
    is_subbed: bool, 
    mode: str = "class",
    custom_kb: Optional[InlineKeyboardMarkup] = None
):
    """
    mode: 'class' or 'teacher'
    target_id: class_id if mode='class', teacher_id if mode='teacher'
    """
    day_of_week = date.weekday()
    
    standard_lessons = []
    subs = {}
    
    target_name = ""
    
    if mode == "class":
        # Fetch Class Name for title
        cls_res = await session.execute(select(Class.name).where(Class.id == target_id))
        target_name = cls_res.scalar_one_or_none() or "Класс"

        # 1. Standard Schedule
        stmt = select(Schedule).where(
            Schedule.class_id == target_id,
            Schedule.day_of_week == day_of_week
        ).order_by(Schedule.lesson_number)
        result = await session.execute(stmt)
        standard_lessons = result.scalars().all()
        
        # 2. Substitutions
        date_str_db = date.strftime("%d.%m.%Y")
        stmt_sub = select(Substitution).where(
            Substitution.class_id == target_id,
            Substitution.date == date_str_db
        )
        result_sub = await session.execute(stmt_sub)
        subs = {s.lesson_number: s for s in result_sub.scalars().all()}
        
    elif mode == "teacher":
        # Fetch Teacher Name
        t_res = await session.execute(select(Teacher.name).where(Teacher.id == target_id))
        target_name = t_res.scalar_one_or_none() or "Учитель"
        
        # For teachers, we need to find lessons where teacher_name MATCHES.
        # This is tricky because DB Schedule stores 'teacher_name' as string, and Teacher model has 'name'.
        # Hopefully they match exactly from parser.
        
        # 1. Standard Schedule
        stmt = select(Schedule).where(
            Schedule.teacher_name.ilike(f"%{target_name}%"), # Loose match or exact? Name should be exact from Nika.
            Schedule.day_of_week == day_of_week
        ).order_by(Schedule.lesson_number)
        # Note: A teacher might have multiple lessons at same time? Unlikely for one person.
        # But `Schedule` table has `class_id`. We need to fetch the Class too to display it.
        # Eager load class?
        stmt = stmt.options(selectinload(Schedule.school_class))
        
        result = await session.execute(stmt)
        standard_lessons = result.scalars().all()
        
        # 2. Substitutions
        # Teacher substitutions are harder.
        # A substitution record might:
        # a) Assign THIS teacher to a class (Replacement) -> We should show this.
        # b) Remove THIS teacher from a class (Cancellation/Replacement) -> We should show "Cancelled" for them?
        
        date_str_db = date.strftime("%d.%m.%Y")
        
        # Find subs where this teacher IS the new teacher
        stmt_sub_new = select(Substitution).where(
            Substitution.teacher_name.ilike(f"%{target_name}%"),
            Substitution.date == date_str_db
        ).options(selectinload(Substitution.school_class))
        
        # Find subs where this teacher WAS the original teacher (to show cancellation)
        # We can't easily query "was original" directly from Substitution table unless we look at Schedule for that class/day/lesson.
        # This is complex.
        # Simplified approach:
        # 1. Get all standard lessons for this teacher.
        # 2. Check if there's a substitution for that Class+Lesson. If so, does it CHANGE the teacher?
        
        result_sub_new = await session.execute(stmt_sub_new)
        subs_new_list = result_sub_new.scalars().all()
        
        # Map: ClassID_LessonNum -> Sub
        # But wait, we serve a Teacher view.
        # We iterate generic "Lesson Numbers".
        
        # Strategy: 
        # Collect all "Potential" lessons:
        # A. From Standard Schedule (filtered by this teacher)
        # B. From Substitutions (where this teacher is the NEW teacher)
        pass 

    ru_days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = ru_days[day_of_week]
    date_formatted = date.strftime('%d.%m')
    
    # Premium Header
    header = f"🎓 *Лицей «Солярис»*  |  {date_formatted}\n" \
             f"👤 *{target_name}*\n" if mode == "teacher" else \
             f"🏫 *{target_name}*  |  {date_formatted}\n" 
             
    if mode == "class":
         header = f"🏫 *Лицей «Солярис»*  |  {date_formatted}\n" \
                  f"🗓 *{day_name}*\n" \
                  f"📚 *Класс: {target_name}*\n" \
                  f"{'─' * 25}\n"
    else:
         header = f"🎓 *{target_name}*  |  {date_formatted}\n" \
                  f"🗓 *{day_name}*\n" \
                  f"{'─' * 25}\n"

    text = header
    
    if mode == "class":
        # Group lessons by lesson_number to handle group splits
        lessons_by_num = {}
        for l in standard_lessons:
            if l.lesson_number not in lessons_by_num:
                lessons_by_num[l.lesson_number] = []
            lessons_by_num[l.lesson_number].append(l)
        
        # Determine all lesson numbers (including from subs)
        lesson_nums = set(lessons_by_num.keys())
        lesson_nums.update(subs.keys())
        
        if not lesson_nums:
            text += "\n🏖 *Уроков нет!* Наслаждайся отдыхом.\n"
        else:
            for num in sorted(lesson_nums):
                lessons_list = lessons_by_num.get(num, [])
                sub_lesson = subs.get(num)
                
                # Rendering number emoji
                num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                idx_val = num - 1
                num_icon = num_emoji[idx_val] if 0 <= idx_val < len(num_emoji) else f"*{num}.*"
                
                # Get time from first lesson (same for all groups)
                first_lesson = lessons_list[0] if lessons_list else None
                time_str = ""
                if first_lesson and first_lesson.start_time and first_lesson.end_time:
                    start = first_lesson.start_time.strftime('%H:%M') if hasattr(first_lesson.start_time, 'strftime') else str(first_lesson.start_time)[:5]
                    end = first_lesson.end_time.strftime('%H:%M') if hasattr(first_lesson.end_time, 'strftime') else str(first_lesson.end_time)[:5]
                    time_str = f" ({start}-{end})"
                
                # Check for substitution status
                is_cancelled = sub_lesson.is_cancelled if sub_lesson else False
                is_replacement = sub_lesson and not sub_lesson.is_cancelled
                
                # Check if this is a group split (multiple lessons for same number)
                has_groups = len(lessons_list) > 1 and any(l.group_name for l in lessons_list)
                
                if is_cancelled:
                    subject = first_lesson.subject_name if first_lesson else "Урок"
                    text += f"\n{num_icon} ~{subject}~{time_str} (ОТМЕНА ❌)\n"
                elif has_groups:
                    # Multiple groups - show each as sub-item
                    text += f"\n{num_icon}⏰{time_str}\n"
                    for i, l in enumerate(lessons_list):
                        subj_icon = get_subject_emoji(l.subject_name)
                        group_label = l.group_name or f"Группа {i+1}"
                        connector = "├" if i < len(lessons_list) - 1 else "└"
                        text += f"   {connector} 🏷 *{group_label}*: {subj_icon} {l.subject_name}\n"
                        text += f"   {'│' if i < len(lessons_list) - 1 else ' '}     👤 {l.teacher_name} | 🚪 {format_room(l.room_number)}\n"
                else:
                    # Single lesson for whole class
                    if first_lesson:
                        subject = first_lesson.subject_name
                        teacher = first_lesson.teacher_name
                        room = first_lesson.room_number
                    else:
                        subject = "По расписанию"
                        teacher = None
                        room = None
                    
                    # Apply substitution overrides
                    if is_replacement:
                        if sub_lesson.subject_name: subject = sub_lesson.subject_name
                        if sub_lesson.room_number: room = sub_lesson.room_number
                    
                    subj_icon = get_subject_emoji(subject)
                    
                    if is_replacement:
                        text += f"\n{num_icon} {subj_icon} *{subject}*{time_str} (ЗАМЕНА 🔄)"
                    else:
                        text += f"\n{num_icon} {subj_icon} *{subject}*{time_str}"
                    
                    meta_info = []
                    if is_replacement and sub_lesson and sub_lesson.teacher_name:
                        orig_t = first_lesson.teacher_name if first_lesson else None
                        new_t = sub_lesson.teacher_name
                        if orig_t and orig_t != new_t:
                            meta_info.append(f"👤 ~{orig_t}~ -> *{new_t}*")
                        else:
                            meta_info.append(f"👤 *{new_t}*")
                    elif teacher:
                        meta_info.append(f"👤 {teacher}")
                    
                    if room:
                        meta_info.append(f"🚪 {format_room(room)}")
                        
                    if meta_info:
                        text += f"\n      └ {' | '.join(meta_info)}"
                    text += "\n"

    elif mode == "teacher":
        # TEACHER LOGIC
        # 1. Build a map of LessonNum -> LessonData
        # LessonData = { 'subject': ..., 'class_name': ..., 'room': ..., 'status': ... }
        
        # A teacher can have multiple lessons at same slot? (e.g. groups). 
        # Yes, technically. So mapping LessonNum -> List[LessonData]
        
        lessons_map = {}
        
        # Add Standard Lessons
        for l in standard_lessons:
            # Check for cancellation/substitution for this specific class slot
            # We need to query if THIS class has a sub at THIS slot that affects THIS teacher.
            # Only effective way is to fetch ALL subs for these classes.
            # Optimization: Fetch all Subs for found classes on this date.
            pass
            
            # Simple approach first: Just show standard schedule for teacher
            # TODO: Handle substitutions correctly for teachers (complex relation)
            
            l_data = {
                "subject": l.subject_name,
                "class_name": l.school_class.name if l.school_class else "??",
                "room": l.room_number,
                "status": "normal"
            }
            if l.lesson_number not in lessons_map: lessons_map[l.lesson_number] = []
            lessons_map[l.lesson_number].append(l_data)
            
        if not lessons_map:
             text += "\n🏖 *Уроков нет!* Или данные обновляются.\n"
        else:
             for num in sorted(lessons_map.keys()):
                num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                idx_val = num - 1
                num_icon = num_emoji[idx_val] if 0 <= idx_val < len(num_emoji) else f"*{num}.*"
                
                for item in lessons_map[num]:
                    subj_icon = get_subject_emoji(item['subject'])
                    text += f"\n{num_icon} {subj_icon} *{item['subject']}*"
                    text += f"\n      └ 🎓 {item['class_name']} | 🚪 {format_room(item['room'])}\n"

    
    # Callback data needs to support mode
    # schedule_controls_kb(date_str, is_subbed, mode)
    # We need to update keyboard signature
    
    # Use custom keyboard if provided, otherwise default schedule controls
    keyboard = custom_kb if custom_kb else schedule_controls_kb(date_formatted, is_subbed, mode=mode)

    try:
        await message.edit_text(
            text, 
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        pass

@router.callback_query(F.data == "toggle_sub")
async def toggle_subscription(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        user.notification_enabled = not user.notification_enabled
        await session.commit()
        status = "включены 🔔" if user.notification_enabled else "выключены 🔕"
        await callback.answer(f"Уведомления {status}")
        # Refresh keyborad
        # Need date and class_id to re-render?
        # Ideally just update markup button.
        # For MVP re-render current view or just update markup.
        # Simpler refactor: just answer toast. Button wont update until meaningful action.
        # Or force re-render.
        # await render_schedule(...) # Need dates from state.
