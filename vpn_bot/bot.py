import os
import json
import secrets
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor


# ===============================
# Конфиг через .env
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN обязателен в .env")

DEV_SKIP_PAYMENTS = os.getenv("DEV_SKIP_PAYMENTS", "1") == "1"

WG_SERVER_ENDPOINT = os.getenv("WG_SERVER_ENDPOINT", "127.0.0.1:51820")
WG_SERVER_PUBLIC_KEY = os.getenv("WG_SERVER_PUBLIC_KEY", "PUBLIC_KEY_PLACEHOLDER")
WG_CLIENT_DNS = os.getenv("WG_CLIENT_DNS", "1.1.1.1,8.8.8.8")
WG_ALLOWED_IPS = os.getenv("WG_ALLOWED_IPS", "0.0.0.0/0,::/0")
WG_SUBNET = os.getenv("WG_SUBNET", "10.66.66.0/24")

# ===============================
# Настройка бота
# ===============================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Простейший план
PLANS = {
    "basic": {"name": "Базовый", "price": 10},
    "pro": {"name": "Pro", "price": 20}
}

PLANS_MAP = {k: v for k, v in PLANS.items()}

# ===============================
# Функции
# ===============================
def generate_client_config(client_ip: str) -> str:
    """Генерируем тестовый конфиг WireGuard"""
    private_key = secrets.token_hex(16)
    config = f"""
[Interface]
PrivateKey = {private_key}
Address = {client_ip}/32
DNS = {WG_CLIENT_DNS}

[Peer]
PublicKey = {WG_SERVER_PUBLIC_KEY}
Endpoint = {WG_SERVER_ENDPOINT}
AllowedIPs = {WG_ALLOWED_IPS}
"""
    return config.strip()


async def provision_and_send(chat_id: int, user, plan):
    # Для теста генерируем IP на основе случайного числа
    last_octet = secrets.randbelow(200) + 10
    client_ip = f"10.66.66.{last_octet}"
    config = generate_client_config(client_ip)
    await bot.send_message(chat_id, f"Ваш конфиг для {plan['name']} готов:\n\n<pre>{config}</pre>", parse_mode="HTML")


# ===============================
# Хендлеры
# ===============================

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name or "друг"

    # Текст приветствия
    welcome_text = (
        f"Привет, {user_name} 👋\n\n"
        "Наша команда готова избавить Вас от:\n\n"
        "➩ Зависающих видео в запрещённой сети\n"
        "➩ Бесконечного просмотра рекламы\n"
        "➩ Блокировки из-за частой смены IP-адреса\n"
        "➩ Утечки заряда батареи и ваших данных (как у бесплатных VPN)\n\n"
        "⇩ Главное меню ⇩"
    )

    # Inline-кнопки под сообщением
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Выбрать план VPN", callback_data="menu_buy"),
        InlineKeyboardButton("Статус подписки", callback_data="menu_status"),
        InlineKeyboardButton("Помощь", callback_data="menu_help")
    )

    # Отправляем сообщение с кнопками
    await message.answer(welcome_text, reply_markup=keyboard)

