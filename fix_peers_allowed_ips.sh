#!/bin/bash

echo "🔧 Исправление allowed_ips для существующих пиров"
echo "========================================="
echo ""

# Проверка прав
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт с правами root: sudo $0"
    exit 1
fi

# Проверяем, существует ли wg0
if ! ip link show wg0 &>/dev/null; then
    echo "❌ WireGuard интерфейс wg0 не найден"
    exit 1
fi

echo "📋 Получаю список пиров..."
peers=$(wg show wg0 peers | awk '{print $1}')

if [ -z "$peers" ]; then
    echo "⚠️ Нет подключенных пиров"
    exit 0
fi

echo "Найдено пиров: $(echo "$peers" | wc -l)"
echo ""

# Исправляем allowed_ips для каждого пира
fixed=0
not_fixed=0

for peer in $peers; do
    current_allowed=$(wg show wg0 peer "$peer" allowed-ips 2>/dev/null || echo "(none)")
    
    if [ "$current_allowed" = "(none)" ] || [ -z "$current_allowed" ]; then
        echo "🔧 Исправляю allowed_ips для пира ${peer:0:20}..."
        wg set wg0 peer "$peer" allowed-ips 0.0.0.0/0
        
        if [ $? -eq 0 ]; then
            echo "   ✅ Успешно установлено: 0.0.0.0/0"
            ((fixed++))
        else
            echo "   ❌ Ошибка при установке"
            ((not_fixed++))
        fi
    else
        echo "✅ Пиру ${peer:0:20} already has allowed_ips: $current_allowed"
    fi
done

echo ""
echo "========================================="
echo "📊 Результаты:"
echo "   ✅ Исправлено: $fixed"
echo "   ⚠️ Ошибок: $not_fixed"
echo ""

# Показываем финальный статус
echo "📋 Текущее состояние пиров:"
wg show wg0 peers
echo ""

echo "✅ Готово!"

