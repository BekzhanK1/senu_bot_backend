from aiogram.fsm.state import State, StatesGroup


class CrisisFlow(StatesGroup):
    after_grounding = State()
    waiting_stress = State()
