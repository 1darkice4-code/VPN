import os
import secrets
import requests
import base64
import urllib.parse
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
import psycopg2
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# ===============================
# Подключение к БД (sync psycopg2)
# ===============================
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "vpn_bot_db")
DB_USER = os.getenv("DB_USER", "vpn_bot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")

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

# Создаём таблицы, если их ещё нет
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
    config_key INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
""")
conn.commit()

# ===============================
# Конфиг через .env
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN обязателен в .env")

DEV_SKIP_PAYMENTS = os.getenv("DEV_SKIP_PAYMENTS", "1") == "1"

# wgREST API endpoint
WGREST_URL = os.getenv("WGREST_URL", "http://host.docker.internal:8080")
WGREST_DEVICE = os.getenv("WGREST_DEVICE", "wg0")
WGREST_AUTH_TOKEN = os.getenv("WGREST_AUTH_TOKEN", "")

# ===============================
# Настройка бота
# ===============================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Планы (включая premium)
PLANS = {
    "basic": {"name": "1 мес (Базовый)", "price": 249},
    "pro": {"name": "3 мес (Pro)", "price": 749},
    "premium": {"name": "6 мес (Premium)", "price": 1499}
}

# ===============================
# Вспомогательные функции
# ===============================

def check_wg_device():
    """Проверяем существование WireGuard устройства"""
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

def create_peer_via_wgrest(user_id: int, plan_name: str):
    """Создаем пира через wgREST API и получаем конфиг"""
    try:
        # Пробуем использовать wgREST API
        # Но если он не работает, генерируем конфиг вручную
        
        # 1. Проверяем доступность wgREST
        try:
            headers = {}
            if WGREST_AUTH_TOKEN:
                headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
            response = requests.get(f"{WGREST_URL}/version", headers=headers, timeout=3)
            print(f"wgREST доступен, версия: {response.text}")
        except:
            raise Exception("wgREST недоступен, используем fallback")
        
        # 2. Проверяем доступность устройства
        if not check_wg_device():
            raise Exception("WireGuard устройство недоступно. Проверьте, что WireGuard сервис запущен.")
        
        # 3. Создаем пира через API
        peer_name = f"user_{user_id}_{secrets.token_hex(4)}"
        
        # Генерируем IP для клиента (10.250.250.10-250) в подсети сервера
        client_ip = f"10.250.250.{10 + (user_id % 240)}/32"
        
        headers = {"Content-Type": "application/json"}
        if WGREST_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
        
        # Создаем пира с указанием allowed_ips
        response = requests.post(
            f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/",
            json={
                "name": peer_name,
                "allowed_ips": [client_ip]
            },
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            peer = response.json()
            print(f"DEBUG: Peer response: {peer}")
            # Используем url_safe_public_key для URL (API требует именно этот формат)
            peer_key = peer.get('url_safe_public_key', '')
            
            if not peer_key:
                raise Exception("Не удалось получить публичный ключ пира")
            
            print(f"DEBUG: Requesting config for key: {peer_key}")
            
            # Получаем конфиг
            config_headers = {}
            if WGREST_AUTH_TOKEN:
                config_headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
            
            config_response = requests.get(
                f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/{peer_key}/quick.conf",
                headers=config_headers,
                timeout=10
            )
            
            if config_response.status_code == 200:
                config = config_response.text
                print(f"✅ Конфиг получен через wgREST")
                return config, peer_key
            else:
                print(f"❌ Ошибка получения конфига: {config_response.status_code}")
                raise Exception(f"Не удалось получить конфигурацию пира")
        
        print(f"❌ Ошибка создания пира: {response.status_code} - {response.text}")
        raise Exception("wgREST API не смог создать пир")
        
    except Exception as e:
        print(f"⚠️ wgREST недоступен: {e}")
        # Fallback - генерируем конфиг вручную
        return generate_fallback_config(user_id)

def generate_fallback_config(user_id: int):
    """Генерируем fallback конфигурацию когда wgREST недоступен"""
    print("🔄 Генерируем fallback конфигурацию...")
    
    # Генерируем ключи клиента
    private_key = secrets.token_hex(32)
    public_key = secrets.token_hex(32)
    
    # Получаем IP сервера (из переменных окружения или используем дефолтный)
    server_endpoint = os.getenv('SERVER_ENDPOINT', 'your-server-ip:51831')
    server_public_key = os.getenv('SERVER_PUBLIC_KEY', 'MzUciL6+pfBWjte7YVAPlxBuIvCTCvk9kJGA2kjZMTA=')
    
    # Генерируем IP клиента в подсети сервера
    client_ip = f"10.250.250.{10 + (user_id % 240)}"
    
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/24
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25"""
    
    print(f"✅ Fallback конфигурация создана для IP {client_ip}")
    return config, public_key

