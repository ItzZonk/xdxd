from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    choosing_grade = State()
    choosing_class = State()
    viewing_schedule = State()
