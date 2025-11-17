# Telegram Data Cleaner

سیستم تحلیل و تمیز‌سازی داده کانال‌های تلگرام با پردازش Real-time

## 📋 توضیحات پروژه

این پروژه یک سیستم جامع برای دریافت، پردازش و تحلیل داده‌های کانال‌های تلگرام است که شامل موارد زیر می‌باشد:

- **دریافت خودکار داده**: Polling هر 3-4 دقیقه از API
- **پردازش Real-time**: پردازش و نرمال‌سازی متن‌های فارسی
- **مدیریت حجم**: پشتیبانی از 200-250 کانال و ~4500 پیام در روز
- **نگهداری تاریخچه**: ذخیره 15 روز history
- **Match با لغت‌نامه**: تگ‌گذاری خودکار بر اساس شرایط
- **REST API**: ارائه داده به سیستم‌های دیگر

## 🛠 Stack فنی

- **Python 3.11+**: زبان برنامه‌نویسی
- **Poetry**: مدیریت dependency
- **PostgreSQL 15**: دیتابیس اصلی (با async support)
- **SQLAlchemy 2.0**: ORM با async
- **FastAPI**: REST API framework
- **APScheduler**: زمان‌بندی polling
- **Pandas**: پردازش داده
- **Hazm**: پردازش متن فارسی
- **Redis 7**: Caching
- **Alembic**: Database migrations

## 📁 ساختار پروژه

```
telegram_data_cleaner/
├── src/
│   ├── api/                    # FastAPI endpoints
│   ├── core/
│   │   ├── ingestion/         # fetch از API
│   │   ├── processing/        # پردازش و تمیز‌سازی
│   │   ├── matching/          # match با لغت‌نامه
│   │   ├── analytics/         # تحلیل و آمار
│   │   └── logging.py         # Logging setup
│   ├── models/                # SQLAlchemy models
│   ├── services/              # Business logic
│   ├── schemas/               # Pydantic schemas
│   ├── config.py              # Configuration
│   └── database.py            # DB connection
├── tests/                     # Test files
├── scripts/                   # Utility scripts
├── alembic/                   # Database migrations
├── docker/                    # Docker compose
├── pyproject.toml            # Poetry dependencies
├── alembic.ini               # Alembic config
└── .env.example              # Environment variables template
```

## 🚀 نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.11 یا بالاتر
- Poetry
- Docker و Docker Compose (برای PostgreSQL و Redis)

### مراحل نصب

1. **کلون کردن پروژه**
   ```bash
   cd telegram_data_cleaner
   ```

2. **نصب Poetry** (اگر نصب نیست)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **نصب Dependencies**
   ```bash
   poetry install
   ```

4. **ایجاد فایل Environment**
   ```bash
   cp .env.example .env
   ```

   سپس `.env` را ویرایش کنید و مقادیر مناسب را وارد کنید.

5. **راه‌اندازی Docker Services**
   ```bash
   cd docker
   docker-compose up -d
   ```

6. **چک کردن وضعیت Services**
   ```bash
   docker-compose ps
   ```

## 🗄️ راه‌اندازی Database

### 1. اجرای Migrations

```bash
# فعال‌سازی virtual environment
poetry shell

# ساخت اولین migration
alembic revision --autogenerate -m "Initial migration"

# اعمال migrations
alembic upgrade head
```

### 2. Initial Setup (اختیاری)

برای ساخت جداول و داده‌های اولیه:

```bash
python scripts/init_db.py
```

این اسکریپت:
- تمام جداول را می‌سازد
- دسته‌بندی‌های پیش‌فرض اضافه می‌کند
- تگ‌های نمونه ایجاد می‌کند

### 3. چک کردن Setup

برای اطمینان از صحت نصب:

```bash
python scripts/check_setup.py
```

این اسکریپت موارد زیر را چک می‌کند:
- ✓ اتصال PostgreSQL
- ✓ اتصال Redis
- ✓ Import مدل‌ها
- ✓ Configuration
- ✓ Alembic migrations

## 🧪 اجرای تست‌ها

### تست تمام پروژه

```bash
poetry run pytest
```

### تست با Coverage Report

```bash
poetry run pytest --cov=src --cov-report=html
```

گزارش HTML در `htmlcov/index.html` ایجاد می‌شود.

### تست فایل خاص

```bash
poetry run pytest tests/test_database.py
poetry run pytest tests/test_models.py
```

### تست با حالت Verbose

```bash
poetry run pytest -v
```

## 📊 مدل‌های Database

### Channel
کانال‌های تلگرام را نگهداری می‌کند:
- `telegram_id`: شناسه یکتا تلگرام
- `name`: نام کانال
- `username`: نام کاربری کانال
- `category_id`: دسته‌بندی
- `is_active`: فعال/غیرفعال
- `last_sync`: آخرین به‌روزرسانی