def generate_client_config(user_id: int, client_ip: str) -> str:
    """Генерируем конфиг WireGuard через wgREST API"""
    try:
        # Используем wgREST для создания реального пира
        config, public_key = create_peer_via_wgrest(user_id, "VIP")
        return config
    except Exception as e:
        print(f"❌ Ошибка создания конфига через wgREST: {e}")
        # Fallback уже обработан в create_peer_via_wgrest
        raise Exception(f"Не удалось создать VPN конфигурацию: {e}")

def save_user_to_db(user: types.User):
    """Сохраняем пользователя в таблицу users, если его нет"""
    try:
        cursor.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT (telegram_id) DO NOTHING",
            (user.id, getattr(user, "username", None), getattr(user, "first_name", None))
        )
        conn.commit()
    except Exception as e:
        print("DB save_user error:", e)
        conn.rollback()

def save_subscription_to_db(user: types.User, plan_key: str, client_ip: str, config: str, config_key: int = 0):
    """Сохраняем подписку"""
    try:
        # Убедимся, что пользователь есть
        save_user_to_db(user)
        cursor.execute(
            "INSERT INTO subscriptions (user_id, plan, client_ip, config, config_key) VALUES (%s, %s, %s, %s, %s)",
            (user.id, PLANS.get(plan_key, {}).get("name", plan_key), client_ip, config, config_key)
        )
        conn.commit()
    except Exception as e:
        print("DB save_subscription error:", e)
        conn.rollback()

# ===============================
# Генерация WireGuard deep links
# ===============================
def generate_wireguard_link(name: str, conf_text: str) -> str:
    """Генерирует deep link для автоматического импорта конфигурации в WireGuard"""
    # Кодируем конфигурацию в base64
    encoded_conf = base64.b64encode(conf_text.encode('utf-8')).decode('utf-8')
    
    # Экранируем спецсимволы, чтобы ссылка не "сломалась"
    encoded_conf = urllib.parse.quote(encoded_conf)
    
    # Формируем deep link
    link = f"wireguard://import?name={urllib.parse.quote(name)}&config={encoded_conf}"
    return link

# ===============================
# Отправка конфига (основная логика)
# ===============================
async def provision_and_send(chat_id: int, user: types.User, plan_key: str):
    """Генерируем 7 конфигов и отправляем пользователю; сохраняем в БД"""
    plan = PLANS.get(plan_key)
    if not plan:
        await bot.send_message(chat_id, "❌ Ошибка: выбран неверный план.")
        return

    try:
        # Генерируем 7 конфигураций
        configs_dict = {}
        for key_num in range(1, 8):
            # Генерируем уникальный IP для каждой конфигурации
            last_octet = secrets.randbelow(240) + 10
            client_ip = f"10.250.250.{last_octet}_{key_num}"
            
            # Генерируем конфиг через wgREST
            config = generate_client_config(user.id, client_ip)

            # Сохраняем в базу с номером ключа
            save_subscription_to_db(user, plan_key, client_ip, config, config_key=key_num)
            
            # Сохраняем конфиг для отправки
            configs_dict[key_num] = config
        
        # Отправляем сообщение с кнопками deep links
        text = (
            "🔐 Готово! Нажмите на кнопки ниже, чтобы добавить VPN в WireGuard:\n\n"
            "⚠️ **Помните: 1 конфигурация = 1 устройство**\n\n"
            "Просто нажмите на нужную кнопку — конфигурация откроется в WireGuard автоматически!"
        )
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        for key_num in range(1, 8):
            config = configs_dict[key_num]
            link = generate_wireguard_link(f"VPN Ключ {key_num}", config)
            keyboard.add(InlineKeyboardButton(f"🔑 Ключ {key_num}", url=link))
        
        keyboard.add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
        
        await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        print(f"❌ Ошибка создания конфига: {e}")
        await bot.send_message(
            chat_id, 
            f"❌ Ошибка создания VPN конфигурации: {str(e)}\n\n"
            "Попробуйте позже или обратитесь в поддержку: @Jotaro1707"
        )

# ===============================
# Хендлеры: меню, покупки, инструкции
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
        InlineKeyboardButton("🔑 Мои ключи", callback_data="menu_keys"),
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
    await call.answer("Генерируем конфиг…")
    await provision_and_send(call.from_user.id, call.from_user, plan_key)

# --- Мои ключи ---
@dp.callback_query_handler(lambda c: c.data == "menu_keys")
async def callback_keys(call: types.CallbackQuery):
    await call.answer()
    try:
        cursor.execute(
            "SELECT config, config_key FROM subscriptions WHERE user_id=%s ORDER BY config_key",
            (call.from_user.id,)
        )
        configs = cursor.fetchall()
        if configs:
            # Создаем меню с 7 кнопками
            keyboard = InlineKeyboardMarkup(row_width=2)
            buttons = []
            for i in range(1, 8):
                # Проверяем, есть ли конфиг для этого ключа
                config_exists = any(cfg[1] == i for cfg in configs)
                if config_exists:
                    buttons.append(InlineKeyboardButton(f"🔑 Ключ {i}", callback_data=f"key_{i}"))
                else:
                    buttons.append(InlineKeyboardButton(f"❌ Ключ {i}", callback_data=f"key_{i}"))
            
            # Добавляем кнопки по 2 в ряд
            for i in range(0, len(buttons), 2):
                if i + 1 < len(buttons):
                    keyboard.add(buttons[i], buttons[i+1])
                else:
                    keyboard.add(buttons[i])
            
            keyboard.add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
            
            await call.message.answer("🔑 Выберите ключ для скачивания:", reply_markup=keyboard)
        else:
            await call.message.answer("У вас пока нет активных конфигураций.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")))
    except Exception as e:
        print("keys error:", e)
        await call.message.answer("Ошибка при получении ключей. Попробуйте позже.")

