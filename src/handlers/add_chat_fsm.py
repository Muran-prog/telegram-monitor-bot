import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from telethon import TelegramClient
from telethon.tl.types import User, Channel, Chat
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import UserAlreadyParticipantError

from src.states.user_states import AddChat
from src.database.queries import (
    db_get_session_credentials, db_is_chat_monitored, db_add_chat
)
from src.config import SESSIONS_DIR
from src.utils.lexicon import LEXICON
from src.keyboards.inline import create_cancel_keyboard
from src.handlers.session_management import show_session_menu

router = Router()

@router.callback_query(F.data.startswith("add_chat:"))
async def start_add_chat_process(callback: CallbackQuery, state: FSMContext):
    phone = callback.data.split(":", 1)[1]
    await state.set_state(AddChat.entering_chat_identifier)
    await state.update_data(phone=phone)
    await callback.message.edit_text(
        text=LEXICON['prompt_add_chat'],
        reply_markup=create_cancel_keyboard()
    )
    await callback.answer()

@router.message(StateFilter(AddChat.entering_chat_identifier))
async def process_chat_identifier(message: Message, state: FSMContext):
    chat_identifier = message.text
    user_data = await state.get_data()
    phone = user_data.get('phone')
    user_id = message.from_user.id

    if not phone:
        await message.answer(LEXICON['error_generic'])
        await state.clear()
        return

    credentials = db_get_session_credentials(user_id, phone)
    session_path = SESSIONS_DIR / f"{user_id}_{phone}.session"

    if not credentials or not session_path.exists():
        await message.answer(LEXICON['error_generic'])
        await state.clear()
        return

    api_id, api_hash = credentials
    with open(session_path, "r") as f:
        session_string = f.read()

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    final_message, should_clear_state = "", True

    try:
        await client.connect()
        entity = await client.get_entity(chat_identifier)

        if db_is_chat_monitored(user_id, phone, entity.id):
            final_message = "This entity is already in your monitoring list."
        else:
            if isinstance(entity, User):
                user_name = f"{entity.first_name} {entity.last_name or ''}".strip()
                db_add_chat(user_id, phone, entity.id, user_name, 'user')
                final_message = LEXICON['add_user_success'].format(user_name=user_name)
            elif isinstance(entity, (Channel, Chat)):
                try:
                    await client(JoinChannelRequest(entity))
                    final_message = LEXICON['add_chat_success'].format(chat_title=entity.title)
                except UserAlreadyParticipantError:
                    final_message = LEXICON['add_chat_already_joined'].format(chat_title=entity.title)
                db_add_chat(user_id, phone, entity.id, entity.title, 'chat')
            else:
                final_message = LEXICON['add_chat_error']
    except (ValueError, TypeError):
        final_message, should_clear_state = LEXICON['add_chat_not_found'], False
    except Exception as e:
        logging.error(f"Error adding chat: {e}")
        final_message = LEXICON['add_chat_error']
    finally:
        await message.answer(final_message)
        if client.is_connected():
            await client.disconnect()
        if should_clear_state:
            await state.clear()
            await show_session_menu(message, user_id)