import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeInvalidError, SessionPasswordNeededError, PasswordHashInvalidError
)
from telethon.sessions import StringSession

from src.config import CODE_LENGTH, SESSIONS_DIR
from src.database.queries import db_add_session_credentials
from src.globals import active_sessions
from src.handlers.session_management import show_session_menu
from src.keyboards.inline import (
    create_cancel_keyboard, create_numeric_code_keyboard
)
from src.states.user_states import ConnectAccount
from src.utils.helpers import format_masked_code
from src.utils.lexicon import LEXICON

router = Router()

# --- FSM Navigation ---

@router.callback_query(F.data == "cancel_connection", StateFilter("*"))
async def handle_cancel_connection(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if 'telethon_client' in user_data and user_data['telethon_client'].is_connected():
        await user_data['telethon_client'].disconnect()
    
    if await state.get_state() is not None:
        await state.clear()
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(LEXICON['cancellation_message'])
            
    await show_session_menu(callback.message, callback.from_user.id)
    await callback.answer()

# --- Connection Flow ---

@router.callback_query(F.data == "connect_account_pressed")
async def start_connection_process(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ConnectAccount.entering_api_id)
    await callback.message.edit_text(
        text=LEXICON['prompt_api_id'],
        reply_markup=create_cancel_keyboard()
    )
    await callback.answer()

@router.message(StateFilter(ConnectAccount.entering_api_id))
async def process_api_id(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer(
            text=LEXICON['error_api_id'],
            reply_markup=create_cancel_keyboard()
        )
        return
    await state.update_data(api_id=int(message.text))
    await state.set_state(ConnectAccount.entering_api_hash)
    await message.answer(
        text=LEXICON['prompt_api_hash'],
        reply_markup=create_cancel_keyboard()
    )

@router.message(StateFilter(ConnectAccount.entering_api_hash))
async def process_api_hash(message: Message, state: FSMContext):
    await state.update_data(api_hash=message.text)
    await state.set_state(ConnectAccount.entering_phone)
    await message.answer(
        text=LEXICON['prompt_phone'],
        reply_markup=create_cancel_keyboard()
    )

@router.message(StateFilter(ConnectAccount.entering_phone))
async def process_phone(message: Message, state: FSMContext):
    phone = message.text
    if not phone or not (phone.startswith('+') and phone[1:].isdigit()):
        await message.answer(
            text=LEXICON['error_phone'],
            reply_markup=create_cancel_keyboard()
        )
        return

    user_data = await state.get_data()
    api_id, api_hash = user_data.get('api_id'), user_data.get('api_hash')
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        db_add_session_credentials(message.from_user.id, phone, api_id, api_hash)
        await state.update_data(
            phone=phone,
            phone_code_hash=sent_code.phone_code_hash,
            telethon_client=client,
            current_code=""
        )
        await state.set_state(ConnectAccount.entering_code)
        await message.answer(
            text=LEXICON['prompt_code_interactive'].format(masked_code=format_masked_code("")),
            reply_markup=create_numeric_code_keyboard()
        )
    except Exception as e:
        logging.error(f"Error during phone processing: {e}")
        await message.answer(LEXICON['error_generic'])
        if client.is_connected():
            await client.disconnect()
        await state.clear()
        await show_session_menu(message, message.from_user.id)

# --- Code and Password Handling ---

async def complete_successful_connection(message_or_callback: Message | CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    client: TelegramClient = user_data.get('telethon_client')
    phone = user_data.get('phone')
    user_id = message_or_callback.from_user.id
    
    session_file_path = SESSIONS_DIR / f"{user_id}_{phone}.session"
    with open(session_file_path, "w") as f:
        f.write(client.session.save())

    if client.is_connected():
        await client.disconnect()
        
    await state.clear()
    
    msg_to_send = message_or_callback if isinstance(message_or_callback, Message) else message_or_callback.message
    await msg_to_send.answer(LEXICON['success_connection'])
    active_sessions[user_id] = phone
    await show_session_menu(msg_to_send, user_id)


async def submit_code_logic(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    client: TelegramClient = user_data.get('telethon_client')
    phone = user_data.get('phone')
    phone_code_hash = user_data.get('phone_code_hash')
    code = user_data.get('current_code', '')

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        await complete_successful_connection(callback, state)
    except PhoneCodeInvalidError:
        await state.update_data(current_code="")
        await callback.answer(LEXICON['invalid_code_alert'], show_alert=True)
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(
                text=LEXICON['prompt_code_interactive'].format(masked_code=format_masked_code("")),
                reply_markup=create_numeric_code_keyboard()
            )
    except SessionPasswordNeededError:
        await state.set_state(ConnectAccount.entering_password)
        await callback.message.edit_text(
            text=LEXICON['prompt_password'],
            reply_markup=create_cancel_keyboard()
        )
    except Exception:
        if client.is_connected():
            await client.disconnect()
        await state.clear()
        await callback.message.edit_text(LEXICON['error_generic'])
        await show_session_menu(callback.message, callback.from_user.id)


@router.callback_query(F.data.startswith("code_digit:"), StateFilter(ConnectAccount.entering_code))
async def handle_code_digit(callback: CallbackQuery, state: FSMContext):
    digit = callback.data.split(":")[1]
    user_data = await state.get_data()
    current_code = user_data.get('current_code', "")

    if len(current_code) < CODE_LENGTH:
        current_code += digit
        await state.update_data(current_code=current_code)
        new_text = LEXICON['prompt_code_interactive'].format(masked_code=format_masked_code(current_code))
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(text=new_text, reply_markup=create_numeric_code_keyboard())
        if len(current_code) == CODE_LENGTH:
            await submit_code_logic(callback, state)
    await callback.answer()


@router.callback_query(F.data == "code_delete", StateFilter(ConnectAccount.entering_code))
async def handle_code_delete(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_code = user_data.get('current_code', "")
    if current_code:
        current_code = current_code[:-1]
        await state.update_data(current_code=current_code)
        new_text = LEXICON['prompt_code_interactive'].format(masked_code=format_masked_code(current_code))
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(text=new_text, reply_markup=create_numeric_code_keyboard())
    await callback.answer()


@router.callback_query(F.data == "code_send", StateFilter(ConnectAccount.entering_code))
async def handle_code_send(callback: CallbackQuery, state: FSMContext):
    await submit_code_logic(callback, state)
    await callback.answer()


@router.callback_query(F.data == "resend_code", StateFilter(ConnectAccount.entering_code))
async def handle_resend_code(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    client: TelegramClient = user_data.get('telethon_client')
    phone = user_data.get('phone')
    try:
        sent_code = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=sent_code.phone_code_hash, current_code="")
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(
                text=LEXICON['prompt_code_interactive'].format(masked_code=format_masked_code("")),
                reply_markup=create_numeric_code_keyboard()
            )
        await callback.answer(text=LEXICON['code_resent'], show_alert=True)
    except Exception:
        await callback.answer(LEXICON['error_generic'], show_alert=True)


@router.message(StateFilter(ConnectAccount.entering_password))
async def process_password(message: Message, state: FSMContext):
    password = message.text
    await message.delete()
    user_data = await state.get_data()
    client: TelegramClient = user_data.get('telethon_client')
    try:
        await client.sign_in(password=password)
        await complete_successful_connection(message, state)
    except PasswordHashInvalidError:
        await message.answer(
            text=LEXICON['error_invalid_password'],
            reply_markup=create_cancel_keyboard()
        )
    except Exception:
        if client.is_connected():
            await client.disconnect()
        await state.clear()
        await message.answer(LEXICON['error_generic'])
        await show_session_menu(message, message.from_user.id)