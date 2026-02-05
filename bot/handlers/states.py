from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    creating_checklist = State()
    adding_item_choose = State()
    adding_item_text = State()


class WorkerStates(StatesGroup):
    choosing_checklist = State()
    answering_item = State()
    answering_comment = State()
