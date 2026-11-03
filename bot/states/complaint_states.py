from aiogram.fsm.state import State, StatesGroup

class ComplaintForm(StatesGroup):
    phone = State()
    first_name = State()
    last_name = State()
    national_id = State()
    directorate_id = State()
    category = State()
    title = State()
    details = State()
    waiting_for_location = State()
    waiting_for_id_image = State()
    waiting_for_attachment = State()
    waiting_for_track_code = State()