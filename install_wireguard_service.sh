#!/bin/bash

# Скрипт для установки WireGuard как системного сервиса
# Запускать с правами root

set -e

DEVICE_NAME="wg0"
LISTEN_PORT="51830"
CONFIG_DIR="/etc/wireguard"
CONFIG_FILE="$CONFIG_DIR/$DEVICE_NAME.conf"
SERVICE_NAME="wg-quick@$DEVICE_NAME"

echo "🔧 Установка WireGuard как системного сервиса..."

# Проверяем права root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт с правами root: sudo $0"
    exit 1
fi

# Устанавливаем WireGuard
echo "📦 Установка WireGuard..."
apt update
apt install -y wireguard

# Создаем директорию конфигурации
mkdir -p "$CONFIG_DIR"

# Генерируем ключи если не существуют
PRIVATE_KEY_FILE="$CONFIG_DIR/${DEVICE_NAME}_private.key"
PUBLIC_KEY_FILE="$CONFIG_DIR/${DEVICE_NAME}_public.key"

if [ ! -f "$PRIVATE_KEY_FILE" ]; then
    echo "🔑 Генерация ключей сервера..."
    wg genkey | tee "$PRIVATE_KEY_FILE" | wg pubkey > "$PUBLIC_KEY_FILE"
    chmod 600 "$PRIVATE_KEY_FILE"
    chmod 644 "$PUBLIC_KEY_FILE"
fi

# Читаем ключи
PRIVATE_KEY=$(cat "$PRIVATE_KEY_FILE")
PUBLIC_KEY=$(cat "$PUBLIC_KEY_FILE")

echo "🔑 Публичный ключ сервера: $PUBLIC_KEY"

# Создаем конфигурацию WireGuard
echo "📝 Создание конфигурации WireGuard..."
cat > "$CONFIG_FILE" << EOF
[Interface]
PrivateKey = $PRIVATE_KEY
Address = 10.66.66.1/24
ListenPort = $LISTEN_PORT
DNS = 1.1.1.1, 8.8.8.8
MTU = 1420

# Автоматические правила iptables для NAT
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
EOF

# Устанавливаем права доступа
chmod 600 "$CONFIG_FILE"

# Включаем IP forwarding
echo "🌐 Включение IP forwarding..."
echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
sysctl -p

# Запускаем WireGuard как системный сервис
echo "🚀 Запуск WireGuard сервиса..."
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Проверяем статус
echo "📊 Проверка статуса WireGuard..."
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ WireGuard сервис запущен успешно"
else
    echo "❌ Ошибка запуска WireGuard сервиса"
    systemctl status "$SERVICE_NAME"
    exit 1
fi

# Показываем информацию
echo ""
echo "🎉 WireGuard установлен и настроен!"
echo "📋 Публичный ключ сервера: $PUBLIC_KEY"
echo "🌐 Интерфейс: $DEVICE_NAME"
echo "🔌 Порт: $LISTEN_PORT"
echo "📁 Конфигурация: $CONFIG_FILE"
echo "🔧 Сервис: $SERVICE_NAME"

# Показываем статус
echo ""
echo "📊 Статус устройства:"
wg show "$DEVICE_NAME"

echo ""
echo "🔍 Статус сервиса:"
systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
echo "📝 Команды для управления:"
echo "  Остановить: sudo systemctl stop $SERVICE_NAME"
echo "  Запустить:   sudo systemctl start $SERVICE_NAME"
echo "  Перезапустить: sudo systemctl restart $SERVICE_NAME"
echo "  Статус:      sudo systemctl status $SERVICE_NAME"
echo "  Логи:        sudo journalctl -u $SERVICE_NAME -f"
