#!/bin/bash

# Скрипт для создания WireGuard устройства
# Запускать на хосте с правами root

set -e

DEVICE_NAME="wg0"
LISTEN_PORT="51830"
PRIVATE_KEY_FILE="/etc/wireguard/${DEVICE_NAME}_private.key"
PUBLIC_KEY_FILE="/etc/wireguard/${DEVICE_NAME}_public.key"
CONFIG_FILE="/etc/wireguard/${DEVICE_NAME}.conf"

echo "🔧 Создание WireGuard устройства ${DEVICE_NAME}..."

# Создаем директорию если не существует
mkdir -p /etc/wireguard

# Генерируем ключи если не существуют
if [ ! -f "$PRIVATE_KEY_FILE" ]; then
    echo "🔑 Генерация ключей..."
    wg genkey | tee "$PRIVATE_KEY_FILE" | wg pubkey > "$PUBLIC_KEY_FILE"
    chmod 600 "$PRIVATE_KEY_FILE"
    chmod 644 "$PUBLIC_KEY_FILE"
fi

# Читаем ключи
PRIVATE_KEY=$(cat "$PRIVATE_KEY_FILE")
PUBLIC_KEY=$(cat "$PUBLIC_KEY_FILE")

echo "🔑 Публичный ключ: $PUBLIC_KEY"

# Создаем конфигурацию устройства
cat > "$CONFIG_FILE" << EOF
[Interface]
PrivateKey = $PRIVATE_KEY
Address = 10.66.66.1/24
ListenPort = $LISTEN_PORT
DNS = 1.1.1.1, 8.8.8.8
MTU = 1420

# Правила iptables для NAT
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
EOF

# Устанавливаем права доступа
chmod 600 "$CONFIG_FILE"

# Загружаем модуль WireGuard
modprobe wireguard

# Создаем интерфейс
ip link add dev "$DEVICE_NAME" type wireguard

# Настраиваем интерфейс
wg set "$DEVICE_NAME" private-key "$PRIVATE_KEY_FILE"
wg set "$DEVICE_NAME" listen-port "$LISTEN_PORT"

# Поднимаем интерфейс
ip link set "$DEVICE_NAME" up
ip addr add 10.66.66.1/24 dev "$DEVICE_NAME"

echo "✅ WireGuard устройство ${DEVICE_NAME} создано и настроено"
echo "📋 Публичный ключ сервера: $PUBLIC_KEY"
echo "🌐 Интерфейс: $DEVICE_NAME"
echo "🔌 Порт: $LISTEN_PORT"
echo "📁 Конфигурация: $CONFIG_FILE"

# Показываем статус
echo ""
echo "📊 Статус устройства:"
wg show "$DEVICE_NAME"
