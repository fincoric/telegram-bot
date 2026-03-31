import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Берём токен из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения!")

SEND_HOUR = 9
SEND_MINUTE = 0

POLL_QUESTION = "На какой паре ты сегодня будешь?"
POLL_OPTIONS = [
    "1 пара 08:30 - 10:00",
    "2 пара 10:15 - 11:45",
    "3 пара 12:05 - 13:35",
    "4 пара 14:05 - 15:35",
    "5 пара 15:55 - 17:25",
    "6 пара 17:40 - 19:10",
    "Меня не будет",
    "Я еще не определился(-ась)"
]

CONFIG_FILE = Path("config.json")

dp = Dispatcher()
target_chat_id: Optional[int] = None


def load_chat_id() -> Optional[int]:
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        value = data.get("chat_id")
        return int(value) if value else None
    except Exception:
        return None


def save_chat_id(chat_id: int) -> None:
    CONFIG_FILE.write_text(
        json.dumps({"chat_id": chat_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def panel_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📩 Отправить опрос сейчас", callback_data="send_poll_now")
    return kb.as_markup()


async def send_poll(bot: Bot, chat_id: int):
    await bot.send_poll(
        chat_id=chat_id,
        question=POLL_QUESTION,
        options=POLL_OPTIONS,
        is_anonymous=False,
        allows_multiple_answers=True,
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Бот запущен.\n"
        "Напиши /setchat в нужной группе или канале, чтобы сохранить чат.\n"
        "Напиши /panel, чтобы открыть кнопку ручной отправки."
    )


@dp.message(Command("setchat"))
async def setchat_handler(message: Message):
    global target_chat_id

    if message.chat.type == "private":
        await message.answer("Открой /setchat в нужной группе или канале, а не в личке.")
        return

    target_chat_id = message.chat.id
    save_chat_id(target_chat_id)
    await message.answer(f"Чат сохранён: {target_chat_id}")


@dp.message(Command("panel"))
async def panel_handler(message: Message):
    await message.answer("Панель управления:", reply_markup=panel_keyboard())


@dp.callback_query(F.data == "send_poll_now")
async def send_poll_now(callback: CallbackQuery, bot: Bot):
    await callback.answer("Отправляю опрос...")

    if target_chat_id is None:
        await callback.message.answer("Сначала отправь /setchat в нужной группе или канале.")
        return

    try:
        await send_poll(bot, target_chat_id)
        await callback.message.answer("Опрос отправлен ✅")
    except Exception as e:
        await callback.message.answer(f"Не удалось отправить опрос: {e}")


async def scheduler(bot: Bot):
    global target_chat_id
    last_sent_date = None

    while True:
        now = datetime.now()

        if target_chat_id:
            if now.hour == SEND_HOUR and now.minute == SEND_MINUTE:
                if last_sent_date != now.date():
                    try:
                        await send_poll(bot, target_chat_id)
                        last_sent_date = now.date()
                    except Exception:
                        pass

        await asyncio.sleep(20)


async def main():
    global target_chat_id
    target_chat_id = load_chat_id()

    bot = Bot(token=TOKEN)
    asyncio.create_task(scheduler(bot))
    # Запуск polling без портов
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
