# 🔧 Информация о wgREST

## Что это?

wgREST - это REST API для управления WireGuard, написанный на Go.

## 🎯 Функциональность

wgREST предоставляет HTTP API для:
- ✅ Создания/удаления WireGuard устройств
- ✅ Добавления/удаления пиров (клиентов)
- ✅ Получения конфигураций пиров
- ✅ Генерации QR кодов для быстрого подключения
- ✅ Управления настройками устройств (DNS, AllowedIPs и т.д.)

## 📋 API Endpoints

### Устройства (Devices)

```
GET    /v1/devices/                    - Список устройств
POST   /v1/devices/                    - Создать устройство
GET    /v1/devices/:name                - Информация об устройстве
PATCH  /v1/devices/:name                - Обновить устройство
DELETE /v1/devices/:name                - Удалить устройство
```

### Пиры (Peers)

```
GET    /v1/devices/:name/peers/                              - Список пиров
POST   /v1/devices/:name/peers/                              - Добавить пира
GET    /v1/devices/:name/peers/:urlSafePubKey                - Информация о пире
PATCH  /v1/devices/:name/peers/:urlSafePubKey                - Обновить пира
DELETE /v1/devices/:name/peers/:urlSafePubKey                - Удалить пира
GET    /v1/devices/:name/peers/:urlSafePubKey/quick.conf     - Получить конфиг
GET    /v1/devices/:name/peers/:urlSafePubKey/quick.conf.png - QR код
```

## ⚙️ Конфигурация

В `docker-compose.yml` настроено:

```yaml
wgrest:
  ports:
    - "8080:8000"              # API доступен на порту 8080
  environment:
    WGREST_LISTEN: 0.0.0.0:8000       # Слушает на всех интерфейсах
    WGREST_DATA_DIR: /var/lib/wgrest  # Директория для данных
  volumes:
    - ./wg:/config                   # WireGuard конфиги
    - wgrest_data:/var/lib/wgrest     # Данные wgREST
```

## 🚀 Запуск и проверка

### 1. Сборка и запуск

```bash
docker-compose up -d wgrest
```

### 2. Проверка работы

```bash
# Проверка версии
curl http://localhost:8080/version

# Список устройств
curl http://localhost:8080/v1/devices/

# Создание устройства wg0
curl -X POST http://localhost:8080/v1/devices/ \
  -H "Content-Type: application/json" \
  -d '{"name": "wg0"}'
```

### 3. Логи

```bash
docker-compose logs -f wgrest
```

## 📖 Использование с ботом

**Важно**: В текущей версии бот **НЕ использует wgREST API**. 

Бот генерирует конфиги самостоятельно для демонстрации.

Для интеграции бота с wgREST нужно:

```python
import requests

async def create_real_wg_peer(user_id: int, plan: str):
    """Создание пира через wgREST API"""
    response = requests.post(
        'http://wgrest:8000/v1/devices/wg0/peers/',
        json={
            'name': f'user_{user_id}',
            'description': f'Plan: {plan}'
        }
    )
    peer = response.json()
    
    # Получаем конфиг
    config_response = requests.get(
        f"http://wgrest:8000/v1/devices/wg0/peers/{peer['urlSafePubKey']}/quick.conf"
    )
    return config_response.text
```

## 🔒 Безопасность

### Для продакшна рекомендуется:

1. **Добавить аутентификацию**:
```yaml
wgrest:
  environment:
    WGREST_STATIC_AUTH_TOKEN: your_secret_token
```

2. **Использовать HTTPS**:
```yaml
wgrest:
  environment:
    WGREST_TLS_DOMAIN: vpn.example.com
```

3. **Ограничить доступ** через Nginx reverse proxy

## 🐛 Troubleshooting

### wgREST не запускается

```bash
# Проверьте логи
docker-compose logs wgrest

# Проверьте сборку
docker-compose build wgrest

# Пересоберите без кеша
docker-compose build --no-cache wgrest
```

### Ошибка доступа к конфигам

```bash
# Проверьте права на файлы
ls -la ./wg

# Проверьте монтирование
docker exec wgrest ls -la /config
```

### API не отвечает

```bash
# Проверьте, что контейнер запущен
docker-compose ps wgrest

# Проверьте порт
curl http://localhost:8080/version

# Проверьте сеть Docker
docker network inspect vpn_vpn_network
```

## 📚 Документация

Полная OpenAPI спецификация: [openapi-spec.yaml](wgrest/openapi-spec.yaml)

Официальная документация: https://github.com/suquant/wgrest

## ✅ Текущий статус

wgREST настроен и готов к использованию:

- ✅ Dockerfile исправлен
- ✅ Сборка проходит без git
- ✅ Настроен в docker-compose.yml
- ✅ Доступен на порту 8080
- ⚠️ Бот пока не использует wgREST (планируется интеграция)

---

**wgREST готов к работе! 🎉**

