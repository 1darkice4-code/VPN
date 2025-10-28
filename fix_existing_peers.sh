#!/bin/bash

echo "🔧 Исправление allowed_ips для существующих пиров WireGuard"
echo "========================================================"

# Получаем список всех пиров
echo "📋 Получаем список пиров..."
peers=$(wg show wg0 peers | awk '{print $1}')

if [ -z "$peers" ]; then
    echo "❌ Пиры не найдены"
    exit 1
fi

echo "Найдено пиров: $(echo "$peers" | wc -l)"
echo ""

# Для каждого пира проверяем allowed_ips
for peer in $peers; do
    echo "🔍 Проверяем пир: ${peer:0:20}..."
    
    # Получаем allowed_ips для пира
    allowed_ips=$(wg show wg0 peer "$peer" allowed-ips 2>/dev/null)
    
    if [ -z "$allowed_ips" ] || [ "$allowed_ips" = "(none)" ]; then
        echo "  ❌ allowed_ips пустые, исправляем..."
        
        # Устанавливаем allowed_ips через wg команду
        wg set wg0 peer "$peer" allowed-ips 0.0.0.0/0
        
        if [ $? -eq 0 ]; then
            echo "  ✅ allowed_ips установлены: 0.0.0.0/0"
        else
            echo "  ❌ Ошибка установки allowed_ips"
        fi
    else
        echo "  ✅ allowed_ips уже установлены: $allowed_ips"
    fi
done

echo ""
echo "📊 Итоговое состояние пиров:"
wg show wg0 peers

echo ""
echo "✅ Исправление завершено!"
