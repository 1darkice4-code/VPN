import os
import secrets
import requests
import base64
import urllib.parse
import subprocess
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
import psycopg2
from dotenv import load_dotenv
from typing import Tuple

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
cursor.execute("""
CREATE TABLE IF NOT EXISTS configs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    config_key INTEGER NOT NULL,
    public_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, config_key)
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

# Словарь для хранения ID последнего сообщения каждого пользователя
user_last_message = {}

# Планы (включая личные и семейные)
PLANS = {
    # Личные планы (1 устройство)
    "personal_1m": {"name": "Личный 1 мес", "price": 149, "devices": 1, "type": "personal"},
    "personal_3m": {"name": "Личный 3 мес", "price": 400, "devices": 1, "type": "personal"},
    "personal_6m": {"name": "Личный 6 мес", "price": 1200, "devices": 1, "type": "personal"},
    "personal_1y": {"name": "Личный 1 год", "price": 2000, "devices": 1, "type": "personal"},
    
    # Семейные планы (до 7 устройств)
    "family_1m": {"name": "Семейный 1 мес", "price": 499, "devices": 7, "type": "family"},
    "family_3m": {"name": "Семейный 3 мес", "price": 1399, "devices": 7, "type": "family"},
    "family_6m": {"name": "Семейный 6 мес", "price": 1999, "devices": 7, "type": "family"},
    "family_1y": {"name": "Семейный 1 год", "price": 2999, "devices": 7, "type": "family"}
}

# ===============================
# Вспомогательные функции
# ===============================

async def delete_previous_messages(user_id: int):
    """Удаляет предыдущие сообщения пользователя"""
    if user_id in user_last_message:
        try:
            await bot.delete_message(user_id, user_last_message[user_id])
        except:
            pass  # Игнорируем ошибки удаления

async def update_last_message(user_id: int, message_id: int):
    """Обновляет ID последнего сообщения пользователя"""
    user_last_message[user_id] = message_id

def check_ip_forwarding():
    """Проверяем, включен ли IP forwarding на сервере"""
    try:
        with open('/proc/sys/net/ipv4/ip_forward', 'r') as f:
            return f.read().strip() == '1'
    except:
        return False

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
        # Используем wgREST API для создания реального пира
        
        # 1. Проверяем доступность wgREST
        try:
            headers = {}
            if WGREST_AUTH_TOKEN:
                headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
            response = requests.get(f"{WGREST_URL}/version", headers=headers, timeout=3)
            print(f"wgREST доступен, версия: {response.text}")
        except:
            raise Exception("wgREST недоступен")
        
        # 2. Проверяем доступность устройства
        if not check_wg_device():
            raise Exception("WireGuard устройство недоступно. Проверьте, что WireGuard сервис запущен.")
        
        # 3. Проверяем IP forwarding
        if not check_ip_forwarding():
            print("⚠️ IP forwarding не включен на сервере! Трафик может не работать.")
        
        # 4. Создаем пира через API
        peer_name = f"user_{user_id}_{secrets.token_hex(4)}"
        
        # Генерируем IP для клиента (10.66.66.10-250) в подсети сервера
        client_ip = f"10.66.66.{10 + (user_id % 240)}/32"
        
        headers = {"Content-Type": "application/json"}
        if WGREST_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {WGREST_AUTH_TOKEN}"
        
        # Создаем пира без allowed_ips (wgREST может не поддерживать это при создании)
        response = requests.post(
            f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/",
            json={
                "name": peer_name
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
            
            # Обновляем allowed_ips для пира (весь трафик через VPN)
            update_response = requests.patch(
                f"{WGREST_URL}/v1/devices/{WGREST_DEVICE}/peers/{peer_key}/",
                json={
                    "allowed_ips": ["0.0.0.0/0"]
                },
                headers=headers,
                timeout=10
            )
            
            if update_response.status_code in [200, 204]:
                print(f"✅ Allowed IPs обновлены для пира {peer_key}")
            else:
                print(f"⚠️ Не удалось обновить allowed_ips: {update_response.status_code}")
            
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
        print(f"❌ wgREST недоступен: {e}")
        # Не генерируем fallback конфиг - это вводит пользователей в заблуждение
        raise Exception(f"wgREST API недоступен: {e}")


def generate_client_config(user_id: int, client_ip: str) -> Tuple[str, str]:
    """Генерируем конфиг WireGuard через wgREST API"""
    try:
        # Используем wgREST для создания реального пира
        config, public_key = create_peer_via_wgrest(user_id, "VIP")
        return config, public_key
    except Exception as e:
        print(f"❌ Ошибка создания конфига через wgREST: {e}")
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

def save_config_to_db(user: types.User, config_key: int, public_key: str):
    """Сохраняем public_key конфигурации в таблицу configs"""
    try:
        # Убедимся, что пользователь есть
        save_user_to_db(user)
        cursor.execute(
            "INSERT INTO configs (user_id, config_key, public_key) VALUES (%s, %s, %s) ON CONFLICT (user_id, config_key) DO UPDATE SET public_key = EXCLUDED.public_key",
            (user.id, config_key, public_key)
        )
        conn.commit()
    except Exception as e:
        print("DB save_config error:", e)
        conn.rollback()

# ===============================
# Генерация WireGuard deep links
# ===============================
def generate_wireguard_link(name: str, conf_text: str) -> str:
    """Генерирует deep link для автоматического импорта конфигурации в WireGuard"""
    try:
        # Кодируем конфигурацию в base64
        encoded_conf = base64.b64encode(conf_text.encode('utf-8')).decode('utf-8')
        
        # Экранируем спецсимволы, чтобы ссылка не "сломалась"
        encoded_conf = urllib.parse.quote(encoded_conf)
        
        # Формируем deep link
        link = f"wireguard://import?name={urllib.parse.quote(name)}&config={encoded_conf}"
        
        print(f"Generated WireGuard link length: {len(link)} characters")
        return link
    except Exception as e:
        print(f"Error generating WireGuard link: {e}")
        return ""

def is_peer_active(public_key: str, interface: str = "wg0") -> bool:
    """
    Проверяет активность WireGuard пира по public_key
    
    Args:
        public_key: публичный ключ пира
        interface: интерфейс WireGuard (по умолчанию wg0)
    
    Returns:
        True если пир активен (last_handshake < 180 секунд), False иначе
    """
    try:
        # Выполняем команду wg show для получения информации о пирах
        result = subprocess.run(
            ['wg', 'show', interface, 'dump'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"❌ Ошибка выполнения wg show {interface} dump: {result.stderr}")
            return False
        
        # Парсим вывод команды
        # Формат: private_key public_key preshared_key endpoint allowed_ips last_handshake rx_bytes tx_bytes persistent_keepalive
        current_time = int(time.time())
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
                
            parts = line.split('\t')
            if len(parts) >= 6:
                peer_public_key = parts[1]
                last_handshake_str = parts[5]
                
                # Проверяем, что это наш пир
                if peer_public_key == public_key:
                    # Если last_handshake равен 0, пир никогда не подключался
                    if last_handshake_str == '0':
                        return False
                    
                    try:
                        last_handshake = int(last_handshake_str)
                        time_diff = current_time - last_handshake
                        
                        # Проверяем, что прошло менее 180 секунд (3 минуты)
                        return time_diff < 180
                    except ValueError:
                        print(f"❌ Неверный формат last_handshake: {last_handshake_str}")
                        return False
        
        # Если пир не найден в выводе, считаем его неактивным
        print(f"⚠️ Пир с public_key {public_key} не найден в интерфейсе {interface}")
        return False
        
    except subprocess.TimeoutExpired:
        print(f"❌ Таймаут выполнения команды wg show {interface} dump")
        return False
    except Exception as e:
        print(f"❌ Ошибка проверки активности пира: {e}")
        return False

# ===============================
# Отправка конфига (основная логика)
# ===============================
async def provision_and_send(chat_id: int, user: types.User, plan_key: str):
    """Генерируем конфиги в зависимости от плана, сохраняем в БД и отправляем меню с кнопками"""
    plan = PLANS.get(plan_key)
    if not plan:
        await bot.send_message(chat_id, "❌ Ошибка: выбран неверный план.")
        return

    try:
        # Определяем количество конфигураций в зависимости от плана
        max_devices = plan.get('devices', 1)
        
        # Генерируем конфигурации
        for key_num in range(1, max_devices + 1):
            # Генерируем уникальный IP для каждой конфигурации
            client_ip = f"10.66.66.{10 + ((user.id + key_num) % 240)}/32"
            
            # Генерируем конфиг через wgREST
            config, public_key = generate_client_config(user.id, client_ip)

            # Сохраняем в базу с номером ключа
            save_subscription_to_db(user, plan_key, client_ip, config, config_key=key_num)
            
            # Сохраняем public_key в таблицу configs
            save_config_to_db(user, key_num, public_key)
        
        # Отправляем информационное сообщение
        device_text = "1 устройство" if max_devices == 1 else f"до {max_devices} устройств"
        info_text = (
            f"🎉 **Поздравляем! Вы приобрели план: {plan['name']}**\n\n"
            f"🔐 Вам доступно {max_devices} конфигураций WireGuard\n\n"
            f"📱 **План позволяет подключить: {device_text}**\n\n"
            "⚠️ **Помните: 1 конфигурация = 1 устройство**\n\n"
            "Для получения конфигурации нажмите на соответствующую кнопку ниже:"
        )
        
        # Создаем меню с кнопками в зависимости от количества устройств
        keyboard = InlineKeyboardMarkup(row_width=2)
        buttons = []
        for i in range(1, max_devices + 1):
            buttons.append(InlineKeyboardButton(f"🔑 Ключ {i}", callback_data=f"key_{i}"))
        
        # Добавляем кнопки по 2 в ряд
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                keyboard.add(buttons[i], buttons[i+1])
            else:
                keyboard.add(buttons[i])
        
        keyboard.add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
        
        sent_message = await bot.send_message(chat_id, info_text, parse_mode="Markdown", reply_markup=keyboard)
        await update_last_message(user.id, sent_message.message_id)
            
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

    sent_message = await message.answer(welcome_text, reply_markup=keyboard)
    await update_last_message(message.from_user.id, sent_message.message_id)

# --- Buy menu ---
@dp.callback_query_handler(lambda c: c.data == "menu_buy")
async def callback_buy(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "📋 **Выберите тип подписки:**\n\n"
        "👤 **Личный план** - для одного устройства\n"
        "👨‍👩‍👧‍👦 **Семейный план** - до 7 устройств\n\n"
        "⇩ Выберите категорию ⇩"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("👤 Личный план", callback_data="plan_personal"),
        InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный план", callback_data="plan_family"),
        InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main")
    )
    
    sent_message = await call.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

# --- Personal plans ---
@dp.callback_query_handler(lambda c: c.data == "plan_personal")
async def callback_personal_plans(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "👤 **Личные планы**\n\n"
        "📱 **Для одного устройства**\n"
        "💡 Идеально для индивидуального использования\n\n"
        "⇩ Выберите период ⇩"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    personal_plans = {k: v for k, v in PLANS.items() if v.get('type') == 'personal'}
    for key, plan in personal_plans.items():
        keyboard.add(InlineKeyboardButton(f"{plan['name']} — {plan['price']}₽", callback_data=f"buy_{key}"))
    
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_buy"))
    
    sent_message = await call.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

# --- Family plans ---
@dp.callback_query_handler(lambda c: c.data == "plan_family")
async def callback_family_plans(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "👨‍👩‍👧‍👦 **Семейные планы**\n\n"
        "📱 **До 7 устройств**\n"
        "💡 Идеально для семьи или команды\n\n"
        "⇩ Выберите период ⇩"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    family_plans = {k: v for k, v in PLANS.items() if v.get('type') == 'family'}
    for key, plan in family_plans.items():
        keyboard.add(InlineKeyboardButton(f"{plan['name']} — {plan['price']}₽", callback_data=f"buy_{key}"))
    
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_buy"))
    
    sent_message = await call.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

@dp.callback_query_handler(lambda call: call.data.startswith("buy_"))
async def process_buy(call: types.CallbackQuery):
    plan_key = call.data.split("_", 1)[1]
    await call.answer()  # Убираем текст "Генерируем конфиг…"
    await provision_and_send(call.from_user.id, call.from_user, plan_key)

# --- Мои ключи ---
@dp.callback_query_handler(lambda c: c.data == "menu_keys")
async def callback_keys(call: types.CallbackQuery):
    await call.answer()
    
    try:
        # Проверяем, есть ли у пользователя конфигурации
        cursor.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE user_id=%s",
            (call.from_user.id,)
        )
        config_count = cursor.fetchone()[0]
        
        if config_count > 0:
            # Получаем все конфигурации пользователя
            cursor.execute(
                "SELECT config_key FROM subscriptions WHERE user_id=%s ORDER BY config_key",
                (call.from_user.id,)
            )
            configs = cursor.fetchall()
            config_keys = [cfg[0] for cfg in configs]
            
            # Определяем максимальное количество ключей для отображения
            max_keys = max(config_keys) if config_keys else 7
            
            # Создаем меню с кнопками
            keyboard = InlineKeyboardMarkup(row_width=2)
            buttons = []
            for i in range(1, max_keys + 1):
                # Проверяем, есть ли конфиг для этого ключа
                if i in config_keys:
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
            
            sent_message = await call.message.answer("🔑 Выберите ключ:", reply_markup=keyboard)
            await update_last_message(call.from_user.id, sent_message.message_id)
        else:
            sent_message = await call.message.answer(
                "У вас пока нет активных конфигураций.\n\nВыберите план в разделе \"Выбрать план VPN\"",
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Главное меню", callback_data="menu_main"))
            )
            await update_last_message(call.from_user.id, sent_message.message_id)
    except Exception as e:
        print("keys error:", e)
        await call.answer("❌ Ошибка при получении ключей", show_alert=True)

# --- Получение конкретного ключа ---
@dp.callback_query_handler(lambda c: c.data.startswith("key_"))
async def callback_send_key(call: types.CallbackQuery):
    await call.answer()
    try:
        key_num = int(call.data.split("_")[1])
        
        # Получаем конфигурацию и public_key для этого ключа
        cursor.execute(
            "SELECT s.config, c.public_key FROM subscriptions s "
            "LEFT JOIN configs c ON s.user_id = c.user_id AND s.config_key = c.config_key "
            "WHERE s.user_id=%s AND s.config_key=%s",
            (call.from_user.id, key_num)
        )
        result = cursor.fetchone()
        
        if result:
            config, public_key = result
            
            # Проверяем активность конфигурации
            if public_key and is_peer_active(public_key):
                # Конфигурация активна - отправляем предупреждение
                await call.answer("⚠️ Этот ключ уже используется. Выберите другой ключ.", show_alert=True)
            else:
                # Конфигурация неактивна - отправляем только конфиг
                try:
                    from io import BytesIO
                    bio = BytesIO()
                    bio.write(config.encode())
                    bio.seek(0)
                    bio.name = f"wg_key_{key_num}.conf"
                    
                    await bot.send_document(
                        call.from_user.id, 
                        bio, 
                        caption=f"🔑 Ключ {key_num}"
                    )
                    
                except Exception as e:
                    print(f"send_document error for key {key_num}:", e)
                    await call.answer("❌ Ошибка при отправке ключа", show_alert=True)
        else:
            await call.answer("❌ Этот ключ не найден", show_alert=True)
    except Exception as e:
        print("send_key error:", e)
        await call.answer("❌ Ошибка при отправке ключа", show_alert=True)

# --- Help menu ---
@dp.callback_query_handler(lambda c: c.data == "menu_help")
async def callback_help(call: types.CallbackQuery):
    await call.answer()
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Как подключиться?", callback_data="help_connect"),
        InlineKeyboardButton("Не работает VPN", callback_data="help_issue"),
        InlineKeyboardButton("Связаться со мной", callback_data="help_contact"),
        InlineKeyboardButton("Главное меню", callback_data="menu_main")
    )

    sent_message = await call.message.answer("Выберите пункт меню:", reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

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

    text = "Куда будем подключать VPN?"
    sent_message = await call.message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
    await update_last_message(call.from_user.id, sent_message.message_id)

@dp.callback_query_handler(lambda c: c.data == "help_issue")
async def help_issue(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "Попробуйте:\n\n"
        "1. Выключить/включить VPN\n"
        "2. Перезагрузить устройство\n"
        "3. Проверить ключи в разделе \"🔑 Мои ключи\"\n\n"
        "Если проблема сохраняется — @Jotaro1707"
    )
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Главное меню", callback_data="menu_main"),
    )
    sent_message = await call.message.answer(text, reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

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
    sent_message = await call.message.answer(text, reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

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
        InlineKeyboardButton("🔑 Мои ключи", callback_data="menu_keys"),
        InlineKeyboardButton("Помощь", callback_data="menu_help")
    )
    sent_message = await call.message.answer(welcome_text, reply_markup=keyboard)
    await update_last_message(call.from_user.id, sent_message.message_id)

# --- Platform-specific instructions ---
@dp.callback_query_handler(lambda c: c.data == "connect_android")
async def connect_android(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "📱 Android:\n\n"
        "1. Установите WireGuard\n"
        "2. Получите ключ в разделе \"🔑 Мои ключи\"\n"
        "3. Импортируйте файл .conf в приложение"
    )
    sent_message = await call.message.answer(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))
    await update_last_message(call.from_user.id, sent_message.message_id)

@dp.callback_query_handler(lambda c: c.data == "connect_ios")
async def connect_ios(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "🍏 iOS:\n\n"
        "1. Установите WireGuard\n"
        "2. Получите ключ в разделе \"🔑 Мои ключи\"\n"
        "3. Импортируйте файл .conf в приложение"
    )
    sent_message = await call.message.answer(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))
    await update_last_message(call.from_user.id, sent_message.message_id)

@dp.callback_query_handler(lambda c: c.data == "connect_macos")
async def connect_macos(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "💻 macOS:\n\n"
        "1. Установите WireGuard\n"
        "2. Получите ключ в разделе \"🔑 Мои ключи\"\n"
        "3. Импортируйте файл .conf в приложение"
    )
    sent_message = await call.message.answer(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))
    await update_last_message(call.from_user.id, sent_message.message_id)

@dp.callback_query_handler(lambda c: c.data == "connect_windows")
async def connect_windows(call: types.CallbackQuery):
    await call.answer()
    
    text = (
        "🖥 Windows:\n\n"
        "1. Установите WireGuard\n"
        "2. Получите ключ в разделе \"🔑 Мои ключи\"\n"
        "3. Импортируйте файл .conf в приложение"
    )
    sent_message = await call.message.answer(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Главное меню", callback_data="menu_main")))
    await update_last_message(call.from_user.id, sent_message.message_id)

# ===============================
# Запуск бота
# ===============================
if __name__ == "__main__":
    print("Запускаю бота…")
    executor.start_polling(dp, skip_updates=True)
