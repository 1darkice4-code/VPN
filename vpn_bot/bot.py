import os
import secrets
import requests
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
import psycopg2
from dotenv import load_dotenv
from io import BytesIO

# ===============================
# Загружаем переменные окружения
# ===============================
load_dotenv()

# ===============================
# Настройки базы данных
# ===============================
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "vpn_bot_db")
DB_USER = os.getenv("DB_USER", "vpn_bot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "post123")

# ===============================
# Подключение к БД
# ===============================
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    print("✅ Подключение к БД успешно")
except Exception as e:
    print("❌ Ошибка подключения к БД:", e)
    raise SystemExit(1)

# Создание таблиц
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    username TEXT,
    first_name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    plan TEXT,
    client_ip TEXT,
    config TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
""")
conn.commit()

# ===============================
# Настройки Telegram бота
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN обязателен в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===============================
# Настройки wgREST и WireGuard
# ===============================
WGREST_URL = os.getenv("WGREST_URL", "http://host.docker.internal:8080")
WGREST_DEVICE = os.getenv("WGREST_DEVICE", "wg0")
WGREST_AUTH_TOKEN = os.getenv("WGREST_AUTH_TOKEN")
USE_WGREST = os.getenv("USE_WGREST", "true") == "true"

WG_SERVER_PUBLIC_KEY = os.getenv("WG_SERVER_PUBLIC_KEY")
WG_SERVER_ENDPOINT = os.getenv("WG_SERVER_ENDPOINT")
WG_CLIENT_DNS = os.getenv("WG_CLIENT_DNS", "1.1.1.1,8.8.8.8")
WG_ALLOWED_IPS = os.getenv("WG_ALLOWED_IPS", "0.0.0.0/0,::/0")
WG_SUBNET = os.getenv("WG_SUBNET", "10.66.66.0/24")

# ===============================
# Настройка платежей (тест)
# ===============================
DEV_SKIP_PAYMENTS = os.getenv("DEV_SKIP_PAYMENTS", "1") == "1"

# ===============================
# Планы подписки
# ===============================
PLANS = {
    "basic": {"name": "1 мес (Базовый)", "price": 249},
    "pro": {"name": "3 мес (Pro)", "price": 749},
    "premium": {"name": "6 мес (Premium)", "price": 1499}
}


# ===============================
# Вспомогательные функции
# ===============================

def save_user_to_db(user: types.User):
    """Сохраняем пользователя в БД"""
    try:
        cursor.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT (telegram_id) DO NOTHING",
            (user.id, getattr(user, "username", None), getattr(user, "first_name", None))
        )
        conn.commit()
    except Exception as e:
        print("DB save_user error:", e)
        conn.rollback()


def save_subscription_to_db(user: types.User, plan_key: str, client_ip: str, config: str):
    """Сохраняем подписку"""
    try:
        save_user_to_db(user)
        cursor.execute(
            "INSERT INTO subscriptions (user_id, plan, client_ip, config) VALUES (%s, %s, %s, %s)",
            (user.id, PLANS.get(plan_key, {}).get("name", plan_key), client_ip, config)
        )
        conn.commit()
    except Exception as e:
        print("DB save_subscription error:", e)
        conn.rollback()


def generate_demo_config(client_ip: str) -> str:
    """Генерация демо-конфига WireGuard"""
    private_key = secrets.token_urlsafe(32)
    return f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/24
DNS = {WG_CLIENT_DNS}

[Peer]
PublicKey = {WG_SERVER_PUBLIC_KEY}
Endpoint = {WG_SERVER_ENDPOINT}
AllowedIPs = {WG_ALLOWED_IPS}
PersistentKeepalive = 25
""".strip()


def create_wg_device():
    """Проверяем наличие устройства в wgREST и создаем при необходимости"""
    headers = {"Authorization": f"Bearer {WGREST_AUTH_TOKEN}", "Content-Type": "application/json"}

    # Проверка устройства
    resp = requests.get(f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/", headers=headers, timeout=5)
    if resp.status_code == 404:
        # создаем устройство
        resp_create = requests.post(f"{WGREST_URL}/v1/devices/", json={"name": WGREST_DEVICE}, headers=headers,
                                    timeout=5)
        if resp_create.status_code not in [200, 201]:
            raise Exception(f"Не удалось создать устройство {WGREST_DEVICE}: {resp_create.text}")
        print(f"✅ Устройство {WGREST_DEVICE} создано")
    elif resp.status_code != 200:
        raise Exception(f"Ошибка проверки устройства {WGREST_DEVICE}: {resp.status_code} {resp.text}")
    else:
        print(f"✅ Устройство {WGREST_DEVICE} существует")


def create_peer_via_wgrest(user_id: int, plan_name: str):
    """Создаем пира через wgREST и возвращаем конфиг"""
    if not WGREST_AUTH_TOKEN:
        raise SystemExit("WGREST_AUTH_TOKEN не задан в .env")

    headers = {"Authorization": f"Bearer {WGREST_AUTH_TOKEN}", "Content-Type": "application/json"}

    # Проверка доступности wgREST
    try:
        resp_ver = requests.get(f"{WGREST_URL}/version", headers=headers, timeout=5)
        print(f"wgREST доступен, версия: {resp_ver.text}")
    except Exception as e:
        raise Exception(f"wgREST недоступен: {e}")

    # Проверка/создание устройства
    create_wg_device()

    # Создаем пира
    peer_name = f"user_{user_id}_{secrets.token_hex(4)}"
    resp_peer = requests.post(
        f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/",
        json={"name": peer_name},
        headers=headers,
        timeout=10
    )
    if resp_peer.status_code not in [200, 201]:
        raise Exception(f"Не удалось создать пира: {resp_peer.status_code} {resp_peer.text}")

    peer = resp_peer.json()
    peer_key = peer.get("urlSafePubKey")
    if not peer_key:
        raise Exception("wgREST вернул пира без urlSafePubKey")

    # Получаем конфиг .conf
    resp_conf = requests.get(f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/{peer_key}/quick.conf", headers=headers,
                             timeout=10)
    if resp_conf.status_code != 200:
        raise Exception(f"Не удалось получить конфиг: {resp_conf.status_code} {resp_conf.text}")

    config = resp_conf.text
    print(f"✅ Конфиг для {peer_name} получен через wgREST")
    return config, peer.get("publicKey", "")


def generate_client_config(user_id: int, client_ip: str) -> str:
    """Генерация конфига — через wgREST или fallback демо"""
    if USE_WGREST:
        try:
            return create_peer_via_wgrest(user_id, "VIP")[0]
        except Exception as e:
            print(f"⚠️ wgREST недоступен, используем демо-конфиг: {e}")
            return generate_demo_config(client_ip)
    else:
        return generate_demo_config(client_ip)


async def provision_and_send(chat_id: int, user: types.User, plan_key: str):
    """Генерация конфигурации и отправка пользователю"""
    plan = PLANS.get(plan_key)
    if not plan:
        await bot.send_message(chat_id, "❌ Ошибка: выбран неверный план.")
        return

    # Генерация IP в подсети
    last_octet = secrets.randbelow(200) + 10
    client_ip = f"10.66.66.{last_octet}"

    # Генерация конфига
    config = generate_client_config(user.id, client_ip)

    # Сохраняем в БД
    save_subscription_to_db(user, plan_key, client_ip, config)

    # Отправка в чате
    try:
        await bot.send_message(
            chat_id,
            f"✅ Ваш конфиг для *{plan['name']}* готов:\n\n<pre>{config}</pre>",
            parse_mode="HTML"
        )
    except:
        await bot.send_message(chat_id, f"Ваш конфиг для {plan['name']} готов. (Не удалось отформатировать пред.)")

    # Отправка файла
    try:
        bio = BytesIO()
        bio.write(config.encode())
        bio.seek(0)
        bio.name = f"wg_{client_ip}.conf"
        await bot.send_document(chat_id, bio)
    except Exception as e:
        print("send_document error:", e)


# ===============================
# Хендлеры меню
# ===============================
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    save_user_to_db(message.from_user)
    user_name = message.from_user.first_name or "друг"
    welcome_text = (
        f"Привет, {user_name} 👋\n\n"
        "Наш VPN поможет вам:\n\n"
        "➩ Избавиться от рекламы и блокировок\n"
        "➩ Поддерживать стабильное соединение\n"
        "➩ Работать безопасно и анонимно\n\n"
        "⇩ Главное меню ⇩"
    )
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Выбрать план VPN", callback_data="menu_buy"),
        InlineKeyboardButton("Статус подписки", callback_data="menu_status"),
        InlineKeyboardButton("Помощь", callback_data="menu_help")
    )
    await message.answer(welcome_text, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "menu_buy")
async def callback_buy(call: types.CallbackQuery):
    await call.answer()
    keyboard = InlineKeyboardMarkup(row_width=1)
    for key, plan in PLANS.items():
        keyboard.add(InlineKeyboardButton(f"{plan['name']} — {plan['price']}₽", callback_data=f"buy_{key}"))
    await call.message.answer("Выберите план:", reply_markup=keyboard)


@dp.callback_query_handler(lambda call: call.data.startswith("buy_"))
async def process_buy(call: types.CallbackQuery):
    plan_key = call.data.split("_", 1)[1]
    await call.answer("Генерируем конфиг…")
    await provision_and_send(call.from_user.id, call.from_user, plan_key)


@dp.callback_query_handler(lambda c: c.data == "menu_status")
async def callback_status(call: types.CallbackQuery):
    await call.answer()
    try:
        cursor.execute(
            "SELECT plan, client_ip, created_at FROM subscriptions WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
            (call.from_user.id,)
        )
        sub = cursor.fetchone()
        if sub:
            plan_name, client_ip, created_at = sub
            created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            await call.message.answer(
                f"🔔 Текущая подписка: *{plan_name}*\nIP: `{client_ip}`\nДата: {created_str}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
            )
        else:
            await call.message.answer(
                "У вас пока нет активной подписки.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
            )
    except Exception as e:
        print("status error:", e)
        await call.message.answer("Ошибка при получении статуса подписки. Попробуйте позже.")


@dp.callback_query_handler(lambda c: c.data == "menu_help")
async def callback_help(call: types.CallbackQuery):
    await call.answer()
    user_name = call.from_user.first_name or "друг"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Как подключиться?", callback_data="help_connect"),
        InlineKeyboardButton("Не работает VPN", callback_data="help_issue"),
        InlineKeyboardButton("Связаться со мной", callback_data="help_contact"),
        InlineKeyboardButton("Главное меню", callback_data="menu_main")
    )
    await call.message.edit_text(f"{user_name}, выберите необходимый пункт меню:", reply_markup=keyboard)


