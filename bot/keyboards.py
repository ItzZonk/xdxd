from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import Class

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(text="👶 Начальная школа (1-4)", callback_data="grade_1-4"))
    builder.row(InlineKeyboardButton(text="👦 Средняя школа (5-9)", callback_data="grade_5-9"))
    builder.row(InlineKeyboardButton(text="🎓 Старшие классы (10-11)", callback_data="grade_10-11"))
    
    builder.row(
        InlineKeyboardButton(text="👤 Личный кабинет", callback_data="personal_cabinet"),
        InlineKeyboardButton(text="👨‍🏫 Учителя", callback_data="teachers_menu")
    )
    
    return builder.as_markup()

def classes_in_grade_kb(current_grade: int, min_grade: int, max_grade: int, classes: list[Class]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    grade_classes = sorted(
        [c for c in classes if c.grade_level == current_grade],
        key=lambda c: c.name
    )
    
    rows = []
    current_row = []
    for cls in grade_classes:
        current_row.append(InlineKeyboardButton(text=f"{cls.name}", callback_data=f"set_cls_{cls.id}"))
        if len(current_row) == 3:
            builder.row(*current_row)
            current_row = []
    if current_row:
        builder.row(*current_row)
        
    nav_buttons = []
    
    if current_grade > min_grade:
        nav_buttons.append(InlineKeyboardButton(text=f"⬅️ {current_grade - 1}-е", callback_data=f"view_grade:{current_grade - 1}:{min_grade}:{max_grade}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        
    nav_buttons.append(InlineKeyboardButton(text=f"📂 {current_grade}-е классы", callback_data="ignore"))
    
    if current_grade < max_grade:
        nav_buttons.append(InlineKeyboardButton(text=f"{current_grade + 1}-е ➡️", callback_data=f"view_grade:{current_grade + 1}:{min_grade}:{max_grade}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        
    builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="🔙 Вернуться к выбору параллели", callback_data="main_menu"))
    
    return builder.as_markup()

def teachers_list_kb(teachers: list, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    limit = 20
    start = page * limit
    end = start + limit
    
    current_page_teachers = teachers[start:end]
    
    for t in current_page_teachers:
        builder.button(text=t.name, callback_data=f"sel_teach_{t.id}")
    builder.adjust(2)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"teach_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"• {page+1} •", callback_data="ignore"))

    if end < len(teachers):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"teach_page_{page+1}"))
    
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="main_menu"))
    
    return builder.as_markup()

def schedule_controls_kb(current_date_str: str, is_subscribed: bool, mode: str = "class") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if mode == "class":
        sub_text = "🔕 Отписаться" if is_subscribed else "🔔 Подписаться"
        builder.row(InlineKeyboardButton(text=sub_text, callback_data="toggle_sub"))
    
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data="prev_day"),
        InlineKeyboardButton(text="Сегодня", callback_data="today"),
        InlineKeyboardButton(text="➡️", callback_data="next_day")
    )
    
    back_callback = "select_grade" if mode == "class" else "teachers_menu"
    builder.row(InlineKeyboardButton(text="↩️ Меню выбора", callback_data=back_callback))
    
    return builder.as_markup()

def role_selection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👨‍🎓 Я - Ученик", callback_data="role_student"),
        InlineKeyboardButton(text="👨‍🏫 Я - Учитель", callback_data="role_teacher")
    )
    builder.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="main_menu"))
    return builder.as_markup()

def cabinet_controls_kb(mode: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data="cab_prev"),
        InlineKeyboardButton(text="Сегодня", callback_data="cab_today"),
        InlineKeyboardButton(text="➡️", callback_data="cab_next")
    )
    
    builder.row(InlineKeyboardButton(text="⚙️ Сменить роль", callback_data="change_role"))
    builder.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="main_menu"))
    
    return builder.as_markup()
