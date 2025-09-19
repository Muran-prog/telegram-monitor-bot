import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config import DOWNLOADS_DIR, SESSIONS_DIR, SUPERVISOR_SLEEP_INTERVAL
from src.database.queries import (
    db_add_message, db_autoclean_messages, db_get_chat_settings,
    db_get_chats, db_get_last_message_id, db_get_recent_active_messages,
    db_get_session_credentials, db_mark_message_as_deleted
)
from src.globals import monitoring_tasks
from src.utils.lexicon import LEXICON

async def notify_user_of_deletion(bot: Bot, user_id: int, session_phone: str, chat_title: str, deleted_message_details: dict):
    header = LEXICON['deletion_notification_title']
    try:
        date_obj = datetime.fromisoformat(deleted_message_details['date'])
        date_str = date_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, TypeError):
        date_str = "N/A"
    
    body = LEXICON['deletion_notification_body'].format(
        chat_title=chat_title, session_phone=session_phone, date=date_str
    )
    
    content = ""
    if deleted_message_details.get('text'):
        content += LEXICON['deleted_text_content'].format(text=deleted_message_details['text'])
    if deleted_message_details.get('file_path'):
        content += "\n" + LEXICON['deleted_file_content'].format(file_path=deleted_message_details['file_path'])
    if not content:
        content = LEXICON['deleted_media_only_content']
        
    full_message = f"{header}\n{body}{content}"
    
    try:
        await bot.send_message(user_id, full_message)
    except TelegramBadRequest as e:
        logging.warning(f"Failed to send deletion notification to user {user_id}: {e}")

async def chat_worker(user_id: int, session_phone: str, chat_id: int, client: TelegramClient, bot: Bot):
    while True:
        try:
            settings = db_get_chat_settings(user_id, session_phone, chat_id)
            if not settings:
                logging.warning(f"Chat {chat_id} removed from DB for {session_phone}. Worker stopping.")
                break

            last_id = db_get_last_message_id(session_phone, chat_id)
            
            messages_to_process = []
            if last_id == 0:
                async for msg in client.iter_messages(chat_id, limit=settings['initial_fetch_limit']):
                    messages_to_process.append(msg)
            else:
                async for msg in client.iter_messages(chat_id, min_id=last_id):
                    messages_to_process.append(msg)
            
            for msg in reversed(messages_to_process):
                file_path, file_size = None, None
                if settings['download_media'] and msg.media and not getattr(msg, 'web_preview', None):
                    with suppress(Exception):
                        file_path = await msg.download_media(file=DOWNLOADS_DIR)
                        if file_path and os.path.exists(file_path):
                            file_size = os.path.getsize(file_path)

                sender_id_val = getattr(msg.sender_id, 'user_id', msg.sender_id) if msg.sender_id else None
                db_add_message(msg.id, chat_id, session_phone, msg.text, sender_id_val, msg.date, file_path, file_size)
            
            if settings['detect_deletions']:
                db_msgs = db_get_recent_active_messages(session_phone, chat_id)
                if db_msgs:
                    ids_to_check = [m['telethon_message_id'] for m in db_msgs]
                    live_msgs = {m.id for m in await client.get_messages(chat_id, ids=ids_to_check) if m}
                    for db_msg in db_msgs:
                        if db_msg['telethon_message_id'] not in live_msgs:
                            await notify_user_of_deletion(bot, user_id, session_phone, settings['title'], db_msg)
                            db_mark_message_as_deleted(db_msg['id'])
            
            if settings['db_autoclean_limit'] > 0:
                db_autoclean_messages(session_phone, chat_id, settings['db_autoclean_limit'])
            
            await asyncio.sleep(settings['check_frequency_seconds'])

        except asyncio.CancelledError:
            logging.info(f"Worker for chat {chat_id} ({session_phone}) cancelled.")
            break
        except Exception as e:
            logging.error(f"Error in worker for chat {chat_id} ({session_phone}): {e}. Retrying in 60s.")
            await asyncio.sleep(60)

async def session_supervisor(user_id: int, session_phone: str, bot: Bot):
    task_key = (user_id, session_phone)
    if task_key not in monitoring_tasks:
        return
    monitoring_tasks[task_key]['workers'] = {}

    credentials = db_get_session_credentials(user_id, session_phone)
    session_path = SESSIONS_DIR / f"{user_id}_{session_phone}.session"

    if not credentials or not session_path.exists():
        logging.error(f"Credentials or session file for {session_phone} not found. Supervisor exiting.")
        return
    
    api_id, api_hash = credentials
    with open(session_path, "r") as f:
        session_string = f.read()
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)

    try:
        while True: # Main reconnection loop
            try:
                logging.info(f"Supervisor for {session_phone} connecting...")
                await client.connect()
                logging.info(f"Supervisor for {session_phone} connected.")
                
                while True: # Worker management loop
                    if not await client.is_user_authorized():
                        logging.warning(f"Auth lost for {session_phone}. Supervisor pausing.")
                        await asyncio.sleep(300)
                        continue

                    db_chats = {c['id'] for c in db_get_chats(user_id, session_phone)}
                    running_workers = set(monitoring_tasks[task_key]['workers'].keys())
                    
                    for chat_id in db_chats - running_workers:
                        logging.info(f"Supervisor starting worker for new chat {chat_id} on {session_phone}")
                        task = asyncio.create_task(chat_worker(user_id, session_phone, chat_id, client, bot))
                        monitoring_tasks[task_key]['workers'][chat_id] = task
                    
                    for chat_id in running_workers - db_chats:
                        logging.info(f"Supervisor stopping worker for removed chat {chat_id} on {session_phone}")
                        task = monitoring_tasks[task_key]['workers'].pop(chat_id)
                        task.cancel()
                    
                    await asyncio.sleep(SUPERVISOR_SLEEP_INTERVAL)

            except asyncio.CancelledError:
                logging.info(f"Supervisor for {session_phone} received cancellation request.")
                break
            except Exception as e:
                logging.error(f"Supervisor for {session_phone} encountered an error: {e}. Reconnecting in 60s.")
                if client.is_connected():
                    await client.disconnect()
                await asyncio.sleep(60)

    except asyncio.CancelledError:
        logging.info(f"Supervisor for {session_phone} cancelled during setup.")
    finally:
        logging.info(f"Cleaning up supervisor for {session_phone}.")
        worker_tasks_to_cancel = []
        if task_key in monitoring_tasks and 'workers' in monitoring_tasks[task_key]:
            for worker_task in monitoring_tasks[task_key]['workers'].values():
                worker_task.cancel()
                worker_tasks_to_cancel.append(worker_task)
        
        if worker_tasks_to_cancel:
            await asyncio.gather(*worker_tasks_to_cancel, return_exceptions=True)

        if client.is_connected():
            await client.disconnect()
        logging.info(f"Supervisor for {session_phone} has been stopped.")