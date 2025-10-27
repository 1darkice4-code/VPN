#!/bin/bash

# Скрипт для исправления конфигурации WireGuard
# Синхронизирует настройки с кодом бота

set -euo pipefail

echo "🔧 Исправление конфигурации WireGuard..."

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт с правами root: sudo $0"
    exit 1
fi

CONFIG_FILE="/etc/wireguard/wg0.conf"
PRIVATE_KEY_FILE="/etc/wireguard/wg0_private.key"
PUBLIC_KEY_FILE="/etc/wireguard/wg0_public.key"

# Остановить WireGuard если запущен
if systemctl is-active --quiet wg-quick@wg0; then
    echo "⏹️ Останавливаю WireGuard..."
    systemctl stop wg-quick@wg0
fi

# Сгенерировать ключи если их нет
if [ ! -f "$PRIVATE_KEY_FILE" ]; then
    echo "🔑 Генерирую ключи..."
    wg genkey | tee "$PRIVATE_KEY_FILE" | wg pubkey > "$PUBLIC_KEY_FILE"
    chmod 600 "$PRIVATE_KEY_FILE"
    chmod 644 "$PUBLIC_KEY_FILE"
fi

# Прочитать ключи
PRIVATE_KEY=$(cat "$PRIVATE_KEY_FILE")
PUBLIC_KEY=$(cat "$PUBLIC_KEY_FILE")

echo "🔑 Публичный ключ сервера: $PUBLIC_KEY"

# Определить внешний интерфейс
DEFAULT_IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
if [ -z "$DEFAULT_IFACE" ]; then
    echo "❌ Не удалось определить внешний интерфейс"
    exit 1
fi
echo "🌐 Внешний интерфейс: $DEFAULT_IFACE"

# Создать правильную конфигурацию (как в коде бота)
echo "📝 Создаю конфигурацию..."
cat > "$CONFIG_FILE" << EOF
[Interface]
PrivateKey = $PRIVATE_KEY
Address = 10.66.66.1/24
ListenPort = 51831
DNS = 1.1.1.1, 8.8.8.8
MTU = 1420

PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o $DEFAULT_IFACE -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o $DEFAULT_IFACE -j MASQUERADE
EOF

chmod 600 "$CONFIG_FILE"

# Включить IP forwarding
echo "🌐 Включаю IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q "net.ipv4.ip_forward" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Запустить WireGuard
echo "🚀 Запускаю WireGuard..."
systemctl start wg-quick@wg0

sleep 2

if systemctl is-active --quiet wg-quick@wg0; then
    echo "✅ WireGuard запущен успешно!"
    
    echo ""
    echo "📋 Информация для настройки бота:"
    echo "🔑 Публичный ключ: $PUBLIC_KEY"
    echo "🌐 Подсеть: 10.66.66.0/24"
    echo "🔌 Порт: 51831"
    echo "📁 Конфигурация: $CONFIG_FILE"
    
    echo ""
    echo "📝 Обновите vpn_bot/.env:"
    echo "SERVER_PUBLIC_KEY=$PUBLIC_KEY"
    echo "SERVER_ENDPOINT=$(curl -s ifconfig.me):51831"
    
else
    echo "❌ Ошибка при запуске WireGuard!"
    journalctl -u wg-quick@wg0 -n 20
    exit 1
fi

echo ""
echo "🎉 Готово! WireGuard настроен как в коде бота."
