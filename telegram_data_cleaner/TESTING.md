# راهنمای تست فاز 1

این راهنما مراحل کامل تست فاز 1 پروژه را شامل می‌شود.

## مرحله 1️⃣: نصب Poetry

اگر Poetry نصب نیست:

```bash
# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# یا با brew در macOS
brew install poetry
```

بعد از نصب، بستن و باز کردن ترمینال.

## مرحله 2️⃣: نصب Dependencies

```bash
cd telegram_data_cleaner

# نصب تمام dependencies
poetry install

# چک کردن نصب
poetry show
```

## مرحله 3️⃣: راه‌اندازی Docker Services

```bash
# رفتن به پوشه docker
cd docker

# راه‌اندازی PostgreSQL و Redis
docker-compose up -d

# چک کردن وضعیت (باید 4 container اجرا شوند)
docker-compose ps
```

خروجی باید شبیه این باشد:
```
NAME                    STATUS
telegram_postgres       Up
telegram_redis          Up
telegram_adminer        Up
telegram_redis_commander Up
```

چک کردن logs:
```bash
# مشاهده logs PostgreSQL
docker-compose logs postgres

# مشاهده logs Redis
docker-compose logs redis
```

## مرحله 4️⃣: تنظیم فایل .env

```bash
# برگشت به root پروژه
cd ..

# کپی کردن .env.example
cp .env.example .env
```

فایل `.env` را ویرایش کن (همین مقادیر پیش‌فرض کافی است):
```env
DATABASE_URL=postgresql+asyncpg://telegram_user:telegram_pass@localhost:5432/telegram_data
REDIS_URL=redis://localhost:6379/0
API_URL=http://103.75.197.239:3000/api/all-messages
API_TOKEN=telegramreader-api-token-2025
POLLING_INTERVAL=180
LOG_LEVEL=INFO
HISTORY_DAYS=15
```

## مرحله 5️⃣: اجرای Check Setup Script

این اسکریپت تمام چیزها را چک می‌کند:

```bash
# فعال کردن virtual environment
poetry shell

# اجرای check script
python scripts/check_setup.py
```

اگر همه چیز OK باشد، خروجی شبیه این است:
```
✓ PostgreSQL Connection
✓ Redis Connection
✓ Model Imports
✓ Configuration Loading
✓ All 6 checks passed! System is ready.
```

### اگر خطا دریافت کردی:

**خطای PostgreSQL:**
```bash
# چک کردن container
docker ps | grep postgres

# ریستارت PostgreSQL
cd docker && docker-compose restart postgres
```

**خطای Redis:**
```bash
# چک کردن container
docker ps | grep redis

# ریستارت Redis
cd docker && docker-compose restart redis
```

## مرحله 6️⃣: راه‌اندازی Database با Alembic

```bash
# باید در poetry shell باشی
poetry shell

# ساخت اولین migration
alembic revision --autogenerate -m "Initial tables"

# اعمال migration
alembic upgrade head

# چک کردن revision فعلی
alembic current
```

## مرحله 7️⃣: اجرای Init Database (اختیاری)

برای ساخت داده‌های نمونه:

```bash
python scripts/init_db.py
```

این اسکریپت:
- ✓ جداول را می‌سازد
- ✓ 5 دسته‌بندی اضافه می‌کند
- ✓ 5 تگ نمونه می‌سازد

## مرحله 8️⃣: اجرای تست‌های واحد

```bash
# اجرای تمام تست‌ها
pytest

# اجرای با verbose
pytest -v

# اجرای با coverage
pytest --cov=src --cov-report=term-missing

# اجرای تست‌های خاص
pytest tests/test_database.py -v
pytest tests/test_models.py -v
```

### خروجی موفق:
```
tests/test_database.py::test_engine_initialization PASSED
tests/test_database.py::test_session_creation PASSED
tests/test_database.py::test_database_connection PASSED
tests/test_models.py::test_create_category PASSED
tests/test_models.py::test_create_channel PASSED
tests/test_models.py::test_create_message PASSED
...
====== 18 passed in 2.34s ======
```

## مرحله 9️⃣: دسترسی به Web Interfaces