# --- Получение конкретного ключа ---
@dp.callback_query_handler(lambda c: c.data.startswith("key_"))
async def callback_send_key(call: types.CallbackQuery):
    await call.answer()
    try:
        key_num = int(call.data.split("_")[1])
        
        # Получаем конфигурацию для этого ключа
        cursor.execute(
            "SELECT config FROM subscriptions WHERE user_id=%s AND config_key=%s",
            (call.from_user.id, key_num)
        )
        result = cursor.fetchone()
        
        if result:
            config = result[0]
            
            # Генерируем deep link и отправляем кнопку
            link = generate_wireguard_link(f"VPN Ключ {key_num}", config)
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(f"🔑 Подключить ключ {key_num}", url=link),
                InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")
            )
            
            await bot.send_message(
                call.from_user.id,
                f"🔑 Нажмите кнопку ниже, чтобы добавить **Ключ {key_num}** в WireGuard:\n\n"
                "⚠️ **Напоминание:** 1 конфигурация = 1 устройство",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await call.message.answer("❌ Этот ключ не найден.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")))
    except Exception as e:
        print("send_key error:", e)
        await call.message.answer("Ошибка при отправке ключа. Попробуйте позже.")

# --- Help menu ---
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

# Help -> connect submenu
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

    text = (
        "Спасибо, что выбрали нас ♥️\n\n"
        "⇩ Куда будем подключать VPN? ⇩"
    )
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
        "3. Если была оплата — проверьте ключи в разделе \"🔑 Мои ключи\".\n\n"
        "Если проблема сохраняется — напишите в поддержку: @Jotaro1707"
    )
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Главное меню", callback_data="menu_main"),
    )
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
    # Создаем новое сообщение вместо редактирования
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
        InlineKeyboardButton("🔑 Мои ключи", callback_data="menu_keys"),
        InlineKeyboardButton("Помощь", callback_data="menu_help")
    )
    await call.message.edit_text(welcome_text, reply_markup=keyboard)

# --- Platform-specific instructions ---
@dp.callback_query_handler(lambda c: c.data == "connect_android")
async def connect_android(call: types.CallbackQuery):
    await call.answer()
    text = (
        "📱 Инструкция по подключению VPN на Android:\n\n"
        "1️⃣ Установите приложение WireGuard: https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        "2️⃣ После покупки нажмите на кнопку с нужным ключом\n"
        "3️⃣ Приложение WireGuard откроется автоматически — нажмите «Добавить туннель»\n"
        "4️⃣ Готово! Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))

@dp.callback_query_handler(lambda c: c.data == "connect_ios")
async def connect_ios(call: types.CallbackQuery):
    await call.answer()
    text = (
        "🍏 Инструкция по подключению VPN на iOS:\n\n"
        "1️⃣ Установите WireGuard: https://apps.apple.com/ru/app/wireguard/id1441195209\n"
        "2️⃣ После покупки нажмите на кнопку с нужным ключом\n"
        "3️⃣ Приложение WireGuard откроется автоматически — нажмите «Добавить туннель»\n"
        "4️⃣ Готово! Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))

@dp.callback_query_handler(lambda c: c.data == "connect_macos")
async def connect_macos(call: types.CallbackQuery):
    await call.answer()
    text = (
        "💻 Инструкция для macOS:\n\n"
        "1️⃣ Установите WireGuard: https://apps.apple.com/ru/app/wireguard/id1451685025?mt=12\n"
        "2️⃣ После покупки нажмите на кнопку с нужным ключом\n"
        "3️⃣ Приложение WireGuard откроется автоматически — нажмите «Добавить туннель»\n"
        "4️⃣ Готово! Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))

@dp.callback_query_handler(lambda c: c.data == "connect_windows")
async def connect_windows(call: types.CallbackQuery):
    await call.answer()
    text = (
        "🖥 Инструкция для Windows:\n\n"
        "1️⃣ Установите WireGuard: https://download.wireguard.com/windows-client/wireguard-installer.exe\n"
        "2️⃣ После покупки нажмите на кнопку с нужным ключом\n"
        "3️⃣ Приложение WireGuard откроется автоматически — нажмите «Добавить туннель»\n"
        "4️⃣ Готово! Включите туннель"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))

# ===============================
# Запуск бота
# ===============================
if __name__ == "__main__":
    print("Запускаю бота…")
    executor.start_polling(dp, skip_updates=True)
