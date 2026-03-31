import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8693230772:AAH04ixsC8G7O4i-gIr9X5GkcYcAX1lInrk"

TYUMEN_TZ = timezone(timedelta(hours=7))
CONFIG_FILE = Path("config.json")

default_config = {
    "chat_id": None,
    "auto_poll_enabled": True,
    "last_sent_date": None
}

dp = Dispatcher()
config = default_config.copy()


def load_config():
    global config
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            config.update(data)
        except Exception:
            pass


def save_config():
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


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


def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Создать опрос сейчас")],
            [KeyboardButton(text="💾 Сохранить чат")],
            [KeyboardButton(text="🕒 Автоопрос")],
        ],
        resize_keyboard=True
    )
    return kb


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
    load_config()
    await message.answer("Бот запущен. Меню ниже 👇", reply_markup=main_menu_keyboard())


@dp.message()
async def menu_handler(message: Message):
    text = message.text.strip()

    if text == "💾 Сохранить чат":
        if message.chat.type == "private":
            await message.answer("Эту команду нужно использовать в группе или канале.")
            return
        config["chat_id"] = message.chat.id
        save_config()
        await message.answer(f"Чат сохранён: {config['chat_id']}")

    elif text == "📊 Создать опрос сейчас":
        if not config.get("chat_id"):
            await message.answer("Сначала нужно сохранить чат через '💾 Сохранить чат'")
            return
        await send_poll(message.bot, config["chat_id"])
        config["last_sent_date"] = datetime.now(TYUMEN_TZ).isoformat()
        save_config()
        await message.answer("Опрос отправлен ✅")

    elif text == "🕒 Автоопрос":
        config["auto_poll_enabled"] = True
        save_config()
        await message.answer("Автоматический опрос включён. Он будет отправляться каждые 24 часа.")


async def auto_poll_scheduler(bot: Bot):
    """Отправка опроса каждые 24 часа"""
    while True:
        if config.get("chat_id") and config.get("auto_poll_enabled"):
            last_sent = config.get("last_sent_date")
            now = datetime.now(TYUMEN_TZ)

            # если последний опрос был не сегодня, отправляем
            if not last_sent or (datetime.fromisoformat(last_sent).date() < now.date()):
                try:
                    await send_poll(bot, config["chat_id"])
                    config["last_sent_date"] = now.isoformat()
                    save_config()
                    print(f"Автоопрос отправлен {now}")
                except Exception as e:
                    print(f"Ошибка при отправке автоопроса: {e}")

        await asyncio.sleep(60)  # проверка каждую минуту


async def main():
    load_config()
    bot = Bot(token=TOKEN)
    asyncio.create_task(auto_poll_scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