# Хендлеры для нажатий на кнопки
@dp.callback_query_handler(lambda c: c.data == "menu_buy")
async def callback_buy(call: types.CallbackQuery):
    await call.answer()

    # Получаем имя пользователя
    user_name = call.from_user.first_name or "друг"

    # Inline-кнопки под сообщением
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("1 мес - 249", callback_data="buy_basic"),
        InlineKeyboardButton("3 мес - 749", callback_data="buy_pro"),
        InlineKeyboardButton("6 мес - 1499", callback_data="buy_premium"),
    )

    await call.message.answer(f"{user_name}, выберете план:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "menu_status")
async def callback_status(call: types.CallbackQuery):
    await call.answer()
    await call.message.answer("Ваш статус подписки пока пустой")

@dp.callback_query_handler(lambda c: c.data == "menu_help")
async def callback_help(call: types.CallbackQuery):
    await call.answer()

    # Получаем имя пользователя
    user_name = call.from_user.first_name or "друг"

    # Inline-кнопки под сообщением
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Как подключиться?", callback_data="help_connect"),
        InlineKeyboardButton("Не работает VPN", callback_data="help_issue"),
        InlineKeyboardButton("Связаться со мной", callback_data="help_contact"),
        InlineKeyboardButton("Главное меню", callback_data="menu_main")
    )

    # Редактируем старое сообщение вместо создания нового
    await call.message.edit_text(
        f"{user_name}, выберите необходимый пункт меню:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "help_connect")
async def help_connect(call: types.CallbackQuery):
    await call.answer()

    # создаём клавиатуру
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="🤖 Android", callback_data="connect_android"),
        InlineKeyboardButton(text="🍏 iOS", callback_data="connect_ios"),
        InlineKeyboardButton(text="💻 macOS", callback_data="connect_macos"),
        InlineKeyboardButton(text="🖥 Windows", callback_data="connect_windows"),
    )
    keyboard.add(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_help")
    )

    text = (
        "Спасибо, что выбрали нас ♥️ \n\n"
        "➩ Попробовав раз — Вы поймёте, почему люди остаются с нами. \n"
        "➩ Вы забудете, что такое загрузка на сайтах. \n\n"
        "📺 Инструкция для Роутеров\\Телевизоров: "
        "[Читать инструкцию](https://telegra.ph/Instrukciya-dlya-RouterovTelevizorov-08-23) \n\n"
        "⇩ Куда будем подключать VPN? ⇩"
    )

    # заменяем старое сообщение новым
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True, parse_mode="Markdown")


# --- Android ---
@dp.callback_query_handler(lambda c: c.data == "connect_android")
async def connect_android(call: types.CallbackQuery):
    await call.answer()


    await call.message.answer(
        "📱 Инструкция по подключению VPN на Android:\n\n"
        "1️⃣ Установи приложение 🌐WireGuard (https://play.google.com/store/apps/details?id=com.wireguard.android)\n"
        "2️⃣ Нажми на ключ и скачай его (выше в чате *.conf)\n"
        "3️⃣ Запусти программу Wireguard и нажми ➕ в правом нижнем углу экрана\n"
        "4️⃣ Нажми кнопку Импорт из файла или архива, выбери скачанный ключ из папки загрузок\n"
        "5️⃣ Остается нажать на тумблер. Если ползунок стал зелёным, у тебя всё получилось 👏\n",
    )


# --- iOS ---
@dp.callback_query_handler(lambda c: c.data == "connect_ios")
async def connect_ios(call: types.CallbackQuery):
    await call.answer()


    await call.message.answer(
        "🍏 Инструкция по подключению VPN на iOS:\n\n"
        "1️⃣ Установи приложение 🌐WireGuard (https://apps.apple.com/ru/app/wireguard/id1441195209)\n"
        "2️⃣ Нажми на ключ (выше в чате *.conf)\n"
        "3️⃣ В левом нижнем углу коснись стрелки Поделиться\n"
        "4️⃣ В списке программ выбери Wireguard)\n"
        "5️⃣ Остается нажать на тумблер. Если ползунок стал зелёным, у тебя всё получилось 👏",

    )


# --- macOS ---
@dp.callback_query_handler(lambda c: c.data == "connect_macos")
async def connect_macos(call: types.CallbackQuery):
    await call.answer()


    await call.message.answer(
        "💻 Инструкция по подключению VPN на macOS:\n\n"
        "1️⃣ Скачай и установи приложение 🌐WireGuard (https://apps.apple.com/ru/app/wireguard/id1451685025?mt=12)\n"
        "2️⃣ Нажми на ключ и скачай его (выше в чате *.conf)\n"
        "3️⃣ Укажи приложению Wireguard на скачанный ключ\n"
        "4️⃣ Включи тумблер и наслаждайся высокой скоростью и стабильностью 😉",

    )


