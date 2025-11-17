# فهرست کامل فایل‌های پروژه

## 📚 مستندات (5 فایل)

1. **README.md** - مستندات کامل پروژه
2. **TESTING.md** - راهنمای تست فاز 1
3. **PHASE1_SUMMARY.md** - خلاصه کامل فاز 1 (جامع)
4. **QUICK_REFERENCE.md** - مرجع سریع (یک صفحه)
5. **DATABASE_SCHEMA.md** - ساختار دیتابیس و ERD
6. **PHASE1_CHECKLIST.txt** - چک‌لیست ساده
7. **FILES_INDEX.md** - این فایل

## ⚙️ Configuration (4 فایل)

1. **pyproject.toml** - Poetry dependencies
2. **.env.example** - Environment variables template
3. **.env** - Local configuration
4. **.gitignore** - Git ignore rules

## 🗄️ Database & Migrations (3 فایل)

1. **alembic.ini** - Alembic configuration
2. **alembic/env.py** - Async migration environment
3. **alembic/script.py.mako** - Migration template
4. **alembic/README** - Alembic usage guide
5. **alembic/versions/2025_11_15_*.py** - Initial migration

## 🐳 Docker (1 فایل)

1. **docker/docker-compose.yml** - PostgreSQL + Redis services

## 🔧 Core Application (10 فایل)

### Configuration & Database:
1. **src/config.py** - Pydantic settings
2. **src/database.py** - Async DB connection
3. **src/core/logging.py** - Logging with rotation

### Models (6 فایل):
4. **src/models/base.py** - Base model with UUID
5. **src/models/category.py** - Category model
6. **src/models/channel.py** - Channel model
7. **src/models/message.py** - Message model
8. **src/models/tag.py** - Tag model
9. **src/models/message_tag.py** - MessageTag association
10. **src/models/__init__.py** - Models export

### Empty modules (آماده فاز 2):
- **src/api/__init__.py**
- **src/core/ingestion/__init__.py**
- **src/core/processing/__init__.py**
- **src/core/matching/__init__.py**
- **src/core/analytics/__init__.py**
- **src/schemas/__init__.py**
- **src/services/__init__.py**

## 🧪 Tests (3 فایل)

1. **tests/conftest.py** - Test fixtures
2. **tests/test_database.py** - Database tests (8 tests)
3. **tests/test_models.py** - Model tests (8 tests)
4. **tests/__init__.py** - Test package

## 📜 Scripts (3 فایل)

1. **scripts/init_db.py** - Initialize database with seed data
2. **scripts/check_setup.py** - System health check
3. **scripts/test_api.py** - Test external API

## 📊 آمار کلی

- **Python Files**: 24 فایل
- **Config Files**: 4 فایل
- **Documentation**: 7 فایل
- **Total Files**: 35+ فایل

---

## 🎯 استفاده از فایل‌ها

### برای شروع پروژه:
```
README.md → TESTING.md → check_setup.py
```

### برای فهم سریع:
```
QUICK_REFERENCE.md → PHASE1_CHECKLIST.txt
```

### برای جزئیات کامل:
```
PHASE1_SUMMARY.md → DATABASE_SCHEMA.md
```

### برای توسعه:
```
pyproject.toml → src/models/ → alembic/
```

---

تمام فایل‌ها در: `/Users/mrash/Desktop/StockReader/project/telegram_data_cleaner/`
