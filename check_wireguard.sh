#!/bin/bash

# Скрипт для проверки статуса WireGuard

echo "🔍 Проверка статуса WireGuard..."

# Проверить модуль WireGuard
if lsmod | grep -q wireguard; then
    echo "✅ Модуль WireGuard загружен"
else
    echo "❌ Модуль WireGuard не загружен"
    echo "   Загрузите модуль: sudo modprobe wireguard"
fi

# Проверить интерфейс wg0
if ip link show wg0 >/dev/null 2>&1; then
    echo "✅ Интерфейс wg0 существует"
    
    # Проверить статус
    if ip link show wg0 | grep -q "state UP"; then
        echo "✅ Интерфейс wg0 активен"
    else
        echo "⚠️ Интерфейс wg0 неактивен"
    fi
    
    # Показать конфигурацию
    echo ""
    echo "📊 Конфигурация wg0:"
    sudo wg show wg0
    
    # Показать IP адрес
    echo ""
    echo "🌐 IP адрес wg0:"
    ip addr show wg0 | grep "inet "
    
else
    echo "❌ Интерфейс wg0 не существует"
    echo "   Создайте интерфейс: sudo ip link add dev wg0 type wireguard"
fi

# Проверить файлы ключей
if [ -f "/etc/wireguard/wg0_private.key" ]; then
    echo "✅ Приватный ключ существует"
else
    echo "❌ Приватный ключ не найден"
fi

if [ -f "/etc/wireguard/wg0_public.key" ]; then
    echo "✅ Публичный ключ существует"
    echo "🔑 Публичный ключ: $(cat /etc/wireguard/wg0_public.key)"
else
    echo "❌ Публичный ключ не найден"
fi

# Проверить iptables правила
echo ""
echo "🔒 Проверка iptables правил:"
if iptables -L FORWARD | grep -q "wg0"; then
    echo "✅ Правила FORWARD для wg0 настроены"
else
    echo "❌ Правила FORWARD для wg0 не настроены"
fi

if iptables -t nat -L POSTROUTING | grep -q "MASQUERADE"; then
    echo "✅ NAT правила настроены"
else
    echo "❌ NAT правила не настроены"
fi