### Category
دسته‌بندی کانال‌ها با ساختار سلسله‌مراتبی:
- `name`: نام دسته
- `parent_id`: دسته والد
- `description`: توضیحات

### Message
پیام‌های دریافتی از کانال‌ها:
- `telegram_message_id`: ID پیام در تلگرام
- `channel_id`: کانال مربوطه
- `text`: متن اصلی
- `text_normalized`: متن نرمال‌شده
- `date`: تاریخ ارسال
- `views`: تعداد بازدید
- `forwards`: تعداد forward
- `metadata`: اطلاعات اضافی (JSON)

### Tag
تگ‌ها برای دسته‌بندی پیام‌ها:
- `name`: نام تگ
- `tag_type`: نوع تگ (CHARACTER_COUNT, WORD_COUNT, CUSTOM)
- `condition`: شرایط match (JSON)
- `description`: توضیحات
- `is_active`: فعال/غیرفعال

### MessageTag
رابطه many-to-many بین Message و Tag:
- `message_id`: شناسه پیام
- `tag_id`: شناسه تگ
- `matched_at`: زمان match

## 🔧 دستورات مفید

### Alembic Commands

```bash
# ساخت migration جدید
alembic revision --autogenerate -m "توضیحات تغییرات"

# اعمال migrations
alembic upgrade head

# برگشت به migration قبلی
alembic downgrade -1

# مشاهده وضعیت فعلی
alembic current

# مشاهده تاریخچه
alembic history
```

### Docker Commands

```bash
# راه‌اندازی services
docker-compose up -d

# مشاهده logs
docker-compose logs -f

# توقف services
docker-compose down

# توقف و حذف volumes
docker-compose down -v

# ریستارت یک service خاص
docker-compose restart postgres
docker-compose restart redis
```

### Database Management

```bash
# دسترسی به PostgreSQL shell
docker exec -it telegram_postgres psql -U telegram_user -d telegram_data

# دسترسی به Redis CLI
docker exec -it telegram_redis redis-cli

# Backup database
docker exec telegram_postgres pg_dump -U telegram_user telegram_data > backup.sql

# Restore database
cat backup.sql | docker exec -i telegram_postgres psql -U telegram_user -d telegram_data
```

## 🌐 Web Interfaces

بعد از راه‌اندازی Docker، به آدرس‌های زیر دسترسی دارید:

- **Adminer** (PostgreSQL GUI): http://localhost:8080
  - Server: `postgres`
  - Username: `telegram_user`
  - Password: `telegram_pass`
  - Database: `telegram_data`

- **Redis Commander**: http://localhost:8081

## 📝 Configuration

تنظیمات اصلی در فایل `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/telegram_data
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# API
API_URL=http://103.75.197.239:3000/api/all-messages
API_TOKEN=telegramreader-api-token-2025

# Polling
POLLING_INTERVAL=180  # 3 minutes
BATCH_SIZE=100

# Application
LOG_LEVEL=INFO
HISTORY_DAYS=15
ENVIRONMENT=development
```

## 🐛 عیب‌یابی

### مشکل اتصال به Database

```bash
# چک کردن وضعیت PostgreSQL
docker-compose ps postgres

# مشاهده logs
docker-compose logs postgres

# تست اتصال
docker exec telegram_postgres pg_isready -U telegram_user
```

### مشکل اتصال به Redis

```bash
# چک کردن وضعیت Redis
docker-compose ps redis

# تست اتصال
docker exec telegram_redis redis-cli ping
```

### خطای Import

```bash
# اطمینان از فعال بودن virtual environment
poetry shell

# نصب مجدد dependencies
poetry install --no-cache
```

## 📚 مراحل بعدی (فاز 2)

- [ ] پیاده‌سازی API endpoints با FastAPI
- [ ] سیستم ingestion از API تلگرام
- [ ] پردازش و نرمال‌سازی متن با Hazm
- [ ] سیستم matching با لغت‌نامه
- [ ] پیاده‌سازی caching با Redis
- [ ] سیستم Analytics و آمارگیری
- [ ] مستندات API با Swagger
- [ ] CI/CD Pipeline
- [ ] Monitoring و Alerting

## 🤝 مشارکت

برای مشارکت در پروژه:

1. Fork کنید
2. Feature branch بسازید (`git checkout -b feature/AmazingFeature`)
3. تغییرات را commit کنید (`git commit -m 'Add some AmazingFeature'`)
4. Push به branch (`git push origin feature/AmazingFeature`)
5. Pull Request باز کنید

## 📄 لایسنس

این پروژه تحت لایسنس MIT منتشر شده است.

## 📞 تماس

برای سوالات و پیشنهادات، Issue باز کنید.

---

**نکته**: این پروژه در حال توسعه است و فاز اول (Infrastructure) تکمیل شده است.
