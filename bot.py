import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.config import load_config
from src.database.models import init_db
from src.globals import monitoring_tasks
from src.handlers import (
    add_chat_fsm,
    chat_management,
    connect_account_fsm,
    session_management,
    statistics,
)

async def main():
    """Main function to initialize and run the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize database
    init_db()

    # Load configuration
    config = load_config()

    # Initialize Bot and Dispatcher
    bot = Bot(
        token=config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register routers
    dp.include_router(connect_account_fsm.router)
    dp.include_router(session_management.router)
    dp.include_router(add_chat_fsm.router)
    dp.include_router(chat_management.router)
    dp.include_router(statistics.router)

    # Drop pending updates
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logging.info("Bot is starting...")
        await dp.start_polling(bot)
    finally:
        logging.info("Stopping monitoring tasks...")
        tasks_to_await = []
        for session_info in monitoring_tasks.values():
            if session_info.get('supervisor'):
                session_info['supervisor'].cancel()
                tasks_to_await.append(session_info['supervisor'])

        if tasks_to_await:
            await asyncio.gather(*tasks_to_await, return_exceptions=True)

        await bot.session.close()
        logging.info("Bot has been stopped.")

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")