# --- Submenus: help_connect, help_issue, help_contact
@dp.callback_query_handler(lambda c: c.data == "help_connect")
async def help_connect(call: types.CallbackQuery):
    await call.answer()
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🤖 Android", callback_data="connect_android"),
        InlineKeyboardButton("🍏 iOS", callback_data="connect_ios"),
        InlineKeyboardButton("💻 macOS", callback_data="connect_macos"),
        InlineKeyboardButton("🖥 Windows", callback_data="connect_windows"),
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_help"))
    text = "Спасибо, что выбрали нас ♥️\n\n⇩ Куда будем подключать VPN? ⇩"
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)


@dp.callback_query_handler(lambda c: c.data == "help_issue")
async def help_issue(call: types.CallbackQuery):
    await call.answer()
    user_name = call.from_user.first_name or "друг"
    text = (
        f"{user_name}, я всегда рад помочь вам, но для начала 👇\n\n"
        "‼️ ЧИТАТЬ ВСЕМ ‼️\n\n"
        "1. Попробуйте выключить/включить VPN и сеть.\n"
        "2. Перезагрузите устройство.\n"
        "3. Если была оплата — проверьте статус в разделе \"Статус подписки\".\n\n"
        "Если проблема сохраняется — напишите в поддержку: @Jotaro1707"
    )
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("Главное меню", callback_data="menu_main"))
    await call.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "help_contact")
