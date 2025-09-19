import asyncio
import logging
import os
from contextlib import suppress

from aiogram import F, Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config import SESSIONS_DIR
from src.database.queries import (
    db_get_session_credentials, db_get_chats, db_remove_session_credentials,
    db_remove_all_chats_for_session
)
from src.globals import active_sessions, monitoring_tasks
from src.keyboards.inline import (
    create_session_management_menu, create_session_details_menu,
    create_confirm_delete_keyboard
)
from src.services.monitoring import session_supervisor
from src.states.user_states import SessionManagement
from src.utils.helpers import get_user_sessions
from src.utils.lexicon import LEXICON

router = Router()

# --- Main Menu & Session List ---

async def show_session_menu(message_or_callback: Message | CallbackQuery, user_id: int):
    sessions = get_user_sessions(user_id)
    active_session = active_sessions.get(user_id)

    if not sessions:
        text, reply_markup = LEXICON['start_message_no_sessions'], create_session_management_menu([], None)
    else:
        text, reply_markup = LEXICON['session_menu_title'], create_session_management_menu(sessions, active_session)
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=reply_markup)
    else:
        with suppress(TelegramBadRequest):
            await message_or_callback.message.edit_text(text, reply_markup=reply_markup)

@router.message(CommandStart())
@router.message(Command("menu"))
async def handle_start_command(message: Message, state: FSMContext):
    await state.clear()
    await show_session_menu(message, message.from_user.id)

@router.callback_query(F.data == "back_to_sessions")
async def back_to_session_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_session_menu(callback, callback.from_user.id)
    await callback.answer()

# --- Session Details & Actions ---

async def show_session_details(message_or_callback: Message | CallbackQuery, user_id: int, phone: str):
    message_to_edit = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    
    credentials = db_get_session_credentials(user_id, phone)
    session_path = SESSIONS_DIR / f"{user_id}_{phone}.session"

    if not credentials or not session_path.exists():
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer("Error: Session data not found.", show_alert=True)
        return

    api_id, api_hash = credentials
    with open(session_path, "r") as f:
        session_string = f.read()
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            status, first_name, last_name, tg_user_id = "🟢 Online", me.first_name, me.last_name or "", me.id
        else:
            status, first_name, last_name, tg_user_id = "🔴 Disconnected", "N/A", "", "N/A"
        
        task_key = (user_id, phone)
        is_monitoring = task_key in monitoring_tasks and not monitoring_tasks[task_key]['supervisor'].done()
        monitoring_status = LEXICON['monitoring_status_active'] if is_monitoring else LEXICON['monitoring_status_inactive']
        
        text = LEXICON['session_details_template'].format(
            first_name=first_name, last_name=last_name, phone=phone, user_id=tg_user_id,
            status=status, monitoring_status=monitoring_status
        )
        monitored_chats_count = len(db_get_chats(user_id, phone))
        reply_markup = create_session_details_menu(phone, monitored_chats_count, is_monitoring)
        
        await message_to_edit.edit_text(text, reply_markup=reply_markup)

    except Exception as e:
        logging.error(f"Failed to connect to session {phone}: {e}")
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer("Error: Could not connect to this session.", show_alert=True)
    finally:
        if client.is_connected():
            await client.disconnect()

@router.callback_query(F.data.startswith("view_session:"))
async def view_session_details_handler(callback: CallbackQuery):
    phone = callback.data.split(":", 1)[1]
    await show_session_details(callback, callback.from_user.id, phone)
    await callback.answer()

@router.callback_query(F.data.startswith("set_active:"))
async def set_active_session_handler(callback: CallbackQuery):
    phone = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    active_sessions[user_id] = phone
    await show_session_menu(callback, user_id)
    await callback.answer(LEXICON['session_set_active_alert'].format(phone=phone), show_alert=True)

@router.callback_query(F.data.startswith("delete_session:"))
async def delete_session_prompt(callback: CallbackQuery, state: FSMContext):
    phone = callback.data.split(":", 1)[1]
    await state.set_state(SessionManagement.confirm_delete)
    await callback.message.edit_text(
        LEXICON['confirm_delete_prompt'].format(phone=phone),
        reply_markup=create_confirm_delete_keyboard(phone)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_yes:"), StateFilter(SessionManagement.confirm_delete))
async def confirm_delete_session(callback: CallbackQuery, state: FSMContext):
    phone = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    # Stop monitoring if active
    task_key = (user_id, phone)
    session_task_info = monitoring_tasks.pop(task_key, None)
    if session_task_info and not session_task_info['supervisor'].done():
        session_task_info['supervisor'].cancel()
        
    # Delete session file
    session_file = SESSIONS_DIR / f"{user_id}_{phone}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        
    # Clean up database
    db_remove_session_credentials(user_id, phone)
    db_remove_all_chats_for_session(user_id, phone)
    
    # Clear from active session cache
    if active_sessions.get(user_id) == phone:
        del active_sessions[user_id]
        
    await callback.answer(LEXICON['session_deleted_message'].format(phone=phone), show_alert=True)
    await state.clear()
    await show_session_menu(callback, user_id)

# --- Monitoring Control ---

@router.callback_query(F.data.startswith("start_monitoring:"))
async def start_monitoring_handler(callback: CallbackQuery, bot: Bot):
    phone = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    task_key = (user_id, phone)
    
    if task_key in monitoring_tasks and not monitoring_tasks[task_key]['supervisor'].done():
        await callback.answer("Monitoring is already active.", show_alert=True)
        return
        
    supervisor_task = asyncio.create_task(session_supervisor(user_id, phone, bot))
    monitoring_tasks[task_key] = {'supervisor': supervisor_task, 'workers': {}}
    
    await callback.answer(LEXICON['monitoring_started_alert'], show_alert=True)
    await show_session_details(callback, user_id, phone)

@router.callback_query(F.data.startswith("stop_monitoring:"))
async def stop_monitoring_handler(callback: CallbackQuery):
    phone = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    task_key = (user_id, phone)
    
    session_task_info = monitoring_tasks.pop(task_key, None)
    if session_task_info and not session_task_info['supervisor'].done():
        session_task_info['supervisor'].cancel()
        await callback.answer(LEXICON['monitoring_stopped_alert'], show_alert=True)
    else:
        await callback.answer("Monitoring is not currently active.", show_alert=True)
        
    await show_session_details(callback, user_id, phone)