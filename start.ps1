# PowerShell скрипт для запуска VPN системы

Write-Host "🚀 VPN Management System Setup" -ForegroundColor Green
Write-Host ""

# Проверка Docker
try {
    docker --version | Out-Null
    Write-Host "✅ Docker установлен" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker не установлен!" -ForegroundColor Red
    Write-Host "Установите Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Создание .env файла если нет
if (-not (Test-Path "vpn_bot\.env")) {
    Write-Host "📝 Создание файла vpn_bot\.env..." -ForegroundColor Yellow
    Copy-Item "vpn_bot\env.example" -Destination "vpn_bot\.env"
    Write-Host "⚠️  ВАЖНО: Отредактируйте vpn_bot\.env и укажите BOT_TOKEN!" -ForegroundColor Red
    Write-Host "Нажмите Enter когда закончите редактирование..." -ForegroundColor Yellow
    Read-Host
}

# Создание директорий
New-Item -ItemType Directory -Force -Path "wg" | Out-Null
New-Item -ItemType Directory -Force -Path "SQL" | Out-Null

Write-Host ""
Write-Host "🔨 Запуск системы..." -ForegroundColor Cyan
docker-compose up -d

Write-Host ""
Write-Host "⏳ Ожидание готовности сервисов..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "✅ Система запущена!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Полезные команды:" -ForegroundColor Cyan
Write-Host "  Логи всех сервисов: docker-compose logs -f"
Write-Host "  Логи бота: docker-compose logs -f vpn_bot"
Write-Host "  Остановка: docker-compose down"
Write-Host "  Перезапуск: docker-compose restart"
Write-Host ""
Write-Host "🌐 Сервисы доступны:" -ForegroundColor Cyan
Write-Host "  - REST API: http://localhost:8080"
Write-Host "  - WireGuard: localhost:51830"
Write-Host "  - PostgreSQL: localhost:5432"
Write-Host ""

