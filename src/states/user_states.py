from aiogram.fsm.state import State, StatesGroup

class ConnectAccount(StatesGroup):
    entering_api_id = State()
    entering_api_hash = State()
    entering_phone = State()
    entering_code = State()
    entering_password = State()

class SessionManagement(StatesGroup):
    confirm_delete = State()

class AddChat(StatesGroup):
    entering_chat_identifier = State()

class ChatManagement(StatesGroup):
    confirm_delete_chat = State()

class ChatSettings(StatesGroup):
    entering_frequency = State()
    entering_initial_fetch = State()
    entering_autoclean = State()