### Adminer (PostgreSQL GUI):
1. باز کن: http://localhost:8080
2. اطلاعات ورود:
   - System: `PostgreSQL`
   - Server: `postgres`
   - Username: `telegram_user`
   - Password: `telegram_pass`
   - Database: `telegram_data`

3. می‌تونی جداول رو ببینی:
   - categories
   - channels
   - messages
   - tags
   - message_tags

### Redis Commander:
باز کن: http://localhost:8081

## مرحله 🔟: تست دستی با PostgreSQL

```bash
# اتصال به PostgreSQL
docker exec -it telegram_postgres psql -U telegram_user -d telegram_data

# لیست جداول
\dt

# تعداد رکوردهای هر جدول
SELECT 'categories' as table, COUNT(*) FROM categories
UNION ALL
SELECT 'channels', COUNT(*) FROM channels
UNION ALL
SELECT 'tags', COUNT(*) FROM tags;

# خروج
\q
```

## مرحله 1️⃣1️⃣: تست دستی با Redis

```bash
# اتصال به Redis
docker exec -it telegram_redis redis-cli

# تست
PING
# باید PONG برگردونه

# خروج
exit
```

## ✅ Checklist تست فاز 1

- [ ] Poetry نصب شد
- [ ] Dependencies نصب شد (`poetry install`)
- [ ] Docker containers اجرا شدند (`docker-compose ps`)
- [ ] فایل .env ساخته شد
- [ ] Check setup موفق بود (`python scripts/check_setup.py`)
- [ ] Alembic migration اجرا شد (`alembic upgrade head`)
- [ ] Init database اجرا شد (اختیاری)
- [ ] تست‌ها موفق بودند (`pytest`)
- [ ] Adminer کار می‌کند (http://localhost:8080)
- [ ] Redis Commander کار می‌کند (http://localhost:8081)
- [ ] جداول در database ساخته شدند

## 🐛 مشکلات رایج

### 1. خطا: poetry: command not found
```bash
# نصب poetry
curl -sSL https://install.python-poetry.org | python3 -

# اضافه کردن به PATH
export PATH="$HOME/.local/bin:$PATH"
```

### 2. خطا: Cannot connect to Docker daemon
```bash
# راه‌اندازی Docker Desktop
# یا start کردن Docker service
```

### 3. خطا: Port 5432 already in use
```bash
# بستن PostgreSQL لوکال
brew services stop postgresql
# یا تغییر port در docker-compose.yml
```

### 4. خطا: ModuleNotFoundError
```bash
# اطمینان از فعال بودن poetry shell
poetry shell

# نصب مجدد
poetry install --no-cache
```

### 5. تست‌ها fail می‌شوند
```bash
# ساخت test database
docker exec -it telegram_postgres psql -U telegram_user -c "CREATE DATABASE telegram_data_test;"

# اجرای مجدد تست‌ها
pytest -v
```

## 📊 خروجی مورد انتظار

### Check Setup (موفق):
```
🔍 System Setup Verification

============================================================
  File Structure
============================================================
✓ src/config.py
✓ src/database.py
✓ pyproject.toml
...

============================================================
  PostgreSQL
============================================================
✓ PostgreSQL Connection
✓ Database Size

============================================================
  Redis
============================================================
✓ Redis Connection
✓ Redis Memory Usage

✓ All 6 checks passed! System is ready.
```

### Pytest (موفق):
```
tests/test_database.py ........                          [ 44%]
tests/test_models.py ..........                          [100%]

====== 18 passed in 2.34s ======
```

## 🎉 اگر همه مراحل OK بود

پروژه فاز 1 کاملاً آماده است! می‌تونی:
1. ✅ با Adminer دیتابیس رو مدیریت کنی
2. ✅ با Redis Commander cache رو ببینی
3. ✅ تست‌ها رو اجرا کنی
4. ✅ Migration جدید بسازی
5. ✅ شروع به توسعه فاز 2 کنی

## دستورات مفید روزانه

```bash
# Start services
cd docker && docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Run tests
poetry run pytest

# Activate shell
poetry shell

# Check setup
python scripts/check_setup.py
```