async def help_contact(call: types.CallbackQuery):
    await call.answer()
    text = "С предложениями и вопросами — пишите @Jotaro1707"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Как подключиться?", callback_data="help_connect"),
        InlineKeyboardButton("Не работает VPN", callback_data="help_issue"),
        InlineKeyboardButton("Главное меню", callback_data="menu_main"),
    )
    await call.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "menu_main")
async def back_to_main(call: types.CallbackQuery):
    await call.answer()
    user_name = call.from_user.first_name or "друг"
    welcome_text = (
        f"Привет, {user_name} 👋\n\n"
        "Наш VPN поможет вам:\n\n"
        "➩ Избавиться от рекламы и блокировок\n"
        "➩ Поддерживать стабильное соединение\n"
        "➩ Работать безопасно и анонимно\n\n"
        "⇩ Главное меню ⇩"
    )
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Выбрать план VPN", callback_data="menu_buy"),
        InlineKeyboardButton("Статус подписки", callback_data="menu_status"),
        InlineKeyboardButton("Помощь", callback_data="menu_help")
    )
    await call.message.edit_text(welcome_text, reply_markup=keyboard)


# --- OS-specific instructions
@dp.callback_query_handler(lambda c: c.data == "connect_android")
async def connect_android(call: types.CallbackQuery):
    await call.answer()
    text = (
        "📱 Инструкция по подключению VPN на Android:\n\n"
        "1️⃣ Установите приложение WireGuard: https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        "2️⃣ Скачайте конфиг (он придет в чате после покупки)\n"
        "3️⃣ В приложении нажмите ➕ → Импорт из файла и выберите скачанный .conf\n"
        "4️⃣ Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Главное меню", callback_data="menu_main")))


