#!/bin/bash

echo "========================================="
echo "🔍 ПОЛНАЯ ДИАГНОСТИКА WIREGUARD СИСТЕМЫ"
echo "========================================="
echo ""

# 1. Проверка IP forwarding
echo "1️⃣ IP Forwarding:"
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
    echo "   ✅ Включен"
else
    echo "   ❌ НЕ ВКЛЮЧЕН - это может быть причиной отсутствия трафика!"
fi
echo ""

# 2. Проверка WireGuard интерфейса
echo "2️⃣ WireGuard интерфейс:"
if ip link show wg0 &>/dev/null; then
    echo "   ✅ wg0 существует"
    ip addr show wg0 | grep -E "inet |state"
else
    echo "   ❌ wg0 не найден"
fi
echo ""

# 3. Проверка роутов
echo "3️⃣ Роуты для wg0:"
ip route show | grep wg0 || echo "   ⚠️ Роуты для wg0 не найдены"
echo ""

# 4. Проверка iptables правил
echo "4️⃣ iptables правила для FORWARD:"
if iptables -C FORWARD -i wg0 -j ACCEPT 2>/dev/null; then
    echo "   ✅ FORWARD -i wg0 -j ACCEPT существует"
else
    echo "   ❌ FORWARD -i wg0 -j ACCEPT ОТСУТСТВУЕТ"
fi

if iptables -C FORWARD -o wg0 -j ACCEPT 2>/dev/null; then
    echo "   ✅ FORWARD -o wg0 -j ACCEPT существует"
else
    echo "   ❌ FORWARD -o wg0 -j ACCEPT ОТСУТСТВУЕТ"
fi
echo ""

echo "5️⃣ iptables правила для POSTROUTING:"
DEFAULT_IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
if [ -n "$DEFAULT_IFACE" ]; then
    if iptables -t nat -C POSTROUTING -o "$DEFAULT_IFACE" -j MASQUERADE 2>/dev/null; then
        echo "   ✅ POSTROUTING -o $DEFAULT_IFACE -j MASQUERADE существует"
    else
        echo "   ❌ POSTROUTING -o $DEFAULT_IFACE -j MASQUERADE ОТСУТСТВУЕТ"
    fi
fi
echo ""

# 5. Проверка пиров
echo "6️⃣ Подключенные пиры:"
wg show wg0 | grep -E "peer:|allowed ips:|latest handshake:" || echo "   Нет подключенных пиров"
echo ""

# 6. Проверка allowed_ips у пиров
echo "7️⃣ allowed_ips у пиров:"
peers=$(wg show wg0 peers 2>/dev/null | awk '{print $1}' || echo "")
if [ -z "$peers" ]; then
    echo "   Нет пиров для проверки"
else
    for peer in $peers; do
        allowed_ips=$(wg show wg0 peer "$peer" allowed-ips 2>/dev/null || echo "ERROR")
        if [ "$allowed_ips" = "(none)" ] || [ "$allowed_ips" = "" ]; then
            echo "   ❌ Пиру $peer НЕ УСТАНОВЛЕНЫ allowed_ips"
        elif [ "$allowed_ips" = "ERROR" ]; then
            echo "   ⚠️ Ошибка получения allowed_ips для $peer"
        else
            echo "   ✅ Пиру $peer установлены allowed_ips: $allowed_ips"
        fi
    done
fi
echo ""

# 7. Проверка wgREST API
echo "8️⃣ wgREST API:"
if curl -s http://localhost:8080/version >/dev/null 2>&1; then
    echo "   ✅ wgREST доступен"
    curl -s http://localhost:8080/version
else
    echo "   ❌ wgREST недоступен"
fi
echo ""

# 8. Проверка логов WireGuard
echo "9️⃣ Последние ошибки WireGuard (если есть):"
journalctl -u wg-quick@wg0 -n 5 --no-pager 2>/dev/null | grep -i error || echo "   Нет ошибок"
echo ""

echo "========================================="
echo "✅ Диагностика завершена"
echo "========================================="

