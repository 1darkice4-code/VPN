# ИСПРАВЛЕНИЕ ПРОБЛЕМЫ С wgREST

## Проблема
В логах wgREST видно ошибки:
```
"status":400,"error":"code=400, message=missing key in request header"
```

Это означает, что бот не отправляет токен авторизации в заголовках запросов.

## Исправления

### 1. Исправлена сетевая конфигурация в docker-compose.yml
- Изменен `network_mode` для wgREST с `"container:wg"` на `host`
- Добавлен `extra_hosts` для доступа к хосту из контейнера бота
- Обновлен `WGREST_URL` на `http://host.docker.internal:8080`

### 2. Исправлен код бота (vpn_bot/bot.py)
- Добавлен токен авторизации в запрос к `/version`
- Все запросы к wgREST теперь включают заголовок `Authorization: Bearer {token}`

### 3. Создан файл .env
- Скопируйте `vpn_bot/env.example` в `vpn_bot/.env`
- Укажите ваш реальный `BOT_TOKEN`

## Как применить исправления на сервере

```bash
# 1. Получить обновления
git pull origin main

# 2. Создать файл .env (если его нет)
cp vpn_bot/env.example vpn_bot/.env

# 3. Отредактировать .env и указать ваш BOT_TOKEN
nano vpn_bot/.env

# 4. Перезапустить сервисы
docker-compose down
docker-compose up -d

# 5. Проверить логи
docker logs wgrest
docker logs vpn_bot
```

## Проверка работы

После перезапуска в логах wgREST должны появиться успешные запросы:
```
"status":200,"error":"","latency":38099,"latency_human":"38.099µs"
```

Вместо ошибок 400 с "missing key in request header".
