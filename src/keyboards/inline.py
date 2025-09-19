import math
from typing import List, Dict, Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.lexicon import LEXICON

def create_session_management_menu(sessions: List[str], active_session: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for session_phone in sessions:
        text = f"⭐ {session_phone}" if session_phone == active_session else session_phone
        builder.row(InlineKeyboardButton(text=text, callback_data=f"view_session:{session_phone}"))
    builder.row(InlineKeyboardButton(text=LEXICON['add_new_account_button'], callback_data="connect_account_pressed"))
    return builder.as_markup()

def create_session_details_menu(phone: str, num_chats: int, is_monitoring: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=LEXICON['set_active_button'], callback_data=f"set_active:{phone}"),
        InlineKeyboardButton(text=LEXICON['delete_button'], callback_data=f"delete_session:{phone}")
    )
    if is_monitoring:
        builder.row(InlineKeyboardButton(text=LEXICON['stop_monitoring_button'], callback_data=f"stop_monitoring:{phone}"))
    else:
        builder.row(InlineKeyboardButton(text=LEXICON['start_monitoring_button'], callback_data=f"start_monitoring:{phone}"))
    builder.row(
        InlineKeyboardButton(text=f"{num_chats}{LEXICON['my_chats_button']}", callback_data=f"my_chats:{phone}"),
        InlineKeyboardButton(text=LEXICON['statistics_button'], callback_data=f"stats_menu:{phone}")
    )
    builder.row(InlineKeyboardButton(text=LEXICON['add_chat_button'], callback_data=f"add_chat:{phone}"))
    builder.row(InlineKeyboardButton(text=LEXICON['back_button'], callback_data="back_to_sessions"))
    return builder.as_markup()

def create_paginated_chat_list_keyboard(chats: List[Dict[str, Any]], phone: str, current_page: int = 1, items_per_page: int = 5) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    total_items = len(chats)
    total_pages = math.ceil(total_items / items_per_page)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    for chat in chats[start_index:end_index]:
        title = (chat['title'][:48] + '...') if len(chat['title']) > 50 else chat['title']
        callback_data = f"view_chat:{phone}:{chat['id']}:{current_page}"
        builder.row(InlineKeyboardButton(text=title, callback_data=callback_data))
        
    if total_pages > 1:
        page_nav_row = []
        if current_page > 1:
            page_nav_row.extend([
                InlineKeyboardButton(text=LEXICON['first_page'], callback_data=f"chat_page:{phone}:1"),
                InlineKeyboardButton(text=LEXICON['prev_page'], callback_data=f"chat_page:{phone}:{current_page - 1}")
            ])
        if current_page < total_pages:
            page_nav_row.extend([
                InlineKeyboardButton(text=LEXICON['next_page'], callback_data=f"chat_page:{phone}:{current_page + 1}"),
                InlineKeyboardButton(text=LEXICON['last_page'], callback_data=f"chat_page:{phone}:{total_pages}")
            ])
        builder.row(InlineKeyboardButton(text=LEXICON['page_counter'].format(current_page=current_page, total_pages=total_pages), callback_data="ignore"))
        if page_nav_row:
            builder.row(*page_nav_row)
            
    builder.row(InlineKeyboardButton(text=LEXICON['back_button'], callback_data=f"view_session:{phone}"))
    return builder.as_markup()

def create_chat_details_menu(phone: str, chat_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LEXICON['chat_settings_button'], callback_data=f"chat_settings:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['delete_chat_button'], callback_data=f"delete_chat:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['back_to_chats_button'], callback_data=f"chat_page:{phone}:{page}"))
    return builder.as_markup()

def create_chat_settings_menu(phone: str, chat_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LEXICON['set_frequency_button'], callback_data=f"set_setting:freq:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['set_initial_fetch_button'], callback_data=f"set_setting:fetch:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['set_autoclean_button'], callback_data=f"set_setting:clean:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['toggle_media_button'], callback_data=f"toggle_setting:media:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['toggle_deletions_button'], callback_data=f"toggle_setting:deletions:{phone}:{chat_id}:{page}"))
    builder.row(InlineKeyboardButton(text=LEXICON['back_to_chat_details_button'], callback_data=f"view_chat:{phone}:{chat_id}:{page}"))
    return builder.as_markup()