# --- Windows ---
@dp.callback_query_handler(lambda c: c.data == "connect_windows")
async def connect_windows(call: types.CallbackQuery):
    await call.answer()


    await call.message.answer(
        "🖥 Инструкция по подключению VPN на Windows:\n\n"
        "1️⃣ Скачай и установи приложение 🌐WireGuard (https://download.wireguard.com/windows-client/wireguard-installer.exe)\n"
        "2️⃣ Нажми на ключ и скачай его (выше в чате *.conf)\n"
        "3️⃣ Укажи приложению Wireguard на скачанный ключ\n"
        "4️⃣ Включи тумблер и наслаждайся высокой скоростью и стабильностью 😉",
    )


@dp.callback_query_handler(lambda c: c.data == "help_issue")
async def help_issue(call: types.CallbackQuery):
    await call.answer()
    user_name = call.from_user.first_name or "друг"

    text = (
        f"{user_name}, я всегда рад помочь вам, но для начала 👇\n\n"
        "‼️ ЧИТАТЬ ВСЕМ ‼️\n\n"
        "1. На данный момент сотовые операторы и провайдеры блокируют все VPN в России, "
        "но у нас есть обход всех блокировок. Откройте меню бота > Сменить протокол > "
        "Меняем на Outline и следуем инструкции.\n\n"
        "2. Если у вас не прошла оплата, напишите в бота «проблемы с оплатой» и последние 4 цифры карты. "
        "Скрины бот не понимает! Возможно, оплата прошла: проверьте «мои активные ключи».\n\n"
        "3. Сервера работают без перебоев, но ваш телефон может менять сеть (Wi-Fi ↔️ LTE). "
        "Включите/выключите авиарежим, перезапустите VPN — это помогает.\n\n"
        "4. Instagram: если сайты открываются, а Instagram нет — удалите приложение и установите заново.\n\n"
        "5. Старые роутеры или публичные сети могут не поддерживать VPN. Это не наша проблема.\n\n"
        "6. Если VPN не работает только через мобильную сеть — это блокировки операторов. "
        "Мы ищем обходы.\n\n"
        "Если VPN не работает и ваш случай совпадает с пунктами выше, напишите: @Jotaro1707"
    )

    # Кнопка "Меню"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
    InlineKeyboardButton("Как подключиться?", callback_data="help_connect"),
    InlineKeyboardButton("Связаться со мной", callback_data="help_contact"),
    InlineKeyboardButton("Главное меню", callback_data="menu_main")
    )
    await call.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "help_contact")
async def help_contact(call: types.CallbackQuery):
    await call.answer()

    text = (
        "С предложениями о сотрудничестве, улучшении функционала и по другим вопросам, "
        "пишите мне 👉 @Jotaro1707"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Как подключиться?", callback_data="help_connect"),
        InlineKeyboardButton("Не работает VPN", callback_data="help_issue"),
        InlineKeyboardButton("Главное меню", callback_data="menu_main"),
    )

    # заменяем старое сообщение новым текстом + кнопки
    await call.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "menu_main")
async def back_to_main(call: types.CallbackQuery):
    await call.answer()
    await cmd_start(call.message)  # вернёт в главное меню



@dp.callback_query_handler(lambda call: call.data.startswith("buy_"))
async def process_buy(call: types.CallbackQuery):
    plan_key = call.data.split("_")[1]
    plan = PLANS_MAP.get(plan_key)
    print(f"Callback получен: {call.data}, план: {plan_key}")
    await call.answer("Генерируем конфиг…")
    await provision_and_send(call.from_user.id, call.from_user, plan)


@dp.message_handler(commands=["status"])
async def cmd_status(message: types.Message):
    await message.answer("Тестовая база подписок пока пустая.")


# ===============================
# Запуск
# ===============================
if __name__ == "__main__":
    print("Запускаю бота…")
    executor.start_polling(dp, skip_updates=True)
