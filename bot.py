import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")

TYUMEN_TZ = timezone(timedelta(hours=7))
CONFIG_FILE = Path("config.json")

default_config = {
    "chat_id": None,
    "daily_poll_hour": 0,
    "daily_poll_minute": 0,
    "scheduled_poll_datetime": None,
    "last_sent_date": None,
    "last_sent_scheduled": None,
    "awaiting_time_input": False,
    "awaiting_date_input": False
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


async def get_current_time_tumen() -> datetime:
    """Попытка получить точное время из интернета (вспомогательно)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://worldtimeapi.org/api/timezone/Asia/Yekaterinburg", timeout=5) as resp:
                data = await resp.json()
                dt = datetime.fromisoformat(data["datetime"])
                return dt
    except Exception:
        # fallback на локальное системное время
        return datetime.now(TYUMEN_TZ)


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Опрос")],
            [KeyboardButton(text="💾 Сохранить чат")],
            [KeyboardButton(text="⚙ Панель управления")]
        ],
        resize_keyboard=True
    )


def poll_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏱ Проверка таймера опроса")],
            [KeyboardButton(text="📊 Создать опрос сейчас")],
            [KeyboardButton(text="🕒 Автоматические опросы")],
            [KeyboardButton(text="⬅ Назад")]
        ],
        resize_keyboard=True
    )


def panel_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📩 Отправить опрос сейчас", callback_data="send_poll_now")
    return kb.as_markup()


def auto_poll_inline_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Ежедневно", callback_data="daily_poll"),
            InlineKeyboardButton(text="По дате", callback_data="date_poll")
        ]
    ])
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
    await message.answer(
        "Бот запущен.\nИспользуй меню ниже 👇",
        reply_markup=main_menu_keyboard()
    )


@dp.message()
async def menu_handler(message: Message):
    text = message.text.strip()

    if config.get("awaiting_time_input"):
        await handle_time_input(message)
        return
    if config.get("awaiting_date_input"):
        await handle_date_input(message)
        return

    if text == "💾 Сохранить чат":
        if message.chat.type == "private":
            await message.answer("Эту команду нужно использовать в группе или канале.")
            return
        config["chat_id"] = message.chat.id
        save_config()
        await message.answer(f"Чат сохранён: {config['chat_id']}")

    elif text == "⚙ Панель управления":
        await message.answer("Панель управления:", reply_markup=panel_keyboard())

    elif text == "📝 Опрос":
        await message.answer("Меню опроса:", reply_markup=poll_menu_keyboard())

    elif text == "⏱ Проверка таймера опроса":
        msg = f"⏱ Ежедневный опрос: {config['daily_poll_hour']:02d}:{config['daily_poll_minute']:02d}\n"
        msg += f"Опрос по дате: {config['scheduled_poll_datetime'] if config['scheduled_poll_datetime'] else 'не задан'}\n"
        msg += f"Последняя отправка: {config.get('last_sent_date', 'никогда')}\n"
        msg += "Для изменения ежедневного опроса или даты нажми '🕒 Автоматические опросы'."
        await message.answer(msg)

    elif text == "📊 Создать опрос сейчас":
        if not config["chat_id"]:
            await message.answer("Сначала нужно сохранить чат через '💾 Сохранить чат'")
            return
        await send_poll(message.bot, config["chat_id"])
        config["last_sent_date"] = datetime.now(TYUMEN_TZ).isoformat()
        save_config()
        await message.answer("Опрос отправлен ✅")

    elif text == "🕒 Автоматические опросы":
        await message.answer("Выберите тип автоматического опроса:", reply_markup=auto_poll_inline_keyboard())

    elif text == "⬅ Назад":
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard())

    else:
        await message.answer("Неизвестная команда. Используй меню ниже 👇", reply_markup=main_menu_keyboard())


@dp.callback_query(F.data == "daily_poll")
async def daily_poll_callback(callback: CallbackQuery):
    await callback.message.answer("Введите время ежедневного опроса в формате HH:MM (например 09:00):")
    config["awaiting_time_input"] = True


@dp.callback_query(F.data == "date_poll")
async def date_poll_callback(callback: CallbackQuery):
    await callback.message.answer("Введите дату и время опроса в формате DD.MM.YYYY HH:MM (например 31.03.2026 14:00):")
    config["awaiting_date_input"] = True


async def handle_time_input(message: Message):
    try:
        hour_str, minute_str = message.text.strip().split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        config["daily_poll_hour"] = hour
        config["daily_poll_minute"] = minute
        config["awaiting_time_input"] = False
        save_config()
        await message.answer(f"Ежедневный опрос будет отправляться в {hour:02d}:{minute:02d}", reply_markup=poll_menu_keyboard())
    except Exception:
        await message.answer("Неверный формат. Введи в формате HH:MM, например 14:00")
        config["awaiting_time_input"] = True


async def handle_date_input(message: Message):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        config["scheduled_poll_datetime"] = dt.isoformat()
        config["awaiting_date_input"] = False
        config["last_sent_scheduled"] = None
        save_config()
        await message.answer(f"Опрос будет отправлен один раз {message.text}", reply_markup=poll_menu_keyboard())
    except Exception:
        await message.answer("Неверный формат. Введи в формате DD.MM.YYYY HH:MM, например 31.03.2026 14:00")
        config["awaiting_date_input"] = True


@dp.callback_query(F.data == "send_poll_now")
async def send_poll_now(callback: CallbackQuery, bot: Bot):
    if not config["chat_id"]:
        await callback.message.answer("Сначала отправь /setchat в нужной группе или канале.")
        return
    await send_poll(bot, config["chat_id"])
    config["last_sent_date"] = datetime.now(TYUMEN_TZ).isoformat()
    save_config()
    await callback.message.answer("Опрос отправлен ✅")


async def scheduler(bot: Bot):
    while True:
        # Основное время локальное
        now = datetime.now(TYUMEN_TZ)
        # Попытка корректировки через интернет (вспомогательно)
        internet_time = await get_current_time_tumen()
        if internet_time:
            now = internet_time  # если получилось получить, корректируем

        if config["chat_id"]:
            # Ежедневный опрос
            if now.hour == config.get("daily_poll_hour", 0) and now.minute == config.get("daily_poll_minute", 0):
                last_sent_date = config.get("last_sent_date")
                today_str = now.date().isoformat()
                if last_sent_date != today_str:
                    try:
                        await send_poll(bot, config["chat_id"])
                        config["last_sent_date"] = today_str
                        save_config()
                        print(f"Ежедневный опрос отправлен {now}")
                    except Exception as e:
                        print(f"Ошибка при отправке опроса: {e}")

            # Опрос по конкретной дате
            if config.get("scheduled_poll_datetime"):
                dt = datetime.fromisoformat(config["scheduled_poll_datetime"]).replace(tzinfo=TYUMEN_TZ)
                if now >= dt and config.get("last_sent_scheduled") != config["scheduled_poll_datetime"]:
                    try:
                        await send_poll(bot, config["chat_id"])
                        config["last_sent_scheduled"] = config["scheduled_poll_datetime"]
                        config["scheduled_poll_datetime"] = None
                        save_config()
                        print(f"Опрос по дате отправлен {now}")
                    except Exception as e:
                        print(f"Ошибка при отправке опроса: {e}")

        await asyncio.sleep(20)


async def main():
    load_config()
    bot = Bot(token=TOKEN)
    asyncio.create_task(scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
