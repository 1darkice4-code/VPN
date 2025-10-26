#!/bin/bash

# Безопасная установка WireGuard как системного сервиса
# Автор: Альберт (адаптировано с улучшениями)
# Требует root

set -euo pipefail
LOG_FILE="/var/log/wireguard_install.log"
exec > >(tee -a "$LOG_FILE") 2>&1

DEVICE_NAME="wg0"
LISTEN_PORT="51830"
CONFIG_DIR="/etc/wireguard"
CONFIG_FILE="$CONFIG_DIR/$DEVICE_NAME.conf"
SERVICE_NAME="wg-quick@$DEVICE_NAME"

echo "🔧 Установка WireGuard как системного сервиса..."
echo "🕓 $(date)"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт с правами root: sudo $0"
    exit 1
fi

# Проверка и удаление старого интерфейса wg0, если остался
if ip link show "$DEVICE_NAME" &>/dev/null; then
    echo "⚠️ Интерфейс $DEVICE_NAME уже существует — удаляю..."
    ip link delete "$DEVICE_NAME" || true
fi

# Установка WireGuard
echo "📦 Проверка наличия WireGuard..."
apt update -y
apt install -y wireguard >/dev/null 2>&1

# Создание директории
mkdir -p "$CONFIG_DIR"

# Определение основного сетевого интерфейса (где есть выход в интернет)
DEFAULT_IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
if [ -z "$DEFAULT_IFACE" ]; then
    echo "❌ Не удалось определить сетевой интерфейс с выходом в интернет"
    exit 1
fi
echo "🌐 Основной интерфейс: $DEFAULT_IFACE"

# Поиск свободной подсети (чтобы не конфликтовать с Docker)
echo "🔍 Подбор свободной подсети..."
for NET in 10.44.44 10.55.55 10.66.66 10.77.77 10.88.88 10.99.99; do
    if ! ip addr | grep -q "${NET}"; then
        WG_NET="${NET}.0/24"
        WG_IP="${NET}.1/24"
        break
    fi
done

if [ -z "${WG_NET:-}" ]; then
    echo "❌ Не удалось найти свободную подсеть для WireGuard"
    exit 1
fi
echo "✅ Выбрана подсеть: $WG_NET"

# Генерация ключей
PRIVATE_KEY_FILE="$CONFIG_DIR/${DEVICE_NAME}_private.key"
PUBLIC_KEY_FILE="$CONFIG_DIR/${DEVICE_NAME}_public.key"

if [ ! -f "$PRIVATE_KEY_FILE" ]; then
    echo "🔑 Генерация ключей сервера..."
    wg genkey | tee "$PRIVATE_KEY_FILE" | wg pubkey > "$PUBLIC_KEY_FILE"
    chmod 600 "$PRIVATE_KEY_FILE"
    chmod 644 "$PUBLIC_KEY_FILE"
fi

PRIVATE_KEY=$(cat "$PRIVATE_KEY_FILE")
PUBLIC_KEY=$(cat "$PUBLIC_KEY_FILE")

echo "🔑 Публичный ключ сервера: $PUBLIC_KEY"

# Создание конфигурации
echo "📝 Создание конфигурации WireGuard..."
cat > "$CONFIG_FILE" << EOF
[Interface]
PrivateKey = $PRIVATE_KEY
Address = $WG_IP
ListenPort = $LISTEN_PORT
DNS = 1.1.1.1,8.8.8.8
MTU = 1420

PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o $DEFAULT_IFACE -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o $DEFAULT_IFACE -j MASQUERADE
EOF

chmod 600 "$CONFIG_FILE"

# Включение IP forwarding
echo "🌐 Включение IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q "net.ipv4.ip_forward" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Запуск WireGuard
echo "🚀 Запуск WireGuard сервиса..."
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ WireGuard сервис запущен успешно!"
else
    echo "❌ Ошибка при запуске WireGuard!"
    journalctl -u "$SERVICE_NAME" -n 20
    exit 1
fi

# Финальная информация
echo ""
echo "🎉 WireGuard установлен и запущен"
echo "📋 Публичный ключ: $PUBLIC_KEY"
echo "📁 Конфигурация: $CONFIG_FILE"
echo "🌐 Подсеть: $WG_NET"
echo "🔌 Порт: $LISTEN_PORT"
echo "🔧 Интерфейс: $DEVICE_NAME"
echo "🪪 Внешний интерфейс: $DEFAULT_IFACE"
echo ""
echo "🪶 Лог установки: $LOG_FILE"
