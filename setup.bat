@echo off
echo 🚀 Настройка VPN системы...

REM Проверка наличия Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker не установлен. Установите Docker и попробуйте снова.
    exit /b 1
)

REM Создаем .env файл если его нет
if not exist "vpn_bot\.env" (
    echo 📝 Создаю файл vpn_bot\.env...
    copy vpn_bot\env.example vpn_bot\.env
    echo ⚠️  НЕ ЗАБЫТЬ: Отредактируйте vpn_bot\.env и укажите токен бота!
)

REM Создаем директории если нужно
if not exist "wg" mkdir wg
if not exist "SQL" mkdir SQL

echo ✅ Настройка завершена!
echo.
echo 📋 Следующие шаги:
echo 1. Отредактируйте vpn_bot\.env и укажите токен бота
echo 2. Запустите: docker-compose up -d
echo 3. Проверьте логи: docker-compose logs -f

