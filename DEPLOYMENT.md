# 🚢 Развертывание VPN системы

## Продакшн развертывание

### 1. Системные требования

- **ОС**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM**: минимум 2GB, рекомендуется 4GB+
- **CPU**: минимум 2 ядра
- **Диск**: минимум 10GB свободного места
- **Docker**: версия 20.10+
- **Docker Compose**: версия 2.0+

### 2. Установка зависимостей

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose git

# CentOS/RHEL
sudo yum install -y docker docker-compose git
sudo systemctl start docker
sudo systemctl enable docker

# Добавить пользователя в группу docker
sudo usermod -aG docker $USER
```

### 3. Настройка файрвола

```bash
# Открыть необходимые порты
sudo ufw allow 51830/udp    # WireGuard
sudo ufw allow 8080/tcp      # wgREST API
sudo ufw allow 22/tcp        # SSH
sudo ufw enable
```

### 4. Клонирование репозитория

```bash
cd /opt
sudo git clone <repository-url> vpn
cd vpn
sudo chown -R $USER:$USER .
```

### 5. Настройка переменных окружения

```bash
# Скопируйте пример конфигурации
cp vpn_bot/env.example vpn_bot/.env

# Отредактируйте конфигурацию
nano vpn_bot/.env
```

**Обязательно измените:**
- `BOT_TOKEN` - токен Telegram бота
- `WG_SERVER_ENDPOINT` - внешний IP сервера
- `DB_PASSWORD` - надежный пароль БД

### 6. Настройка WireGuard

После первого запуска:

```bash
# Получить публичный ключ
docker exec wg cat /config/wg0.conf | grep PublicKey

# Обновить в vpn_bot/.env
nano vpn_bot/.env
```

Также настройте `SERVERURL` в `docker-compose.yml`:
```yaml
environment:
  - SERVERURL=your.domain.com
```

### 7. Настройка обратного прокси (Nginx)

```bash
sudo apt install nginx

# Создать конфигурацию
sudo nano /etc/nginx/sites-available/vpn
```

```nginx
server {
    listen 80;
    server_name your.domain.com;
    
    # wgREST API
    location /api/ {
        proxy_pass http://localhost:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Swagger UI
    location /docs {
        proxy_pass http://localhost:8080/;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/vpn /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8. Настройка SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

### 9. Запуск системы

```bash
# Запуск в фоновом режиме
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

### 10. Настройка автостарта

Создайте systemd сервис:

```bash
sudo nano /etc/systemd/system/vpn.service
```

```ini
[Unit]
Description=VPN Management System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/vpn
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn
sudo systemctl start vpn
```

## 🔒 Безопасность

### 1. Ограничение доступа к wgREST API

Добавьте в `docker-compose.yml`:
```yaml
wgrest:
  environment:
    - WGREST_STATIC_AUTH_TOKEN=your_secret_token_here
```

Теперь все запросы требуют заголовок:
```bash
curl -H "Authorization: Bearer your_secret_token_here" http://localhost:8080/v1/devices/
```

### 2. Смена паролей БД

В `docker-compose.yml`:
```yaml
db:
  environment:
    POSTGRES_PASSWORD: your_strong_password_here
```

### 3. Backup базы данных

Создайте скрипт `/opt/vpn/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/vpn/backups"
mkdir -p $BACKUP_DIR

# Backup БД
docker exec vpn_db pg_dump -U vpn_bot_user vpn_bot_db > $BACKUP_DIR/db_$(date +%Y%m%d_%H%M%S).sql

# Backup конфигураций WireGuard
tar -czf $BACKUP_DIR/wg_$(date +%Y%m%d_%H%M%S).tar.gz wg/

# Удалить старые бэкапы (старше 7 дней)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

```bash
chmod +x /opt/vpn/backup.sh
crontab -e
```

Добавьте:
```
0 2 * * * /opt/vpn/backup.sh
```

## 📊 Мониторинг

### Prometheus и Grafana

См. [monitoring/](monitoring/) для настройки мониторинга.

### Логи

```bash
# Логи всех сервисов
docker-compose logs -f > /var/log/vpn.log

# Ротация логов
sudo nano /etc/logrotate.d/vpn
```

```
/var/log/vpn.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 root root
}
```

## 🔄 Обновление

```bash
cd /opt/vpn
git pull
docker-compose down
docker-compose build
docker-compose up -d
docker-compose logs -f
```

## 🆘 Troubleshooting

### Бот не отвечает

```bash
# Проверьте логи
docker-compose logs vpn_bot

# Проверьте .env
cat vpn_bot/.env

# Проверьте подключение к БД
docker exec vpn_db psql -U vpn_bot_user -d vpn_bot_db -c "SELECT * FROM users LIMIT 1;"
```

### WireGuard не работает

```bash
# Проверьте конфигурацию
docker exec wg cat /config/wg0.conf

# Проверьте порт
sudo netstat -ulnp | grep 51830

# Перезапустите контейнер
docker-compose restart wg
```

### База данных не подключается

```bash
# Проверьте статус контейнера
docker-compose ps db

# Проверьте логи
docker-compose logs db

# Пересоздайте БД
docker-compose down
docker volume rm vpn_db_data
docker-compose up -d
```

## 📞 Поддержка

Telegram: @Jotaro1707