@dp.callback_query_handler(lambda c: c.data == "connect_ios")
async def connect_ios(call: types.CallbackQuery):
    await call.answer()
    text = (
        "🍏 Инструкция по подключению VPN на iOS:\n\n"
        "1️⃣ Установите WireGuard: https://apps.apple.com/ru/app/wireguard/id1441195209\n"
        "2️⃣ Откройте файл .conf из чата и поделитесь им в WireGuard\n"
        "3️⃣ Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Главное меню", callback_data="menu_main")))


@dp.callback_query_handler(lambda c: c.data == "connect_macos")
async def connect_macos(call: types.CallbackQuery):
    await call.answer()
    text = (
        "💻 Инструкция для macOS:\n\n"
        "1️⃣ Установите WireGuard: https://apps.apple.com/ru/app/wireguard/id1451685025?mt=12\n"
        "2️⃣ Импортируйте .conf в приложение\n"
        "3️⃣ Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Главное меню", callback_data="menu_main")))


@dp.callback_query_handler(lambda c: c.data == "connect_windows")
async def connect_windows(call: types.CallbackQuery):
    await call.answer()
    text = (
        "🖥 Инструкция для Windows:\n\n"
        "1️⃣ Скачайте WireGuard: https://download.wireguard.com/windows-client/wireguard-installer.exe\n"
        "2️⃣ Откройте .conf файл и импортируйте его в приложение\n"
        "3️⃣ Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Главное меню", callback_data="menu_main")))


# ===============================
# Запуск бота
# ===============================
if __name__ == "__main__":
    print("Запускаю бота…")
    executor.start_polling(dp, skip_updates=True)
