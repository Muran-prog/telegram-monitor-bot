from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from src.database.queries import db_get_chats, db_calculate_chat_statistics, db_get_chat_settings
from src.keyboards.inline import create_statistics_list_keyboard, create_detailed_stats_keyboard
from src.utils.helpers import format_bytes
from src.utils.lexicon import LEXICON

router = Router()

async def display_statistics_list(callback: CallbackQuery, phone: str, sort_key: str, page: int):
    user_id = callback.from_user.id
    chats = db_get_chats(user_id, phone)
    
    if not chats:
        await callback.message.edit_text(
            LEXICON['no_chats_monitored'],
            reply_markup=InlineKeyboardBuilder().add(InlineKeyboardButton(text=LEXICON['back_button'], callback_data=f"view_session:{phone}")).as_markup()
        )
        return

    chats_with_stats = []
    for chat in chats:
        stats = db_calculate_chat_statistics(phone, chat['id'])
        chats_with_stats.append({**chat, **stats})
    
    sort_map = {
        'total': ('total_messages', True),
        'deleted': ('deleted_messages', True),
        'volume': ('media_size_bytes', True),
        'activity': ('last_message_ts', True),
    }
    sort_field, reverse = sort_map.get(sort_key, ('total_messages', True))
    
    chats_with_stats.sort(key=lambda x: (x[sort_field] is not None, x[sort_field]), reverse=reverse)

    if not any(c['total_messages'] > 0 for c in chats_with_stats):
        text = LEXICON['no_stats_yet']
    else:
        text = LEXICON['statistics_title'].format(phone=phone)
    
    reply_markup = create_statistics_list_keyboard(chats_with_stats, phone, sort_key, current_page=page)
    await callback.message.edit_text(text, reply_markup=reply_markup)


@router.callback_query(F.data.startswith("stats_menu:"))
async def statistics_menu_handler(callback: CallbackQuery):
    phone = callback.data.split(":", 1)[1]
    await display_statistics_list(callback, phone, sort_key='total', page=1)
    await callback.answer()

@router.callback_query(F.data.startswith("stats_page:"))
async def stats_page_handler(callback: CallbackQuery):
    _, phone, sort_key, page = callback.data.split(":")
    await display_statistics_list(callback, phone, sort_key, int(page))
    await callback.answer()

@router.callback_query(F.data.startswith("stats_sort:"))
async def stats_sort_handler(callback: CallbackQuery):
    _, phone, sort_key, page = callback.data.split(":")
    await display_statistics_list(callback, phone, sort_key, int(page))
    await callback.answer()

@router.callback_query(F.data.startswith("view_stats:"))
async def view_detailed_stats_handler(callback: CallbackQuery):
    _, phone, chat_id_str, sort_key, page_str = callback.data.split(":")
    chat_id, page = int(chat_id_str), int(page_str)
    user_id = callback.from_user.id

    chat_info = db_get_chat_settings(user_id, phone, chat_id)
    if not chat_info:
        return await callback.answer("Chat not found.", show_alert=True)
    
    stats = db_calculate_chat_statistics(phone, chat_id)

    def format_ts(ts):
        if not ts: return LEXICON['stats_not_available']
        return datetime.fromisoformat(ts).strftime('%Y-%m-%d %H:%M:%S')

    deletion_rate = (stats['deleted_messages'] / stats['total_messages'] * 100) if stats['total_messages'] > 0 else 0

    text = LEXICON['detailed_stats_title'].format(chat_title=chat_info['title']) + "\n\n" + \
           LEXICON['detailed_stats_template'].format(
                total_messages=stats['total_messages'],
                first_message=format_ts(stats['first_message_ts']),
                last_message=format_ts(stats['last_message_ts']),
                deleted_messages=stats['deleted_messages'],
                deletion_rate=deletion_rate,
                media_files=stats['media_files'],
                media_volume=format_bytes(stats['media_size_bytes'])
            )
            
    reply_markup = create_detailed_stats_keyboard(phone, sort_key, page)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()