from aiogram.fsm.state import State, StatesGroup

class MeetingForm(StatesGroup):
    waiting_for_topic = State()
    waiting_for_time = State()

class QuestionForm(StatesGroup):
    waiting_for_text = State()
    is_anonymous = State()
