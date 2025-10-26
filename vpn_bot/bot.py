import os
import secrets
import requests
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
import psycopg2
from dotenv import load_dotenv
from nacl.public import PrivateKey
import base64
from io import BytesIO

# ===============================
# Вспомогательная функция для генерации ключей WireGuard
# ===============================
def generate_keys():
    private_key_obj = PrivateKey.generate()
    private_key = base64.b64encode(private_key_obj.encode()).decode()
    public_key = base64.b64encode(private_key_obj.public_key.encode()).decode()
    return private_key, public_key

# ===============================
# Загружаем переменные окружения
# ===============================
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "vpn_bot_db")
DB_USER = os.getenv("DB_USER", "vpn_bot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN обязателен в .env")

DEV_SKIP_PAYMENTS = os.getenv("DEV_SKIP_PAYMENTS", "1") == "1"
WGREST_URL = os.getenv("WGREST_URL", "http://host.docker.internal:8080")
WGREST_DEVICE = os.getenv("WGREST_DEVICE", "wg0")
WGREST_AUTH_TOKEN = os.getenv("WGREST_AUTH_TOKEN", "")
SERVER_ENDPOINT = os.getenv('SERVER_ENDPOINT', 'your-server-ip:51831')
SERVER_PUBLIC_KEY = os.getenv('SERVER_PUBLIC_KEY', 'MzUciL6+pfBWjte7YVAPlxBuIvCTCvk9kJGA2kjZMTA=')

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

# Создаем таблицы
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
# Конфиг бота
# ===============================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

PLANS = {
    "basic": {"name": "1 мес (Базовый)", "price": 249},
    "pro": {"name": "3 мес (Pro)", "price": 749},
    "premium": {"name": "6 мес (Premium)", "price": 1499}
}

# ===============================
# Вспомогательные функции
# ===============================
def check_wg_device():
    headers = {}
    if WGREST_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
    try:
        response = requests.get(f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/", headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"✅ Устройство {WGREST_DEVICE} доступно")
            return True
        else:
            print(f"❌ Устройство {WGREST_DEVICE} недоступно (статус: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Ошибка проверки устройства: {e}")
        return False

def save_user_to_db(user: types.User):
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

# ===============================
# Создание 7 пиров и генерация конфигов
# ===============================
def create_peer_via_wgrest(user_id: int, client_ip: str):
    """Создаем пира через wgREST API и получаем quick.conf"""
    try:
        headers = {}
        if WGREST_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
        headers["Content-Type"] = "application/json"

        peer_name = f"user_{user_id}_{secrets.token_hex(4)}"
        payload = {"name": peer_name, "allowed_ips": [client_ip + "/32"]}
        print("POST /peers payload:", payload)

        response = requests.post(
            f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/",
            headers=headers,
            json=payload,
            timeout=10
        )
        print("POST /peers response:", response.status_code, response.text)
        response.raise_for_status()
        peer_data = response.json()

        peer_key = None
        if isinstance(peer_data, list) and len(peer_data) > 0:
            peer_key = peer_data[0].get("publicKey") or peer_data[0].get("key") or peer_data[0].get("public_key")
        elif isinstance(peer_data, dict):
            peer_key = peer_data.get("publicKey") or peer_data.get("key") or peer_data.get("public_key")

        if not peer_key:
            raise Exception("Не удалось получить публичный ключ пира из ответа wgREST")

        # URL-safe base64
        peer_id = base64.urlsafe_b64encode(base64.b64decode(peer_key)).decode()

        config_response = requests.get(
            f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/{peer_id}/quick.conf",
            headers=headers,
            timeout=10
        )
        print("GET quick.conf response:", config_response.status_code)
        if config_response.status_code == 200:
            return config_response.text
        else:
            raise Exception(f"Не удалось получить конфиг пира (status {config_response.status_code})")
    except Exception as e:
        print(f"⚠️ wgREST недоступен или ошибка: {e}")
        return generate_fallback_config(user_id, client_ip)

def generate_fallback_config(user_id: int, client_ip: str):
    print("🔄 Генерируем fallback конфигурацию...")
    private_key, public_key = generate_keys()
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/24
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {SERVER_PUBLIC_KEY}
Endpoint = {SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25"""
    print(f"✅ Fallback конфигурация создана для IP {client_ip}")
    return config

async def provision_and_send_all(chat_id: int, user: types.User, plan_key: str):
    plan = PLANS.get(plan_key)
    if not plan:
        await bot.send_message(chat_id, "❌ Ошибка: выбран неверный план.")
        return

    configs = []
    used_ips = set()
    for i in range(7):
        while True:
            last_octet = secrets.randbelow(200) + 10
            client_ip = f"10.66.66.{last_octet}"
            if client_ip not in used_ips:
                used_ips.add(client_ip)
                break
        config = create_peer_via_wgrest(user.id * 10 + i, client_ip)
        save_subscription_to_db(user, plan_key, client_ip, config)
        configs.append((client_ip, config))

    for client_ip, config in configs:
        try:
            await bot.send_message(
                chat_id,
                f"✅ Конфиг для IP `{client_ip}`:\n\n<pre>{config}</pre>",
                parse_mode="HTML"
            )
        except Exception:
            await bot.send_message(chat_id, f"Конфиг для {client_ip} готов (plain text)")

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
    user_name = message.from_user.first_name or "друг"
    save_user_to_db(message.from_user)
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

# --- Buy menu ---
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
    await call.answer("Генерируем 7 конфигов…")
    await provision_and_send_all(call.from_user.id, call.from_user, plan_key)

# --- Status ---
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
            await call.message.answer(f"🔔 Текущая подписка: *{plan_name}*\nIP: `{client_ip}`\nДата: {created_str}",
                                      parse_mode="Markdown", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")))
        else:
            await call.message.answer("У вас пока нет активной подписки.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")))
    except Exception as e:
        print("status error:", e)
        await call.message.answer("Ошибка при получении статуса подписки. Попробуйте позже.")

# --- Help меню ---
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

# ===============================
# Запуск бота
# ===============================
if __name__ == "__main__":
    print("Запускаю бота…")
    executor.start_polling(dp, skip_updates=True)
