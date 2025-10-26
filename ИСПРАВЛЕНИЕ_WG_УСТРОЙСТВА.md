# ИСПРАВЛЕНИЕ ПРОБЛЕМЫ С СОЗДАНИЕМ WIREGUARD УСТРОЙСТВА

## Проблема
wgREST возвращает ошибку 501 (Not Implemented) при попытке создать WireGuard устройство через API:
```
"status":501,"error":"","latency":462347,"latency_human":"462.347µs"
```

## Причина
Функция `CreateDevice` в wgREST **не реализована** - она просто возвращает `http.StatusNotImplemented`.

## Решение

### 1. Создать WireGuard устройство вручную на хосте

Выполните на сервере с правами root:

```bash
# 1. Сделать скрипт исполняемым
chmod +x setup_wireguard.sh

# 2. Запустить скрипт создания устройства
sudo ./setup_wireguard.sh
```

### 2. Альтернативный способ (если скрипт не работает)

```bash
# Установить WireGuard
sudo apt update
sudo apt install wireguard

# Создать директорию
sudo mkdir -p /etc/wireguard

# Сгенерировать ключи
sudo wg genkey | sudo tee /etc/wireguard/wg0_private.key | sudo wg pubkey | sudo tee /etc/wireguard/wg0_public.key

# Установить права
sudo chmod 600 /etc/wireguard/wg0_private.key
sudo chmod 644 /etc/wireguard/wg0_public.key

# Создать интерфейс
sudo ip link add dev wg0 type wireguard

# Настроить интерфейс
sudo wg set wg0 private-key /etc/wireguard/wg0_private.key
sudo wg set wg0 listen-port 51830

# Поднять интерфейс
sudo ip link set wg0 up
sudo ip addr add 10.66.66.1/24 dev wg0

# Настроить iptables для NAT
sudo iptables -A FORWARD -i wg0 -j ACCEPT
sudo iptables -A FORWARD -o wg0 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

### 3. Проверить создание устройства

```bash
# Проверить статус
sudo wg show wg0

# Проверить интерфейс
ip addr show wg0
```

### 4. Перезапустить контейнеры

```bash
# Получить обновления
git pull origin main

# Перезапустить контейнеры
docker-compose down
docker-compose up -d

# Проверить логи
docker logs wgrest
docker logs vpn_bot
```

## Ожидаемый результат

После создания устройства в логах wgREST должны появиться:
```
✅ Устройство wg0 существует
```

А в логах бота:
```
✅ Конфиг получен через wgREST
```

## Автоматический запуск

Чтобы устройство создавалось автоматически при перезагрузке, добавьте в `/etc/rc.local`:

```bash
# Добавить перед exit 0
ip link add dev wg0 type wireguard
wg set wg0 private-key /etc/wireguard/wg0_private.key
wg set wg0 listen-port 51830
ip link set wg0 up
ip addr add 10.66.66.1/24 dev wg0
```

## Проверка работы

После выполнения всех шагов:
1. Устройство `wg0` должно существовать
2. wgREST должен находить устройство (статус 200)
3. Бот должен создавать пиров и генерировать конфиги
4. Пользователи должны получать рабочие VPN конфигурации
