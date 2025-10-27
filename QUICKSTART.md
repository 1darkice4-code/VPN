# 🚀 Быстрый старт VPN системы

## Шаг 1: Подготовка

### Windows
Запустите скрипт настройки:
```cmd
setup.bat
```

### Linux/Mac
```bash
chmod +x setup.sh
./setup.sh
```

## Шаг 2: Настройка Telegram бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям и создайте бота
4. Скопируйте токен бота

5. Отредактируйте файл `vpn_bot/.env`:
   ```env
   BOT_TOKEN=ваш_токен_здесь
   ```

## Шаг 3: Получение публичного ключа WireGuard

После первого запуска получите публичный ключ сервера:

### Вариант 1: Через Docker
```bash
docker exec wg cat /config/wg0.conf | grep PublicKey
```

### Вариант 2: Через файл
```bash
cat wg/config/wg0.conf | grep PublicKey
```

Скопируйте значение **PublicKey** и обновите в `vpn_bot/.env`:
```env
WG_SERVER_PUBLIC_KEY=скопированный_ключ
```

Также обновите адрес сервера:
```env
WG_SERVER_ENDPOINT=ваш_внешний_ip:51831
```

## Шаг 4: Запуск

```bash
docker-compose up -d
```

## Шаг 5: Проверка

Проверьте логи:
```bash
# Все сервисы
docker-compose logs -f

# Только бот
docker-compose logs -f vpn_bot

# Только база данных
docker-compose logs -f db

# Только WireGuard
docker-compose logs -f wg
```

## Шаг 6: Первое подключение

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Выберите план подписки
4. Получите конфиг

## 📱 Установка WireGuard клиента

- **Android**: [Google Play](https://play.google.com/store/apps/details?id=com.wireguard.android)
- **iOS**: [App Store](https://apps.apple.com/ru/app/wireguard/id1441195209)
- **Windows**: [Скачать](https://download.wireguard.com/windows-client/wireguard-installer.exe)
- **macOS**: [App Store](https://apps.apple.com/ru/app/wireguard/id1451685025?mt=12)
- **Linux**: `sudo apt install wireguard` или `sudo yum install wireguard-tools`

## 🔧 Устранение проблем

### Бот не запускается
```bash
# Проверьте .env файл
cat vpn_bot/.env

# Проверьте логи
docker-compose logs vpn_bot

# Перезапустите
docker-compose restart vpn_bot
```

### WireGuard не работает
```bash
# Проверьте конфигурацию
docker exec wg cat /config/wg0.conf

# Проверьте логи
docker-compose logs wg

# Перезапустите
docker-compose restart wg
```

### База данных не инициализируется
```bash
# Полная перезагрузка
docker-compose down -v
docker-compose up -d

# Проверьте инициализацию
docker exec vpn_db psql -U vpn_bot_user -d vpn_bot_db -c "\dt"
```

## 🛑 Остановка

```bash
docker-compose down
```

Или с удалением данных:
```bash
docker-compose down -v
```

## 🔄 Обновление

```bash
# Остановите
docker-compose down

# Обновите код (git pull)

# Пересоберите
docker-compose build

# Запустите
docker-compose up -d
```

## 📊 Мониторинг

### Статус контейнеров
```bash
docker-compose ps
```

### Использование ресурсов
```bash
docker stats
```

### Проверка подключений к БД
```bash
docker exec vpn_db psql -U vpn_bot_user -d vpn_bot_db
```

## 🎯 Следующие шаги

1. Настройте платежи (интеграция с YooKassa/Stripe)
2. Добавьте аутентификацию для wgREST API
3. Настройте мониторинг и алерты
4. Добавьте backup базы данных

