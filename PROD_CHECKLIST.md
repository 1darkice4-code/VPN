# ✅ Чеклист для продакшн развертывания

## ❌ Текущие проблемы

### 1. Бот генерирует НЕ настоящие WireGuard ключи
**Проблема**: В функции `generate_client_config()` используются случайные строки вместо настоящих WG ключей.

**Код (line 94 bot.py)**:
```python
private_key = secrets.token_urlsafe(32)  # Это НЕ настоящий WG ключ!
```

**Почему не работает**: WireGuard требует реальные криптографические ключи.

### 2. Бот НЕ подключен к wgREST API
**Проблема**: Бот генерирует конфиги самостоятельно, а не использует wgREST API.

**Что нужно**: Бот должен вызывать wgREST для создания пиров.

### 3. Нет интеграции с WireGuard сервером
**Проблема**: Конфиги сохраняются в БД, но не добавляются в WireGuard сервер.

## ✅ Что работает

✅ Бот запускается  
✅ Бот подключается к БД  
✅ Бот сохраняет пользователей  
✅ Бот сохраняет подписки  
✅ Бот отправляет конфиги пользователям (НО конфиги не рабочие!)  
✅ База данных работает  
✅ WireGuard сервер работает  
✅ wgREST API работает  

## 🔧 Что нужно исправить для продакшна

### Вариант 1: Интеграция с wgREST (РЕКОМЕНДУЕТСЯ)

Добавить функцию создания пиров через wgREST API:

```python
import requests

async def create_real_wg_peer(user_id: int, plan: str):
    """Создание реального пира через wgREST"""
    WG_ENDPOINT = os.getenv("WG_SERVER_ENDPOINT", "")
    
    # 1. Получаем или создаем устройство wg0
    device_response = requests.get(f'http://wgrest:8000/v1/devices/wg0/')
    
    if device_response.status_code == 404:
        # Создаем устройство
        requests.post(
            'http://wgrest:8000/v1/devices/',
            json={'name': 'wg0'}
        )
    
    # 2. Создаем пира
    peer_response = requests.post(
        'http://wgrest:8000/v1/devices/wg0/peers/',
        json={
            'name': f'user_{user_id}',
            'description': f'Plan: {plan}'
        }
    )
    
    peer = peer_response.json()
    
    # 3. Получаем конфиг
    config_response = requests.get(
        f"http://wgrest:8000/v1/devices/wg0/peers/{peer['urlSafePubKey']}/quick.conf"
    )
    
    return config_response.text
```

Заменить в `provision_and_send()`:
```python
# ВМЕСТО:
config = generate_client_config(client_ip)

# ИСПОЛЬЗОВАТЬ:
config = await create_real_wg_peer(user.id, plan_key)
```

### Вариант 2: Использование wg команды (для VPS)

Если на сервере установлен WireGuard:

```python
import subprocess

def generate_real_wg_keys():
    """Генерация настоящих WireGuard ключей"""
    # Генерируем приватный ключ
    private_key = subprocess.run(
        ['wg', 'genkey'],
        capture_output=True,
        text=True
    ).stdout.strip()
    
    # Получаем публичный ключ
    public_key = subprocess.run(
        ['wg', 'pubkey'],
        input=private_key,
        capture_output=True,
        text=True
    ).stdout.strip()
    
    return private_key, public_key
```

## 📋 Полный чеклист для продакшна

### Обязательно:

- [ ] Интегрировать бота с wgREST API
- [ ] Изменить генерацию ключей на настоящие
- [ ] Настроить WG_SERVER_PUBLIC_KEY (получить после запуска wg)
- [ ] Настроить WG_SERVER_ENDPOINT (внешний IP сервера)
- [ ] Изменить пароли БД
- [ ] Настроить токен бота
- [ ] Открыть порт 51830/udp в файрволе
- [ ] Настроить backup базы данных
- [ ] Добавить мониторинг

### Рекомендуется:

- [ ] Добавить аутентификацию для wgREST
- [ ] Настроить HTTPS через Nginx
- [ ] Добавить логирование
- [ ] Настроить ротацию логов
- [ ] Добавить мониторинг ресурсов

## 🚀 Быстрый фикс для запуска

Если нужно просто запустить на сервере СЕЙЧАС (демо-режим):

1. Скопировать `vpn_bot/env.example` в `vpn_bot/.env`
2. Указать `BOT_TOKEN`
3. Указать `WG_SERVER_ENDPOINT` (IP сервера:51830)
4. После запуска получить реальный `WG_SERVER_PUBLIC_KEY`:
   ```bash
   docker exec wg cat /config/wg0.conf | grep PublicKey
   ```
5. Обновить `WG_SERVER_PUBLIC_KEY` в `.env`
6. Перезапустить бота

**НО**: Конфиги будут демо-версией и не будут подключаться к VPN!

## 🎯 Рекомендуемая последовательность

1. Запустить все компоненты локально (тест)
2. Исправить интеграцию с wgREST
3. Протестировать создание реальных пиров
4. Развернуть на сервере
5. Настроить мониторинг и backup

---

**Вывод**: На сервере система запустится, но VPN конфиги НЕ будут работать, пока не интегрируете с wgREST API!