def create_confirm_delete_keyboard(phone: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=LEXICON['confirm_delete_yes'], callback_data=f"confirm_delete_yes:{phone}"),
        InlineKeyboardButton(text=LEXICON['confirm_delete_no'], callback_data="back_to_sessions")
    )
    return builder.as_markup()

def create_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LEXICON['cancel_button'], callback_data="cancel_connection"))
    return builder.as_markup()

def create_numeric_code_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 10):
        builder.add(InlineKeyboardButton(text=str(i), callback_data=f"code_digit:{i}"))
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text=LEXICON['delete_button_kb'], callback_data="code_delete"),
        InlineKeyboardButton(text="0", callback_data="code_digit:0"),
        InlineKeyboardButton(text=LEXICON['send_code_button'], callback_data="code_send")
    )
    builder.row(
        InlineKeyboardButton(text=LEXICON['resend_code_button'], callback_data="resend_code"),
        InlineKeyboardButton(text=LEXICON['cancel_button'], callback_data="cancel_connection")
    )
    return builder.as_markup()

def create_confirm_delete_chat_keyboard(phone: str, chat_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=LEXICON['confirm_delete_yes'], callback_data=f"confirm_delete_chat:{phone}:{chat_id}:{page}"),
        InlineKeyboardButton(text=LEXICON['confirm_delete_no'], callback_data=f"view_chat:{phone}:{chat_id}:{page}")
    )
    return builder.as_markup()

def create_statistics_list_keyboard(chats_with_stats: List[Dict[str, Any]], phone: str, sort_key: str, current_page: int = 1, items_per_page: int = 5) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    sort_buttons = {
        'total': LEXICON['sort_by_total'],
        'deleted': LEXICON['sort_by_deleted'],
        'volume': LEXICON['sort_by_volume'],
        'activity': LEXICON['sort_by_activity'],
    }
    sort_row = [
        InlineKeyboardButton(
            text=f"✅ {text}" if key == sort_key else text,
            callback_data=f"stats_sort:{phone}:{key}:1"
        ) for key, text in sort_buttons.items()
    ]
    builder.row(*sort_row)

    total_items = len(chats_with_stats)
    total_pages = math.ceil(total_items / items_per_page)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page

    for chat in chats_with_stats[start_index:end_index]:
        title = (chat['title'][:48] + '...') if len(chat['title']) > 50 else chat['title']
        callback_data = f"view_stats:{phone}:{chat['id']}:{sort_key}:{current_page}"
        builder.row(InlineKeyboardButton(text=title, callback_data=callback_data))

    if total_pages > 1:
        page_nav_row = []
        if current_page > 1:
            page_nav_row.extend([
                InlineKeyboardButton(text=LEXICON['first_page'], callback_data=f"stats_page:{phone}:{sort_key}:1"),
                InlineKeyboardButton(text=LEXICON['prev_page'], callback_data=f"stats_page:{phone}:{sort_key}:{current_page-1}")
            ])
        if current_page < total_pages:
            page_nav_row.extend([
                InlineKeyboardButton(text=LEXICON['next_page'], callback_data=f"stats_page:{phone}:{sort_key}:{current_page+1}"),
                InlineKeyboardButton(text=LEXICON['last_page'], callback_data=f"stats_page:{phone}:{sort_key}:{total_pages}")
            ])
        builder.row(InlineKeyboardButton(text=LEXICON['page_counter'].format(current_page=current_page, total_pages=total_pages), callback_data="ignore"))
        if page_nav_row:
            builder.row(*page_nav_row)

    builder.row(InlineKeyboardButton(text=LEXICON['back_button'], callback_data=f"view_session:{phone}"))
    return builder.as_markup()

def create_detailed_stats_keyboard(phone: str, sort_key: str, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LEXICON['back_to_stats_button'], callback_data=f"stats_page:{phone}:{sort_key}:{page}"))
    return builder.as_markup()