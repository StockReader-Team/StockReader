# 🚀 راهنمای Deploy - Telegram Data Cleaner

این راهنما مراحل deploy کردن پروژه روی سرور production را توضیح می‌دهد.

---

## 📋 پیش‌نیازها

### سرور:
- Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- حداقل 2GB RAM
- حداقل 20GB فضای دیسک
- دسترسی root یا sudo

### نرم‌افزارها:
```bash
# 1. Docker & Docker Compose
sudo apt update
sudo apt install -y docker.io docker-compose

# 2. Git
sudo apt install -y git

# 3. (اختیاری) Nginx برای reverse proxy
sudo apt install -y nginx
```

---

## 🔧 مرحله 1: کلون کردن پروژه

```bash
# رفتن به مسیر دلخواه
cd /opt

# کلون پروژه
sudo git clone <YOUR_REPO_URL> telegram_data_cleaner
cd telegram_data_cleaner

# دادن دسترسی
sudo chown -R $USER:$USER /opt/telegram_data_cleaner
```

---

## ⚙️ مرحله 2: تنظیمات محیطی (.env)

```bash
# کپی فایل نمونه
cp .env.example .env

# ویرایش تنظیمات
nano .env
```

### تنظیمات مهم برای Production:

```env
# Database (از داخل Docker)
DATABASE_URL=postgresql+asyncpg://telegram_user:STRONG_PASSWORD_HERE@postgres:5432/telegram_data
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis (از داخل Docker)
REDIS_URL=redis://redis:6379/0
REDIS_CACHE_TTL=3600

# API خارجی
API_URL=http://103.75.197.239:3000/api/all-messages
API_TOKEN=telegramreader-api-token-2025
API_TIMEOUT=60

# Polling
POLLING_INTERVAL=180
BATCH_SIZE=100

# Application
LOG_LEVEL=INFO
HISTORY_DAYS=15
ENVIRONMENT=production

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security (⚠️ تغییر دهید!)
SECRET_KEY=CHANGE_THIS_TO_A_SECURE_RANDOM_STRING
ALLOWED_ORIGINS=http://your-domain.com,https://your-domain.com
```

**⚠️ مهم**: `SECRET_KEY` و `DATABASE_URL` password را تغییر دهید!

---

## 🐳 مرحله 3: راه‌اندازی با Docker Compose

### فایل `docker-compose.production.yml`:

```bash
nano docker-compose.production.yml
```

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: telegram_postgres
    restart: always
    environment:
      POSTGRES_USER: telegram_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-telegram_pass}
      POSTGRES_DB: telegram_data
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"  # فقط localhost
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U telegram_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: telegram_redis
    restart: always
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"  # فقط localhost
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # FastAPI Application
  app:
    build: .
    container_name: telegram_app
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://telegram_user:${DB_PASSWORD:-telegram_pass}@postgres:5432/telegram_data
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
```

### ساخت Dockerfile:

```bash
nano Dockerfile
```

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# نصب dependencies سیستمی
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# نصب Poetry
RUN pip install poetry

# کپی فایل‌های dependency
COPY pyproject.toml poetry.lock ./

# نصب dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# کپی کد
COPY . .

# ساخت پوشه logs
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🏗️ مرحله 4: اجرای سیستم

```bash
# 1. Build و اجرای containers
docker-compose -f docker-compose.production.yml up -d --build

# 2. چک کردن وضعیت
docker-compose -f docker-compose.production.yml ps

# 3. مشاهده logs
docker-compose -f docker-compose.production.yml logs -f app

# 4. اجرای migrations
docker-compose -f docker-compose.production.yml exec app poetry run alembic upgrade head
```

---

## 🔄 مرحله 5: Systemd Service (اختیاری)

برای مدیریت بهتر، یک systemd service بسازید:

```bash
sudo nano /etc/systemd/system/telegram-data-cleaner.service
```

```ini
[Unit]
Description=Telegram Data Cleaner Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/telegram_data_cleaner
ExecStart=/usr/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.production.yml down
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
# فعال‌سازی
sudo systemctl daemon-reload
sudo systemctl enable telegram-data-cleaner
sudo systemctl start telegram-data-cleaner

