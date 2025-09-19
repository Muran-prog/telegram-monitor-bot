from contextlib import suppress
from unittest.mock import MagicMock

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from src.states.user_states import ChatManagement, ChatSettings
from src.database.queries import (
    db_get_chats, db_remove_chat, db_get_chat_settings, db_update_chat_setting
)
from src.utils.lexicon import LEXICON
from src.utils.helpers import get_details_for_callback
from src.keyboards.inline import (
    create_paginated_chat_list_keyboard, create_chat_details_menu,
    create_confirm_delete_chat_keyboard, create_chat_settings_menu,
    create_cancel_keyboard
)

router = Router()

# --- Chat List Display ---

async def display_chat_list(callback: CallbackQuery, phone: str, page: int):
    user_id = callback.from_user.id
    chats = db_get_chats(user_id, phone)
    if not chats:
        text = LEXICON['no_chats_monitored']
        reply_markup = InlineKeyboardBuilder().add(InlineKeyboardButton(text=LEXICON['back_button'], callback_data=f"view_session:{phone}")).as_markup()
    else:
        text = LEXICON['chat_list_title']
        reply_markup = create_paginated_chat_list_keyboard(chats, phone, current_page=page)
    await callback.message.edit_text(text, reply_markup=reply_markup)

@router.callback_query(F.data.startswith("my_chats:"))
async def my_chats_handler(callback: CallbackQuery):
    phone = callback.data.split(":", 1)[1]
    await display_chat_list(callback, phone, page=1)
    await callback.answer()

@router.callback_query(F.data.startswith("chat_page:"))
async def chat_list_page_handler(callback: CallbackQuery):
    _, phone, page = callback.data.split(":")
    await display_chat_list(callback, phone, int(page))
    await callback.answer()

# --- Chat Details & Deletion ---

