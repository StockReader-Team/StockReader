# 🚀 راهنمای شروع سریع

## نصب و راه‌اندازی در 5 دقیقه

### پیش‌نیازها
```bash
- Python 3.11+
- PostgreSQL
- Redis (اختیاری)
```

### مرحله 1: نصب Dependencies
```bash
cd /path/to/telegram_data_cleaner
poetry install
```

### مرحله 2: تنظیم Environment Variables
```bash
cp .env.example .env
# ویرایش .env و تنظیم DATABASE_URL
```

### مرحله 3: اجرای Migrations
```bash
poetry run alembic upgrade head
```

### مرحله 4: اجرای سرور
```bash
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### مرحله 5: دسترسی به UI
```
http://localhost:8000
```

---

## صفحات اصلی

| صفحه | آدرس | توضیح |
|------|------|--------|
| لغت‌نامه | http://localhost:8000/ | مدیریت کلمات |
| داشبورد | http://localhost:8000/dashboard | داشبورد اصلی |
| تطابق‌ها | http://localhost:8000/matches | نتایج matching |
| آنالیتیکس | http://localhost:8000/analytics | آنالیتیکس کانال‌ها |
| API Docs | http://localhost:8000/docs | مستندات Swagger |

---

## اولین کارها

### 1. Import نمادهای بورسی
1. برو به http://localhost:8000/
2. کلیک روی "Import از CSV"
3. آپلود فایل symbols.csv
4. منتظر بمان تا import کامل شود

### 2. دریافت پیام‌ها
1. برو به صفحه اصلی
2. کلیک روی "دریافت پیام جدید"
3. تعداد پیام: 100
4. کلیک روی "شروع"

### 3. مشاهده تطابق‌ها
1. برو به http://localhost:8000/matches
2. فیلتر بر اساس کانال یا نماد
3. مشاهده پیام‌های match شده

### 4. مشاهده آنالیتیکس
1. برو به http://localhost:8000/analytics
2. انتخاب یک کانال
3. انتخاب بازه زمانی
4. مشاهده نمودارها و آمار

---

## دستورات مفید

### دریافت دستی پیام‌ها
```bash
curl -X POST "http://localhost:8000/api/ingestion/sync?limit=100"
```

### محاسبه دستی Analytics
```bash
curl -X POST "http://localhost:8000/api/analytics/compute-aggregates?hours_back=1&granularity=hourly"
```

### Export Excel
```bash
curl "http://localhost:8000/api/analytics/channels/{channel_id}/export/excel?days=7" -o analytics.xlsx
```

### چک کردن وضعیت سیستم
```bash
curl "http://localhost:8000/api/health"
```

---

## مستندات کامل

- **خلاصه پروژه**: [docs/PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **راهنمای API**: [docs/API_GUIDE.md](API_GUIDE.md)
- **راهنمای Analytics**: [docs/ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md)
- **یادداشت‌های جلسات**: [docs/SESSION_NOTES.md](SESSION_NOTES.md)

---

## پشتیبانی

در صورت بروز مشکل:
1. لاگ‌ها را چک کنید: `logs/app.log`
2. وضعیت scheduler را چک کنید: `GET /api/scheduler/status`
3. دیتابیس را چک کنید: `SELECT * FROM channels LIMIT 5;`

---

**تاریخ**: 2025-11-16
**نسخه**: 0.2.0
