#!/bin/bash

echo "🔄 Перезапускаем VPN бота..."

# Переходим в папку с ботом
cd /root/VPN

# Обновляем код
echo "📥 Обновляем код..."
git pull origin main

# Проверяем текущий коммит
echo "📋 Текущий коммит:"
git log --oneline -1

# Останавливаем старые процессы бота
echo "🛑 Останавливаем старые процессы..."
pkill -f "python.*bot.py" || true
pkill -f "python3.*bot.py" || true

# Ждем немного
sleep 2

# Запускаем бота в фоне
echo "🚀 Запускаем бота..."
cd vpn_bot
nohup python3 bot.py > bot.log 2>&1 &

# Проверяем, что бот запустился
sleep 3
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "✅ Бот успешно запущен!"
    echo "📊 PID: $(pgrep -f 'python.*bot.py')"
else
    echo "❌ Ошибка запуска бота!"
    echo "📋 Логи:"
    tail -20 bot.log
fi
