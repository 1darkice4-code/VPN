# ⚙️ Настройка wgREST интеграции

## Проблема

wgREST не может напрямую управлять контейнером linuxserver/wireguard через API (ошибки 404/501).

## ✅ Решение

### На сервере выполните:

```bash
# 1. Обновите код
git pull origin main

# 2. Остановите все контейнеры
docker-compose down

# 3. Удалите старые данные wgREST (опционально)
docker volume rm vpn_wgrest_data

# 4. Запустите заново
docker-compose up -d

# 5. Подождите 30 секунд
sleep 30

# 6. Проверьте логи wgREST
docker-compose logs wgrest
```

### Проверьте работу:

```bash
# 1. Проверьте что wgREST работает
curl http://localhost:8080/version

# 2. Проверьте доступность API
curl http://localhost:8080/v1/devices/

# 3. Проверьте логи бота
docker-compose logs vpn_bot
```

## 🔧 Что изменилось:

1. ✅ Добавлен порт для wgREST (8080)
2. ✅ Добавлены environment переменные
3. ✅ Включен USE_WGREST=true
4. ✅ Удален PEERS=10 (пиры создаются через wgREST)

## ⚠️ Важно

wgREST должен работать с файлами конфигураций WireGuard в директории `./wg`.

Если wgREST все еще выдает ошибки:

### Альтернативный вариант - используйте wgREST вместо linuxserver/wireguard:

Замените в `docker-compose.yml` секцию `wg`:

```yaml
wg:
  image: ghcr.io/suquant/wgrest
  container_name: wg
  cap_add:
    - NET_ADMIN
  volumes:
    - ./wg:/config
  ports:
    - "51830:51820/udp"
```

Но это потребует переделки всей схемы.

## 🎯 Текущая конфигурация

Бот будет пытаться использовать wgREST API:
- Если wgREST доступен → использует API
- Если wgREST недоступен → fallback на демо-конфиги

### Просмотр работы:

```bash
# Логи бота покажут:
docker-compose logs vpn_bot | grep -E "wgREST|wgrest|конфиг"
```

Должны увидеть либо:
- `✅ Конфиг получен через wgREST` (работает!)
- `⚠️ wgREST недоступен` (fallback режим)

---

**Интеграция включена, обновите на сервере!**