# چک وضعیت
sudo systemctl status telegram-data-cleaner
```

---

## 🌐 مرحله 6: Nginx Reverse Proxy (اختیاری)

برای دسترسی از طریق دامنه:

```bash
sudo nano /etc/nginx/sites-available/telegram-data-cleaner
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

```bash
# فعال‌سازی
sudo ln -s /etc/nginx/sites-available/telegram-data-cleaner /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### نصب SSL با Let's Encrypt:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 📊 مرحله 7: Monitoring

### چک کردن logs:

```bash
# Application logs
docker-compose -f docker-compose.production.yml logs -f app

# Database logs
docker-compose -f docker-compose.production.yml logs -f postgres

# همه logs
docker-compose -f docker-compose.production.yml logs -f
```

### مانیتورینگ منابع:

```bash
# استفاده از منابع
docker stats

# فضای دیسک
df -h

# حافظه
free -h
```

---

## 🔒 مرحله 8: امنیت

### 1. Firewall:

```bash
# فقط پورت‌های لازم را باز کنید
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 2. بستن پورت‌های داخلی:

در `docker-compose.production.yml` پورت‌های PostgreSQL و Redis را فقط روی localhost bind کنید:

```yaml
ports:
  - "127.0.0.1:5432:5432"  # ✅ فقط localhost
  # - "5432:5432"          # ❌ همه‌جا قابل دسترسی
```

### 3. تغییر پسوردهای پیش‌فرض:

```bash
# در .env
SECRET_KEY=<generate-secure-random-string>
DB_PASSWORD=<strong-password>
```

---

## 🔄 مرحله 9: Backup

### Automatic Backup Script:

```bash
nano /opt/telegram_data_cleaner/backup.sh
```

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/telegram_data_cleaner"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec telegram_postgres pg_dump -U telegram_user telegram_data | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# حذف backup های قدیمی‌تر از 7 روز
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/db_$DATE.sql.gz"
```

```bash
chmod +x /opt/telegram_data_cleaner/backup.sh

# اضافه کردن به crontab (هر روز ساعت 2 صبح)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/telegram_data_cleaner/backup.sh") | crontab -
```

---

## 🔄 مرحله 10: Update کردن

```bash
# 1. رفتن به پوشه پروژه
cd /opt/telegram_data_cleaner

# 2. Pull کردن آخرین تغییرات
git pull origin main

# 3. Rebuild و restart
docker-compose -f docker-compose.production.yml up -d --build

# 4. اجرای migrations (در صورت نیاز)
docker-compose -f docker-compose.production.yml exec app poetry run alembic upgrade head
```

---

## 🐛 عیب‌یابی (Troubleshooting)

### سرویس بالا نمی‌آید:

```bash
# چک logs
docker-compose -f docker-compose.production.yml logs app

# چک health
docker-compose -f docker-compose.production.yml ps

# Restart
docker-compose -f docker-compose.production.yml restart app
```

### Database connection error:

```bash
# چک PostgreSQL
docker exec telegram_postgres pg_isready -U telegram_user

# بررسی connection string در .env
echo $DATABASE_URL
```

### High memory usage:

```bash
# بررسی استفاده از منابع
docker stats

# کاهش workers در صورت نیاز
# در docker-compose.production.yml:
command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## 📋 Checklist نهایی

قبل از production:

- [ ] تمام پسوردها و secret keys تغییر یافته‌اند
- [ ] Firewall تنظیم شده
- [ ] SSL نصب شده (در صورت استفاده از دامنه)
- [ ] Backup خودکار تنظیم شده
- [ ] Monitoring راه‌اندازی شده
- [ ] Logs در حال ذخیره هستند
- [ ] سیستم با restart سرور خودکار بالا می‌آید
- [ ] Database migrations اجرا شده
- [ ] .env فایل در .gitignore است

---

## 🆘 پشتیبانی

در صورت بروز مشکل:

1. لاگ‌ها را بررسی کنید
2. Docker containers را restart کنید
3. به مستندات مراجعه کنید
4. از backup restore کنید

---

**آخرین به‌روزرسانی**: 2025-11-17