@router.callback_query(F.data.startswith("view_chat:"))
async def view_chat_handler(callback: CallbackQuery):
    phone, chat_id, page = await get_details_for_callback(callback)
    user_id = callback.from_user.id
    chats = db_get_chats(user_id, phone)
    chat = next((c for c in chats if c['id'] == chat_id), None)
    if not chat:
        await callback.answer("Error: Chat not found.", show_alert=True)
        return
    await callback.message.edit_text(
        text=LEXICON['chat_details_title'].format(chat_title=chat['title']),
        reply_markup=create_chat_details_menu(phone, chat_id, page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_chat:"))
async def delete_chat_prompt_handler(callback: CallbackQuery, state: FSMContext):
    phone, chat_id, page = await get_details_for_callback(callback)
    user_id = callback.from_user.id
    chats = db_get_chats(user_id, phone)
    chat = next((c for c in chats if c['id'] == chat_id), None)
    if not chat:
        await callback.answer("Error: Chat not found.", show_alert=True)
        return
    await state.set_state(ChatManagement.confirm_delete_chat)
    await callback.message.edit_text(
        text=LEXICON['confirm_delete_chat_prompt'].format(chat_title=chat['title']),
        reply_markup=create_confirm_delete_chat_keyboard(phone, chat_id, page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_chat:"), StateFilter(ChatManagement.confirm_delete_chat))
async def confirm_delete_chat_handler(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    phone, chat_id_to_delete = parts[1], int(parts[2])
    user_id = callback.from_user.id
    chats = db_get_chats(user_id, phone)
    chat_to_delete = next((c for c in chats if c['id'] == chat_id_to_delete), None)
    if chat_to_delete:
        db_remove_chat(user_id, phone, chat_id_to_delete)
        await callback.answer(LEXICON['chat_deleted_success'].format(chat_title=chat_to_delete['title']), show_alert=True)
    await state.clear()
    await display_chat_list(callback, phone, page=1)


# --- Chat Settings ---

async def show_chat_settings_menu(callback: CallbackQuery):
    phone, chat_id, page = await get_details_for_callback(callback)
    settings = db_get_chat_settings(callback.from_user.id, phone, chat_id)
    if not settings:
        return await callback.answer("Error: Chat not found.", show_alert=True)
    
    autoclean_text = (
        LEXICON['autoclean_disabled_text'] if settings['db_autoclean_limit'] <= 0
        else LEXICON['autoclean_enabled_text'].format(count=settings['db_autoclean_limit'])
    )
    
    text = LEXICON['chat_settings_title'].format(chat_title=settings['title']) + "\n\n" + \
           LEXICON['chat_settings_menu_text'].format(
                frequency=settings['check_frequency_seconds'],
                initial_fetch=settings['initial_fetch_limit'],
                autoclean_limit=autoclean_text,
                download_media=LEXICON['on_text'] if settings['download_media'] else LEXICON['off_text'],
                detect_deletions=LEXICON['on_text'] if settings['detect_deletions'] else LEXICON['off_text']
            )
    await callback.message.edit_text(text, reply_markup=create_chat_settings_menu(phone, chat_id, page))


@router.callback_query(F.data.startswith("chat_settings:"))
async def chat_settings_handler(callback: CallbackQuery):
    await show_chat_settings_menu(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_setting:"))
async def toggle_setting_handler(callback: CallbackQuery):
    _, key, phone, chat_id_str, page_str = callback.data.split(':')
    chat_id, page, user_id = int(chat_id_str), int(page_str), callback.from_user.id
    settings = db_get_chat_settings(user_id, phone, chat_id)
    if not settings:
        return await callback.answer("Error.", show_alert=True)
    
    db_key_map = {'media': 'download_media', 'deletions': 'detect_deletions'}
    db_key = db_key_map[key]
    new_value = not settings[db_key]
    db_update_chat_setting(user_id, phone, chat_id, db_key, int(new_value))
    await callback.answer(LEXICON['setting_updated_alert'])
    await show_chat_settings_menu(callback)


@router.callback_query(F.data.startswith("set_setting:"))
async def set_setting_handler(callback: CallbackQuery, state: FSMContext):
    _, key, phone, chat_id, page = callback.data.split(':')
    await state.update_data(
        phone=phone,
        chat_id=int(chat_id),
        page=int(page),
        prompt_message_id=callback.message.message_id
    )
    prompts = {
        'freq': (ChatSettings.entering_frequency, LEXICON['prompt_frequency']),
        'fetch': (ChatSettings.entering_initial_fetch, LEXICON['prompt_initial_fetch']),
        'clean': (ChatSettings.entering_autoclean, LEXICON['prompt_autoclean'])
    }
    target_state, prompt_text = prompts[key]
    await state.set_state(target_state)
    await callback.message.edit_text(prompt_text, reply_markup=create_cancel_keyboard())
    await callback.answer()


async def process_numeric_setting(message: Message, state: FSMContext, bot: Bot, key: str, min_val: int = 0):
    if not message.text.isdigit():
        await message.answer(LEXICON['error_invalid_number'])
        return
    value = int(message.text)
    if value < min_val:
        await message.answer(LEXICON['error_invalid_number'])
        return

    data = await state.get_data()
    db_update_chat_setting(message.from_user.id, data['phone'], data['chat_id'], key, value)
    
    await message.delete()  # Delete user's numeric input message
    
    prompt_message_id = data.get('prompt_message_id')
    if prompt_message_id:
        with suppress(TelegramBadRequest):
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)

    await state.clear()
    
    # Recreate the settings menu after FSM is cleared
    temp_message = await bot.send_message(message.chat.id, "Updating settings...")
    await bot.send_message(message.chat.id, LEXICON['setting_updated_alert'])
    
    # Mock a callback to reuse the menu display function
    fake_callback = MagicMock()
    fake_callback.data = f"chat_settings:{data['phone']}:{data['chat_id']}:{data['page']}"
    fake_callback.from_user.id = message.from_user.id
    fake_callback.message = temp_message
    fake_callback.message.edit_text = temp_message.edit_text
    
    await show_chat_settings_menu(fake_callback)


@router.message(StateFilter(ChatSettings.entering_frequency))
async def process_frequency(message: Message, state: FSMContext, bot: Bot):
    await process_numeric_setting(message, state, bot, 'check_frequency_seconds', 5)

@router.message(StateFilter(ChatSettings.entering_initial_fetch))
async def process_initial_fetch(message: Message, state: FSMContext, bot: Bot):
    await process_numeric_setting(message, state, bot, 'initial_fetch_limit', 1)

@router.message(StateFilter(ChatSettings.entering_autoclean))
async def process_autoclean(message: Message, state: FSMContext, bot: Bot):
    await process_numeric_setting(message, state, bot, 'db_autoclean_limit', 0)