import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dotenv import load_dotenv

from database.db import init_db
from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router

async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='Запустить бота'),
        BotCommand(command='/profile', description='Мои заявки'),
        BotCommand(command='/tip', description='Совет дня')
    ]
    await bot.set_my_commands(main_menu_commands)

async def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    await init_db()
    
    bot = Bot(token=token)
    dp = Dispatcher()
    
    await set_main_menu(bot)
    
    dp.include_router(admin_router)
    dp.include_router(user_router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
