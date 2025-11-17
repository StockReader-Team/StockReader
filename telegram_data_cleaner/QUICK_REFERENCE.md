# Quick Reference - خلاصه سریع فاز 1

## ✅ چیزهایی که آماده است

### 1. ساختار پروژه
- ✅ 35 فایل Python
- ✅ 5 مدل دیتابیس
- ✅ 16 تست (13 موفق)
- ✅ Docker services (PostgreSQL + Redis)

### 2. Models
```
Category ──┐
           ├── Channel ──── Message ──── Tag
           │                         └── MessageTag
           └── Category (parent)
```

### 3. Database
- **PostgreSQL 15**: http://localhost:8080 (Adminer)
- **Redis 7**: http://localhost:8081 (Redis Commander)
- **جداول**: 5 table با 12 index

### 4. API خارجی
- **URL**: http://103.75.197.239:3000/api/all-messages
- **وضعیت**: ✅ تست شد، کار می‌کنه
- **داده**: 25,089 پیام از 200+ کانال

## 🚀 دستورات مهم

### شروع سریع:
```bash
# 1. Start Docker
cd docker && docker-compose up -d

# 2. Activate poetry
poetry shell

# 3. Check setup
python scripts/check_setup.py

# 4. Run tests
pytest -v
```

### Development:
```bash
# فعال کردن env
poetry shell

# تست
pytest

# Migration جدید
alembic revision --autogenerate -m "description"
alembic upgrade head

# تست API
python scripts/test_api.py
```

### Docker:
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f postgres
docker-compose logs -f redis

# PostgreSQL shell
docker exec telegram_postgres psql -U telegram_user -d telegram_data

# Redis shell
docker exec telegram_redis redis-cli
```

## 📊 Configuration (.env)

```env
DATABASE_URL=postgresql+asyncpg://telegram_user:telegram_pass@localhost:5432/telegram_data
REDIS_URL=redis://localhost:6379/0
API_URL=http://103.75.197.239:3000/api/all-messages
API_TOKEN=telegramreader-api-token-2025
POLLING_INTERVAL=180
LOG_LEVEL=INFO
HISTORY_DAYS=15
```

## 🎯 آماده برای فاز 2

### کارهای بعدی:
1. ✅ Ingestion service (fetch از API)
2. ✅ Text processing (نرمال‌سازی فارسی)
3. ✅ Matching system (تگ‌گذاری)
4. ✅ REST API endpoints
5. ✅ Scheduling (هر 3 دقیقه)
6. ✅ Analytics

## 📝 فایل‌های مهم

- **PHASE1_SUMMARY.md**: خلاصه کامل فاز 1
- **README.md**: مستندات کامل
- **TESTING.md**: راهنمای تست
- **QUICK_REFERENCE.md**: این فایل

---

**همه چی آماده است! 🚀**
