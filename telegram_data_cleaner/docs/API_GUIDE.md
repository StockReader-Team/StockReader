# راهنمای کامل API

## 📋 فهرست

1. [Ingestion API](#ingestion-api)
2. [Dictionary API](#dictionary-api)
3. [Analytics API](#analytics-api)
4. [Scheduler API](#scheduler-api)

---

## 🔌 Base URL

```
http://localhost:8000/api
```

---

## 1️⃣ Ingestion API

### 1.1 دریافت دستی پیام‌ها

**Endpoint**: `POST /api/ingestion/sync`

**توضیح**: دریافت دسته‌ای پیام‌های جدید از API خارجی

**Parameters**:
```json
{
  "limit": 100,        // تعداد پیام (پیش‌فرض: 100)
  "offset": 0,         // شروع از کدام پیام (پیش‌فرض: 0)
  "background": false  // اجرا در پس‌زمینه؟
}
```

**مثال cURL**:
```bash
curl -X POST "http://localhost:8000/api/ingestion/sync?limit=50&offset=0" \
  -H "Content-Type: application/json"
```

**پاسخ**:
```json
{
  "status": "completed",
  "stats": {
    "messages_inserted": 45,
    "messages_updated": 5,
    "messages_skipped": 0,
    "errors": 0,
    "duration_seconds": 2.5,
    "batch_size": 50
  }
}
```

---

### 1.2 دریافت لیست کانال‌ها

**Endpoint**: `GET /api/ingestion/channels`

**توضیح**: لیست تمام کانال‌های ذخیره شده

**مثال**:
```bash
curl "http://localhost:8000/api/ingestion/channels"
```

**پاسخ**:
```json
{
  "total": 150,
  "channels": [
    {
      "id": "uuid-here",
      "telegram_id": "1234567890",
      "name": "کانال بورس",
      "username": "bourse_channel",
      "is_active": true,
      "last_sync": "2025-11-16T10:30:00Z",
      "category": {
        "id": "cat-uuid",
        "name": "بورس"
      }
    }
  ]
}
```

---

### 1.3 پاک‌سازی پیام‌های قدیمی

**Endpoint**: `DELETE /api/ingestion/cleanup`

**توضیح**: حذف پیام‌های قدیمی‌تر از N روز

**Parameters**:
```
?days=7  // حذف پیام‌های قدیمی‌تر از 7 روز
```

**مثال**:
```bash
curl -X DELETE "http://localhost:8000/api/ingestion/cleanup?days=7"
```

**پاسخ**:
```json
{
  "status": "completed",
  "deleted_count": 1500,
  "cutoff_date": "2025-11-09T00:00:00Z"
}
```

---

## 2️⃣ Dictionary API

### 2.1 لیست دسته‌بندی‌ها

**Endpoint**: `GET /api/dictionary/categories`

**مثال**:
```bash
curl "http://localhost:8000/api/dictionary/categories"
```

**پاسخ**:
```json
{
  "total": 3,
  "categories": [
    {
      "id": "uuid",
      "name": "نمادها",
      "description": "نمادهای بورسی",
      "word_count": 2918,
      "created_at": "2025-11-15T10:00:00Z"
    }
  ]
}
```

---

### 2.2 ایجاد دسته‌بندی جدید

**Endpoint**: `POST /api/dictionary/categories`

**Body**:
```json
{
  "name": "صنایع",
  "description": "نام صنایع مختلف"
}
```

**مثال**:
```bash
curl -X POST "http://localhost:8000/api/dictionary/categories" \
  -H "Content-Type: application/json" \
  -d '{"name": "صنایع", "description": "نام صنایع مختلف"}'
```

---

### 2.3 لیست کلمات

**Endpoint**: `GET /api/dictionary/words`

**Parameters**:
- `category_id` (اختیاری): فیلتر بر اساس دسته
- `search` (اختیاری): جستجو در کلمات
- `is_active` (اختیاری): فقط فعال یا غیرفعال
- `skip`, `limit`: صفحه‌بندی

**مثال**:
```bash
# تمام نمادها
curl "http://localhost:8000/api/dictionary/words?category_id=uuid-here&limit=10"

# جستجو
curl "http://localhost:8000/api/dictionary/words?search=فولاد"
```

**پاسخ**:
```json
{
  "total": 2918,
  "words": [
    {
      "id": "uuid",
      "word": "فولاد",
      "normalized_word": "فولاد",
      "is_active": true,
      "category": {
        "id": "cat-uuid",
        "name": "نمادها"
      },
      "extra_data": {
        "symbol_name": "فولاد",
        "company_name": "فولاد مبارکه اصفهان",
        "industry_name": "فلزات اساسی",
        "keywords": ["#فولاد", "فولادمبارکه"]
      }
    }
  ]
}
```

---

### 2.4 اضافه کردن کلمه جدید

**Endpoint**: `POST /api/dictionary/words`

**Body**:
```json
{
  "word": "فملی",
  "category_id": "uuid-of-category",
  "is_active": true,
  "extra_data": {
    "symbol_name": "فملی",
    "company_name": "ملی صنایع مس ایران",
    "industry_name": "فلزات اساسی",
    "keywords": ["#فملی", "مس"]
  }
}
```

**مثال**:
```bash
curl -X POST "http://localhost:8000/api/dictionary/words" \
  -H "Content-Type: application/json" \
  -d @word.json
```

---

### 2.5 ویرایش کلمه

**Endpoint**: `PATCH /api/dictionary/words/{word_id}`

**Body** (همه فیلدها اختیاری):
```json
{
  "word": "فملی",
  "is_active": true,
  "extra_data": {
    "keywords": ["#فملی", "مس", "صنایع مس"]
  }
}
```

**مثال**:
```bash
curl -X PATCH "http://localhost:8000/api/dictionary/words/uuid-here" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

---

### 2.6 حذف کلمه

**Endpoint**: `DELETE /api/dictionary/words/{word_id}`

**مثال**:
```bash
curl -X DELETE "http://localhost:8000/api/dictionary/words/uuid-here"
```

---

### 2.7 Import از CSV

**Endpoint**: `POST /api/dictionary/import/csv`

**توضیح**: Import کردن دسته‌ای کلمات از فایل CSV

**Form Data**:
- `file`: فایل CSV
- `category_id`: UUID دسته‌بندی

**فرمت CSV**:
```csv
symbol_name,company_name,industry_name
فولاد,فولاد مبارکه اصفهان,فلزات اساسی
فملی,ملی صنایع مس ایران,فلزات اساسی
```

**مثال**:
```bash
curl -X POST "http://localhost:8000/api/dictionary/import/csv" \
  -F "file=@symbols.csv" \
  -F "category_id=uuid-here"
```

**پاسخ**:
```json
{
  "status": "success",
  "imported_count": 2918,
  "skipped_count": 0,
  "errors": []
}
```

---

## 3️⃣ Analytics API ⭐

### 3.1 آمار کانال

**Endpoint**: `GET /api/analytics/channels/{channel_id}/stats`

**توضیح**: دریافت آمار یک کانال برای بازه زمانی مشخص

**Parameters**:
- `time_range`: یکی از `5min`, `30min`, `1hour`, `today`, `7days`, `30days`

**مثال**:
```bash
curl "http://localhost:8000/api/analytics/channels/uuid-here/stats?time_range=30min"
```

**پاسخ برای بازه‌های کوتاه (5min, 30min, 1hour)**:
```json
{
  "channel_id": "uuid",
  "time_range_minutes": 30,
  "message_count": 45,
  "match_count": 12,
  "top_symbols": [
    {"id": "uuid", "word": "فولاد", "count": 8},
    {"id": "uuid", "word": "فملی", "count": 4}
  ],
  "top_industries": [
    {"name": "فلزات اساسی", "count": 10},
    {"name": "خودرو", "count": 2}
  ],
  "top_categories": [
    {"id": "uuid", "name": "نمادها", "count": 12}
  ],
  "timeline": [
    {"timestamp": "2025-11-16T10:00:00Z", "message_count": 15},
    {"timestamp": "2025-11-16T10:05:00Z", "message_count": 12},
    {"timestamp": "2025-11-16T10:10:00Z", "message_count": 18}
  ]
}
```

**پاسخ برای بازه‌های طولانی (7days, 30days)**:
```json
{
  "channel_id": "uuid",
  "days": 7,
  "total_messages": 5000,
  "total_matches": 1500,
  "categories": [
    {"name": "نمادها", "count": 1200, "percentage": 80.0},
    {"name": "صنایع", "count": 300, "percentage": 20.0}
  ],
  "primary_focus": "نمادها",
  "focus_percentage": 80.0
}
```

---

### 3.2 پروفایل محتوایی کانال

**Endpoint**: `GET /api/analytics/channels/{channel_id}/content-profile`

**توضیح**: تحلیل اینکه کانال روی چه موضوعاتی تمرکز دارد

**Parameters**:
- `days`: تعداد روز (1-90، پیش‌فرض: 7)

**مثال**:
```bash
curl "http://localhost:8000/api/analytics/channels/uuid-here/content-profile?days=7"
```

**پاسخ**:
```json
{
  "channel_id": "uuid",
  "days": 7,
  "total_messages": 5000,
  "total_matches": 1500,
  "categories": [
    {
      "name": "نمادها",
      "count": 1200,
      "percentage": 80.0
    },
    {
      "name": "صنایع",
      "count": 300,
      "percentage": 20.0
    }
  ],
  "primary_focus": "نمادها",
  "focus_percentage": 80.0
}
```

---

### 3.3 مقایسه کانال‌ها

**Endpoint**: `GET /api/analytics/channels/compare`

**توضیح**: مقایسه همزمان تا 10 کانال

**Parameters**:
- `channel_ids`: لیست UUID ها با کاما جدا شده
- `days`: تعداد روز

**مثال**:
```bash
curl "http://localhost:8000/api/analytics/channels/compare?channel_ids=uuid1,uuid2,uuid3&days=7"
```

**پاسخ**:
```json
{
  "days": 7,
  "channels": [
    {
      "channel_id": "uuid1",
      "total_messages": 5000,
      "total_matches": 1500,
      "primary_focus": "نمادها",
      "focus_percentage": 80.0,
      "categories": [...]
    },
    {
      "channel_id": "uuid2",
      "total_messages": 3000,
      "total_matches": 900,
      "primary_focus": "اخبار",
      "focus_percentage": 65.0,
      "categories": [...]
    }
  ]
}
```

---

### 3.4 خروجی Excel

**Endpoint**: `GET /api/analytics/channels/{channel_id}/export/excel`

**توضیح**: دانلود گزارش کامل به صورت فایل Excel

**Parameters**:
- `days`: تعداد روز (1-90، پیش‌فرض: 7)

**مثال**:
```bash
# دانلود مستقیم
curl "http://localhost:8000/api/analytics/channels/uuid-here/export/excel?days=7" \
  -o analytics.xlsx

# یا باز کردن در مرورگر
open "http://localhost:8000/api/analytics/channels/uuid-here/export/excel?days=7"
```

**ساختار فایل Excel**:
- **Sheet 1 - Overview**: خلاصه آمار
- **Sheet 2 - Categories**: جدول دسته‌بندی‌ها
- **Sheet 3 - Top Symbols**: 10 نماد برتر
- **Sheet 4 - Top Industries**: 10 صنعت برتر

---

### 3.5 محاسبه دستی Aggregates

**Endpoint**: `POST /api/analytics/compute-aggregates`

**توضیح**: اجرای دستی محاسبه aggregates (معمولاً خودکار است)

**Parameters**:
- `hours_back`: چند ساعت عقب برگردیم (1-24)
- `granularity`: `hourly` یا `daily`

**مثال**:
```bash
curl -X POST "http://localhost:8000/api/analytics/compute-aggregates?hours_back=2&granularity=hourly"
```

**پاسخ**:
```json
{
  "status": "success",
  "records_created": 150,
  "start_time": "2025-11-16T08:00:00Z",
  "end_time": "2025-11-16T10:00:00Z",
  "granularity": "hourly"
}
```

---

## 4️⃣ Scheduler API

### 4.1 وضعیت Scheduler

**Endpoint**: `GET /api/scheduler/status`

**مثال**:
```bash
curl "http://localhost:8000/api/scheduler/status"
```

**پاسخ**:
```json
{
  "is_running": true,
  "last_sync": "2025-11-16T10:30:00Z",
  "last_success": "2025-11-16T10:30:00Z",
  "last_error": null,
  "next_scheduled": "2025-11-16T10:33:00Z",
  "last_stats": {
    "messages_inserted": 15,
    "messages_updated": 5,
    "duration_seconds": 1.2
  }
}
```

---

### 4.2 لیست Job ها

**Endpoint**: `GET /api/scheduler/jobs`

**مثال**:
```bash
curl "http://localhost:8000/api/scheduler/jobs"
```

**پاسخ**:
```json
{
  "jobs": [
    {
      "id": "ingestion_job",
      "name": "Periodic Message Ingestion",
      "next_run_time": "2025-11-16T10:33:00Z",
      "trigger": "interval[0:03:00]"
    },
    {
      "id": "analytics_aggregation_job",
      "name": "Analytics Aggregation",
      "next_run_time": "2025-11-16T10:35:00Z",
      "trigger": "interval[0:05:00]"
    },
    {
      "id": "cleanup_job",
      "name": "Daily Cleanup",
      "next_run_time": "2025-11-17T02:00:00Z",
      "trigger": "cron[day='*', hour='2', minute='0']"
    }
  ]
}
```

---

### 4.3 اجرای دستی Ingestion

**Endpoint**: `POST /api/scheduler/trigger-ingestion`

**مثال**:
```bash
curl -X POST "http://localhost:8000/api/scheduler/trigger-ingestion"
```

---

## 🔐 Authentication (آینده)

در نسخه فعلی، API ها احتیاج به authentication ندارند. برای production باید:

1. JWT Token authentication
2. API Key
3. Rate limiting
4. IP whitelisting

اضافه شود.

---

## 📊 Response Codes

| Code | معنی | توضیح |
|------|------|--------|
| 200 | OK | موفق |
| 201 | Created | ایجاد شد |
| 204 | No Content | حذف موفق |
| 400 | Bad Request | خطا در ورودی |
| 404 | Not Found | یافت نشد |
| 422 | Validation Error | خطای اعتبارسنجی |
| 500 | Server Error | خطای سرور |

---

## 🧪 تست API ها

### استفاده از cURL

```bash
# Health check
curl http://localhost:8000/api/health

# دریافت پیام
curl -X POST http://localhost:8000/api/ingestion/sync?limit=10

# آنالیتیکس
curl "http://localhost:8000/api/analytics/channels/{id}/stats?time_range=30min"
```

### استفاده از Postman

1. Import کردن collection
2. Set کردن base URL: `http://localhost:8000/api`
3. تست endpoints

### استفاده از Swagger UI

```
http://localhost:8000/docs
```

---

## 💡 نکات مهم

1. **Rate Limiting**: در production حتماً rate limiting اضافه کنید
2. **Caching**: برای analytics، از Redis برای cache استفاده کنید
3. **Async**: تمام APIها async هستند
4. **Error Handling**: همیشه status code را چک کنید
5. **Pagination**: برای لیست‌ها از skip/limit استفاده کنید

---

**آخرین به‌روزرسانی**: 2025-11-16
