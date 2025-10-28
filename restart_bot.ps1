# Перезапуск VPN бота
Write-Host "🔄 Перезапускаем VPN бота..." -ForegroundColor Yellow

# Переходим в папку с ботом
Set-Location "C:\ssh_keys\VPN"

# Обновляем код
Write-Host "📥 Обновляем код..." -ForegroundColor Blue
git pull origin main

# Проверяем текущий коммит
Write-Host "📋 Текущий коммит:" -ForegroundColor Green
git log --oneline -1

# Останавливаем старые процессы бота
Write-Host "🛑 Останавливаем старые процессы..." -ForegroundColor Red
Get-Process | Where-Object {$_.ProcessName -like "*python*" -and $_.CommandLine -like "*bot.py*"} | Stop-Process -Force -ErrorAction SilentlyContinue

# Ждем немного
Start-Sleep -Seconds 2

# Запускаем бота
Write-Host "🚀 Запускаем бота..." -ForegroundColor Green
Set-Location "vpn_bot"
Start-Process python -ArgumentList "bot.py" -WindowStyle Hidden

# Проверяем, что бот запустился
Start-Sleep -Seconds 3
$botProcess = Get-Process | Where-Object {$_.ProcessName -like "*python*" -and $_.CommandLine -like "*bot.py*"}
if ($botProcess) {
    Write-Host "✅ Бот успешно запущен!" -ForegroundColor Green
    Write-Host "📊 PID: $($botProcess.Id)" -ForegroundColor Cyan
} else {
    Write-Host "❌ Ошибка запуска бота!" -ForegroundColor Red
}
