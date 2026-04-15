import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dotenv import load_dotenv
import uvicorn

from database.db import init_db
from handlers.crisis_handlers import crisis_router
from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router
from api_server import create_api_app

async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='Запустить бота'),
        BotCommand(command='/crisis', description='Если тяжело сейчас'),
        BotCommand(command='/profile', description='Мои заявки'),
        BotCommand(command='/tip', description='Совет дня'),
    ]
    await bot.set_my_commands(main_menu_commands)

async def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8080"))
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    await init_db()
    
    bot = Bot(token=token)
    dp = Dispatcher()
    api_app = create_api_app(bot)
    
    await set_main_menu(bot)
    
    dp.include_router(crisis_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    api_config = uvicorn.Config(api_app, host=api_host, port=api_port, log_level="info")
    api_server = uvicorn.Server(api_config)

    await bot.delete_webhook(drop_pending_updates=True)
    poll_task = asyncio.create_task(dp.start_polling(bot))
    api_task = asyncio.create_task(api_server.serve())

    done, pending = await asyncio.wait(
        {poll_task, api_task},
        return_when=asyncio.FIRST_EXCEPTION,
    )
    for task in pending:
        task.cancel()
    for task in done:
        task.result()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
