#!/bin/bash

echo "🔍 Диагностика проблем с трафиком WireGuard VPN"
echo "=============================================="

# 1. Проверяем IP forwarding
echo "1️⃣ Проверка IP forwarding:"
ip_forward=$(cat /proc/sys/net/ipv4/ip_forward)
if [ "$ip_forward" = "1" ]; then
    echo "✅ IP forwarding включен"
else
    echo "❌ IP forwarding ОТКЛЮЧЕН!"
    echo "   Включите командой: echo 1 > /proc/sys/net/ipv4/ip_forward"
    echo "   Для постоянного включения: echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf"
fi

echo ""

# 2. Проверяем WireGuard интерфейс
echo "2️⃣ Проверка WireGuard интерфейса:"
if ip link show wg0 >/dev/null 2>&1; then
    echo "✅ Интерфейс wg0 существует"
    echo "   Адреса:"
    ip addr show wg0 | grep inet
else
    echo "❌ Интерфейс wg0 не найден!"
fi

echo ""

# 3. Проверяем маршруты
echo "3️⃣ Проверка маршрутов:"
echo "   Таблица маршрутизации:"
ip route show | head -5
echo "   WireGuard маршруты:"
ip route show | grep wg0 || echo "   Нет маршрутов через wg0"

echo ""

# 4. Проверяем iptables правила
echo "4️⃣ Проверка iptables правил:"
echo "   NAT правила:"
iptables -t nat -L POSTROUTING -n -v | grep MASQUERADE || echo "   ❌ Нет правил MASQUERADE!"
echo "   FORWARD правила:"
iptables -L FORWARD -n -v | grep wg0 || echo "   ❌ Нет правил FORWARD для wg0!"

echo ""

# 5. Проверяем подключенных пиров
echo "5️⃣ Проверка подключенных пиров:"
if command -v wg >/dev/null 2>&1; then
    wg show
else
    echo "❌ Команда wg не найдена!"
fi

echo ""

# 6. Проверяем статус сервиса
echo "6️⃣ Проверка статуса сервиса:"
if systemctl is-active --quiet wg-quick@wg0; then
    echo "✅ Сервис wg-quick@wg0 активен"
else
    echo "❌ Сервис wg-quick@wg0 НЕ активен!"
    echo "   Запустите: systemctl start wg-quick@wg0"
fi

echo ""

# 7. Проверяем логи
echo "7️⃣ Последние логи WireGuard:"
journalctl -u wg-quick@wg0 --no-pager -n 10

echo ""
echo "🔧 Рекомендации:"
echo "1. Убедитесь, что IP forwarding включен"
echo "2. Проверьте, что iptables правила настроены правильно"
echo "3. Убедитесь, что WireGuard сервис запущен"
echo "4. Проверьте, что пиры подключены и передают трафик"
