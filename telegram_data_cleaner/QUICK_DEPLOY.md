# ⚡ راهنمای سریع Deploy

این راهنما برای deploy سریع پروژه روی سرور است.

---

## 🚀 Deploy در 5 دقیقه

### 1️⃣ نصب Docker (اگر نصب نیست)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2️⃣ کلون پروژه

```bash
cd /opt
sudo git clone <YOUR_REPO> telegram_data_cleaner
cd telegram_data_cleaner
sudo chown -R $USER:$USER .
```

### 3️⃣ تنظیمات محیطی

```bash
# کپی فایل نمونه
cp .env.production.example .env

# ویرایش (⚠️ حتماً SECRET_KEY و DB_PASSWORD را تغییر دهید)
nano .env
```

### 4️⃣ اجرا!

```bash
# Build و اجرا
docker-compose -f docker-compose.production.yml up -d --build

# مشاهده logs
docker-compose -f docker-compose.production.yml logs -f

# اجرای migrations
docker-compose -f docker-compose.production.yml exec app poetry run alembic upgrade head
```

### 5️⃣ چک کردن

```bash
# وضعیت containers
docker-compose -f docker-compose.production.yml ps

# تست API
curl http://localhost:8000/api/health

# مشاهده در مرورگر
# http://YOUR_SERVER_IP:8000
```

---

## 🔄 دستورات مفید

```bash
# Restart
docker-compose -f docker-compose.production.yml restart

# Stop
docker-compose -f docker-compose.production.yml down

# View logs
docker-compose -f docker-compose.production.yml logs -f app

# Rebuild
docker-compose -f docker-compose.production.yml up -d --build

# Execute command در container
docker-compose -f docker-compose.production.yml exec app <command>
```

---

## 📦 Backup

```bash
# اجرای backup دستی
chmod +x scripts/backup.sh
./scripts/backup.sh

# Backup خودکار (روزانه ساعت 2 صبح)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/telegram_data_cleaner/scripts/backup.sh") | crontab -
```

---

## 🔄 Update

```bash
cd /opt/telegram_data_cleaner
git pull
docker-compose -f docker-compose.production.yml up -d --build
docker-compose -f docker-compose.production.yml exec app poetry run alembic upgrade head
```

---

## 🆘 مشکلات رایج

### Container بالا نمی‌آید:
```bash
docker-compose -f docker-compose.production.yml logs app
docker-compose -f docker-compose.production.yml restart
```

### Port اشغال است:
```bash
# تغییر API_PORT در .env
API_PORT=8001

# یا kill process روی پورت 8000
sudo lsof -ti:8000 | xargs kill -9
```

### Out of Memory:
```bash
# کاهش workers
# در docker-compose.production.yml:
# command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## 📚 مستندات کامل

برای جزئیات بیشتر: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

---

**نکته امنیتی**:
- حتماً `SECRET_KEY` و `DB_PASSWORD` را تغییر دهید
- Firewall را تنظیم کنید
- فقط پورت‌های لازم را باز کنید
