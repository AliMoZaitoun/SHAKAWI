import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import SimpleEventIsolation
from bot.config import BOT_TOKEN
from bot.handlers import complaint_flow, evidence

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(events_isolation=SimpleEventIsolation())
    
    dp.include_router(evidence.router)
    dp.include_router(complaint_flow.router)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    await bot.set_my_commands([
        BotCommand(command="start", description="🚀 القائمة الرئيسية"),
        BotCommand(command="new", description="⚡ تقديم شكوى جديدة فوراً"),
        BotCommand(command="mystatus", description="🔍 الاستعلام عن حالة شكوى"),
        BotCommand(command="track", description="تتبع شكوى محددة"),
        BotCommand(command="cancel", description="❌ إلغاء العملية"),
    ], language_code="ar")

    await bot.set_my_commands([
        BotCommand(command="start", description="🚀 Main Menu"),
        BotCommand(command="new", description="⚡ File new complaint instantly"),
        BotCommand(command="mystatus", description="🔍 Check complaint status"),
        BotCommand(command="track", description="Track specific complaint"),
        BotCommand(command="cancel", description="❌ Cancel current operation"),
    ], language_code="en")

    await bot.set_my_commands([
        BotCommand(command="start", description="Main Menu"),
        BotCommand(command="new", description="File new complaint instantly"),
        BotCommand(command="mystatus", description="Check complaint status"),
        BotCommand(command="track", description="Track complaint"),
        BotCommand(command="cancel", description="Cancel"),
    ])
    
    print("🤖 Telegram Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())