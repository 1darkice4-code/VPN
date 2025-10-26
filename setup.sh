#!/bin/bash

echo "🚀 Настройка VPN системы..."

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и попробуйте снова."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose и попробуйте снова."
    exit 1
fi

# Создаем .env файл если его нет
if [ ! -f "vpn_bot/.env" ]; then
    echo "📝 Создаю файл vpn_bot/.env..."
    cp vpn_bot/env.example vpn_bot/.env
    echo "⚠️  НЕ ЗАБЫТЬ: Отредактируйте vpn_bot/.env и укажите токен бота!"
fi

# Создаем директории если нужно
mkdir -p wg
mkdir -p SQL

echo "✅ Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Отредактируйте vpn_bot/.env и укажите токен бота"
echo "2. Запустите: docker-compose up -d"
echo "3. Проверьте логи: docker-compose logs -f"

