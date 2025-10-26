# VPN Management System

Система управления VPN на базе WireGuard с Telegram ботом и REST API.

## 🚀 Компоненты

- **Telegram Bot** (`vpn_bot/`) - бот для управления VPN подписками
- **WireGuard Server** - VPN сервер
- **wgREST API** (`wgrest/`) - REST API для управления WireGuard
- **PostgreSQL** - база данных для хранения пользователей и подписок

## 📋 Требования

- Docker и Docker Compose
- Python 3.8+ (для локальной разработки)
- Go 1.16+ (для сборки wgrest)

## ⚙️ Быстрый старт

### 1. Настройка Telegram бота

1. Скопируйте пример конфигурации:
   ```bash
   cp vpn_bot/env.example vpn_bot/.env
   ```

2. Получите токен бота у [@BotFather](https://t.me/BotFather)

3. Отредактируйте `vpn_bot/.env`:
   ```env
   BOT_TOKEN=ваш_токен_от_BotFather
   ```

4. Обновите настройки WireGuard сервера:
   ```env
   WG_SERVER_ENDPOINT=ваш_реальный_ip:51830
   WG_SERVER_PUBLIC_KEY=публичный_ключ_сервера
   ```

### 2. Получение публичного ключа WireGuard сервера

После первого запуска WireGuard контейнера, ключ будет в файле:
```
wg/config/wg0.conf
```

Или можно получить через контейнер:
```bash
docker exec wg cat /config/wg0.conf | grep PrivateKey
```

### 3. Запуск системы

```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## 📦 Структура проекта

```
VPN/
├── docker-compose.yml          # Конфигурация Docker Compose
├── SQL/                        # SQL скрипты инициализации БД
│   ├── 01_init.sql
│   ├── create_users.sql
│   ├── create_subscriptions.sql
│   └── create_vpn_profiles.sql
├── vpn_bot/                    # Telegram бот
│   ├── bot.py                  # Основной файл бота
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── env.example             # Пример конфигурации
│   └── .env                    # Ваш конфиг (создается вручную)
├── wgrest/                     # REST API для WireGuard
│   ├── cmd/
│   ├── handlers/
│   ├── Dockerfile
│   └── ...
└── wg/                         # Конфигурация WireGuard
```

## 🌐 Доступ к сервисам

- **Telegram Bot**: Работает автоматически после настройки токена
- **PostgreSQL**: `localhost:5432`
- **WireGuard**: `localhost:51830/udp`
- **wgREST API**: `http://localhost:8080`

## 🔧 API Endpoints (wgREST)

```bash
# Получить список устройств
curl http://localhost:8080/v1/devices/

# Создать новое устройство
curl -X POST http://localhost:8080/v1/devices/ \
  -H "Content-Type: application/json" \
  -d '{"name": "wg0"}'

# Добавить пира к устройству
curl -X POST http://localhost:8080/v1/devices/wg0/peers/ \
  -H "Content-Type: application/json" \
  -d '{"name": "client1"}'
```

Полная документация API: [openapi-spec.yaml](wgrest/openapi-spec.yaml)

## 🗄️ База данных

### Подключение к БД

```bash
docker exec -it vpn_db psql -U vpn_bot_user -d vpn_bot_db
```

### Таблицы

- `users` - Пользователи Telegram бота
- `subscriptions` - Подписки пользователей
- `vpn_profiles` - VPN профили

## 🔐 Безопасность

⚠️ **ВАЖНО**: Перед запуском в продакшене:

1. Измените пароли БД
2. Добавьте аутентификацию для wgREST API
3. Настройте HTTPS для wgREST
4. Ограничьте доступ к портам
5. Используйте секреты для токенов

## 🛠️ Разработка

### Локальный запуск бота

```bash
cd vpn_bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

### Сборка wgrest

```bash
cd wgrest
go mod download
go build -o wgrest ./cmd/wgrest-server
```

## 🐛 Troubleshooting

### Бот не запускается

1. Проверьте наличие `.env` файла
2. Проверьте токен бота
3. Смотрите логи: `docker-compose logs vpn_bot`

### WireGuard не работает

1. Проверьте права на папку `wg/`
2. Убедитесь, что порт 51830 открыт
3. Проверьте логи: `docker-compose logs wg`

### БД не инициализируется

1. Удалите volume: `docker-compose down -v`
2. Перезапустите: `docker-compose up -d`
3. Проверьте логи: `docker-compose logs db`

## 📝 Лицензия

MIT

## 👤 Поддержка

Telegram: @Jotaro1707

