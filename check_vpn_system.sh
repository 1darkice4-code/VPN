#!/bin/bash

# Скрипт для проверки статуса VPN системы
# Проверяет WireGuard сервис, wgREST и бота

echo "🔍 Проверка статуса VPN системы..."
echo "=================================="

# Проверяем WireGuard сервис
echo ""
echo "1️⃣ Проверка WireGuard сервиса:"
if systemctl is-active --quiet wg-quick@wg0; then
    echo "✅ WireGuard сервис запущен"
    
    # Показываем статус устройства
    echo "📊 Статус устройства wg0:"
    wg show wg0
    
    # Показываем IP адрес
    echo "🌐 IP адрес wg0:"
    ip addr show wg0 | grep "inet " || echo "   IP адрес не назначен"
    
else
    echo "❌ WireGuard сервис не запущен"
    echo "   Запустите: sudo systemctl start wg-quick@wg0"
fi

# Проверяем wgREST
echo ""
echo "2️⃣ Проверка wgREST API:"
if curl -s http://localhost:8080/version >/dev/null 2>&1; then
    echo "✅ wgREST API доступен"
    
    # Проверяем доступность устройства через API
    if curl -s -H "Authorization: Bearer b1g5r4nd0mt0k3n12345" http://localhost:8080/v1/devices/wg0/ >/dev/null 2>&1; then
        echo "✅ Устройство wg0 доступно через wgREST API"
    else
        echo "❌ Устройство wg0 недоступно через wgREST API"
    fi
else
    echo "❌ wgREST API недоступен"
    echo "   Проверьте: docker logs wgrest"
fi

# Проверяем Docker контейнеры
echo ""
echo "3️⃣ Проверка Docker контейнеров:"
if command -v docker >/dev/null 2>&1; then
    echo "📦 Статус контейнеров:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(vpn_|wgrest)"
    
    # Проверяем логи wgREST
    echo ""
    echo "📋 Последние логи wgREST:"
    docker logs wgrest --tail 5 2>/dev/null || echo "   Контейнер wgrest не найден"
    
    # Проверяем логи бота
    echo ""
    echo "📋 Последние логи бота:"
    docker logs vpn_bot --tail 5 2>/dev/null || echo "   Контейнер vpn_bot не найден"
else
    echo "❌ Docker не установлен"
fi

# Проверяем сетевые правила
echo ""
echo "4️⃣ Проверка сетевых правил:"
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

# Проверяем IP forwarding
echo ""
echo "5️⃣ Проверка IP forwarding:"
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
    echo "✅ IP forwarding включен"
else
    echo "❌ IP forwarding отключен"
    echo "   Включите: echo 1 > /proc/sys/net/ipv4/ip_forward"
fi

# Итоговая оценка
echo ""
echo "=================================="
echo "📊 ИТОГОВАЯ ОЦЕНКА:"

# Подсчитываем количество успешных проверок
success_count=0
total_checks=5

if systemctl is-active --quiet wg-quick@wg0; then ((success_count++)); fi
if curl -s http://localhost:8080/version >/dev/null 2>&1; then ((success_count++)); fi
if docker ps | grep -q "wgrest"; then ((success_count++)); fi
if iptables -L FORWARD | grep -q "wg0"; then ((success_count++)); fi
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then ((success_count++)); fi

echo "✅ Успешно: $success_count/$total_checks"

if [ $success_count -eq $total_checks ]; then
    echo "🎉 Система работает корректно!"
elif [ $success_count -ge 3 ]; then
    echo "⚠️ Система работает с предупреждениями"
else
    echo "❌ Система требует внимания"
fi

echo ""
echo "📝 Полезные команды:"
echo "  Перезапустить WireGuard: sudo systemctl restart wg-quick@wg0"
echo "  Перезапустить контейнеры: docker-compose restart"
echo "  Логи wgREST: docker logs wgrest -f"
echo "  Логи бота: docker logs vpn_bot -f"
echo "  Статус WireGuard: sudo systemctl status wg-quick@wg0"
