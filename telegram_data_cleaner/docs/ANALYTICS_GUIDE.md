# راهنمای جامع سیستم آنالیتیکس

## 📊 معرفی

سیستم Analytics به شما امکان می‌دهد که به طور دقیق محتوای هر کانال تلگرام را تحلیل کنید و بفهمید که:
- کانال چند پیام دارد؟
- چند درصد پیام‌ها تطابق با لغت‌نامه دارند؟
- کانال روی چه نمادها و صنایعی تمرکز دارد؟
- محتوای کانال در طول زمان چگونه تغییر کرده؟

---

## 🎯 کاربردها

### 1. تحلیل کانال‌های خبری بورس
- شناسایی کانال‌هایی که بیشتر درباره نمادهای خاص صحبت می‌کنند
- پیدا کردن کانال‌های تخصصی در یک صنعت

### 2. Monitoring تغییرات
- ردیابی تغییر تمرکز یک کانال در طول زمان
- شناسایی Trending topics

### 3. گزارش‌دهی
- تهیه گزارش‌های دوره‌ای برای مدیریت
- Export به Excel برای تحلیل‌های بیشتر

---

## 📐 معماری سیستم

### Flow داده

```
1. پیام‌ها دریافت می‌شوند
   ↓
2. Matching: تطابق با لغت‌نامه
   ↓
3. Aggregation Job (هر 5 دقیقه):
   - شمارش پیام‌ها
   - شمارش تطابق‌ها
   - محاسبه Top 10 نمادها
   - محاسبه Top 10 صنایع
   - محاسبه توزیع دسته‌بندی‌ها
   ↓
4. ذخیره در جدول channel_analytics
   ↓
5. نمایش در UI / API
```

### جدول channel_analytics

```sql
CREATE TABLE channel_analytics (
  id UUID PRIMARY KEY,
  channel_id UUID NOT NULL,

  -- Time dimensions
  date DATE NOT NULL,
  hour INTEGER,  -- 0-23 (NULL برای daily)
  day_of_week INTEGER,  -- 0-6 (شنبه-جمعه)

  -- Metrics
  message_count INTEGER DEFAULT 0,
  match_count INTEGER DEFAULT 0,

  -- Top lists (JSONB)
  top_symbols JSONB,  -- [{"id": "...", "word": "فولاد", "count": 15}, ...]
  top_industries JSONB,  -- [{"name": "فلزات", "count": 25}, ...]
  top_categories JSONB,  -- [{"id": "...", "name": "نمادها", "count": 50}, ...]

  created_at TIMESTAMP,
  updated_at TIMESTAMP,

  UNIQUE(channel_id, date, hour)
);
```

---

## 🔧 نحوه کار سیستم

### 1. Aggregation (خودکار)

هر 5 دقیقه یکبار، job زیر اجرا می‌شود:

```python
async def _analytics_aggregation_job(self):
    # محاسبه aggregates برای ساعت جاری
    now = datetime.utcnow()
    start_hour = now.replace(minute=0, second=0, microsecond=0)

    analytics_service = ChannelAnalyticsService(session)

    records_created = await analytics_service.compute_aggregates(
        start_datetime=start_hour,
        end_datetime=now,
        granularity="hourly"
    )
```

### 2. محاسبه Aggregates

برای هر کانال و هر ساعت:

```python
# 1. شمارش پیام‌ها در این ساعت
messages = await session.execute(
    select(Message)
    .where(
        Message.channel_id == channel_id,
        Message.created_at >= start_hour,
        Message.created_at < end_hour
    )
)

# 2. شمارش تطابق‌ها
match_count = await session.execute(
    select(func.count(distinct(MessageDictionary.message_id)))
    .where(MessageDictionary.message_id.in_(message_ids))
)

# 3. Top 10 نمادها (از دسته "نمادها")
top_symbols = await session.execute(
    select(
        DictionaryWord.id,
        DictionaryWord.word,
        func.count(MessageDictionary.id).label('count')
    )
    .join(MessageDictionary)
    .where(
        MessageDictionary.message_id.in_(message_ids),
        DictionaryWord.category_id == symbols_category_id
    )
    .group_by(DictionaryWord.id, DictionaryWord.word)
    .order_by(func.count(MessageDictionary.id).desc())
    .limit(10)
)

# 4. Top 10 صنایع (از extra_data)
industries = Counter()
for word in matched_words:
    industry = word.extra_data.get('industry_name')
    if industry:
        industries[industry] += 1

top_industries = industries.most_common(10)

# 5. ذخیره در جدول
analytics_record = ChannelAnalytics(
    channel_id=channel_id,
    date=now.date(),
    hour=now.hour,
    day_of_week=now.weekday(),
    message_count=len(messages),
    match_count=match_count,
    top_symbols=[...],
    top_industries=[...],
    top_categories=[...]
)
```

---

## 🌐 API Endpoints

### 1. آمار Real-time

```http
GET /api/analytics/channels/{channel_id}/stats?time_range=30min
```

**بازه‌های زمانی**:
- `5min`: 5 دقیقه اخیر (query مستقیم از messages)
- `30min`: 30 دقیقه اخیر (query مستقیم)
- `1hour`: 1 ساعت اخیر (query مستقیم)
- `today`: امروز (از aggregates)
- `7days`: 7 روز اخیر (از aggregates)
- `30days`: 30 روز اخیر (از aggregates)

**نحوه کار**:
- برای بازه‌های کوتاه: query مستقیم از جدول `messages`
- برای بازه‌های طولانی: خواندن از `channel_analytics`

```python
if time_range in ["5min", "30min", "1hour"]:
    # Real-time query
    stats = await get_realtime_stats(channel_id, minutes)
else:
    # From aggregates
    stats = await get_channel_content_profile(channel_id, days)
```

### 2. پروفایل محتوایی

```http
GET /api/analytics/channels/{channel_id}/content-profile?days=7
```

**خروجی**:
```json
{
  "channel_id": "uuid",
  "days": 7,
  "total_messages": 5000,
  "total_matches": 1500,
  "categories": [
    {"name": "نمادها", "count": 1200, "percentage": 80.0},
    {"name": "اخبار", "count": 300, "percentage": 20.0}
  ],
  "primary_focus": "نمادها",
  "focus_percentage": 80.0
}
```

### 3. مقایسه کانال‌ها

```http
GET /api/analytics/channels/compare?channel_ids=uuid1,uuid2,uuid3&days=7
```

**کاربرد**: مقایسه همزمان تا 10 کانال

### 4. Excel Export

```http
GET /api/analytics/channels/{channel_id}/export/excel?days=7
```

**ساختار Excel**:

#### Sheet 1: Overview
```
┌──────────────────────────┬────────┐
│ Analysis Period (days)   │ 7      │
│ Total Messages           │ 5000   │
│ Total Matches            │ 1500   │
│ Primary Focus            │ نمادها │
│ Focus Percentage         │ 80%    │
│                          │        │
│ Last Hour Stats          │        │
│ Messages (last hour)     │ 45     │
│ Matches (last hour)      │ 12     │
└──────────────────────────┴────────┘
```

#### Sheet 2: Categories
```
┌───────────┬─────────────┬────────────┐
│ Category  │ Match Count │ Percentage │
├───────────┼─────────────┼────────────┤
│ نمادها    │ 1200        │ 80%        │
│ اخبار     │ 300         │ 20%        │
└───────────┴─────────────┴────────────┘
```

#### Sheet 3: Top Symbols
```
┌─────────┬─────────────┐
│ Symbol  │ Match Count │
├─────────┼─────────────┤
│ فولاد   │ 150         │
│ فملی    │ 120         │
└─────────┴─────────────┘
```

#### Sheet 4: Top Industries
```
┌────────────────┬─────────────┐
│ Industry       │ Match Count │
├────────────────┼─────────────┤
│ فلزات اساسی    │ 300         │
│ خودرو          │ 150         │
└────────────────┴─────────────┘
```

---

## 🖥️ استفاده از UI

### دسترسی
```
http://localhost:8000/analytics
```

### مراحل استفاده

#### 1. انتخاب کانال
- از لیست کشویی "انتخاب کانال" یک کانال را انتخاب کنید
- سیستم خودکار آمار را بارگذاری می‌کند

#### 2. انتخاب بازه زمانی
- 5 دقیقه اخیر: برای monitoring لحظه‌ای
- 30 دقیقه اخیر: برای بررسی سریع
- 1 ساعت اخیر: آمار کوتاه‌مدت
- امروز: عملکرد امروز
- 7 روز اخیر: بررسی هفتگی
- 30 روز اخیر: تحلیل ماهانه

#### 3. بررسی نمودارها

**کارت‌های آمار** (بالای صفحه):
- تعداد پیام‌ها
- تعداد تطابق‌ها
- درصد تطابق
- تمرکز اصلی

**نمودار 10 نماد برتر** (Bar Chart):
- نمادهایی که بیشترین تکرار را دارند
- مقایسه تعداد تکرار

**نمودار دسته‌بندی‌ها** (Pie Chart):
- توزیع محتوا بر اساس دسته‌بندی‌ها
- درک تمرکز کلی کانال

**جدول 10 صنعت برتر**:
- رتبه‌بندی صنایع
- نوار پیشرفت برای مقایسه بصری

#### 4. خروجی Excel
- کلیک روی دکمه "خروجی Excel"
- فایل به صورت خودکار دانلود می‌شود
- نام فایل: `channel_analytics_{channel_id}_{date}.xlsx`

---

## 🎨 نمودارها

### استفاده از Chart.js

```javascript
// نمودار میله‌ای برای نمادها
new Chart(ctx, {
    type: 'bar',
    data: {
        labels: symbols.map(s => s.word),
        datasets: [{
            label: 'تعداد',
            data: symbols.map(s => s.count),
            backgroundColor: 'rgba(59, 130, 246, 0.8)'
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false
    }
});

// نمودار دایره‌ای برای دسته‌بندی‌ها
new Chart(ctx, {
    type: 'pie',
    data: {
        labels: categories.map(c => c.name),
        datasets: [{
            data: categories.map(c => c.count),
            backgroundColor: colors
        }]
    },
    options: {
        plugins: {
            legend: {
                position: 'right',
                rtl: true
            }
        }
    }
});
```

---

## ⚙️ تنظیمات

### فاصله زمانی Aggregation

در `src/services/scheduler_service.py`:

```python
def add_analytics_aggregation_job(
    self,
    interval_minutes: int = 5,  # ← فاصله به دقیقه
    job_id: str = "analytics_aggregation_job"
)
```

**تغییر فاصله**:
```python
# در main.py
scheduler_service.add_analytics_aggregation_job(interval_minutes=10)
```

### سطح Granularity

```python
# Hourly aggregates
await analytics_service.compute_aggregates(
    start_datetime=start,
    end_datetime=end,
    granularity="hourly"  # یا "daily"
)
```

---

## 🔍 Query های پیچیده

### مثال 1: Top Symbols

```python
async def _get_top_words_by_category(
    self,
    message_ids: List[uuid.UUID],
    category_name: str,
    limit: int = 10
):
    # گرفتن category
    category = await session.execute(
        select(DictionaryCategory)
        .where(DictionaryCategory.name == category_name)
    )

    # شمارش کلمات
    result = await session.execute(
        select(
            DictionaryWord.id,
            DictionaryWord.word,
            func.count(MessageDictionary.id).label('count')
        )
        .join(MessageDictionary, MessageDictionary.word_id == DictionaryWord.id)
        .where(
            and_(
                MessageDictionary.message_id.in_(message_ids),
                DictionaryWord.category_id == category.id
            )
        )
        .group_by(DictionaryWord.id, DictionaryWord.word)
        .order_by(func.count(MessageDictionary.id).desc())
        .limit(limit)
    )

    return [
        {"id": str(row.id), "word": row.word, "count": row.count}
        for row in result
    ]
```

### مثال 2: Top Industries

```python
async def _get_top_industries(
    self,
    message_ids: List[uuid.UUID],
    limit: int = 10
):
    # گرفتن تمام words با extra_data
    result = await session.execute(
        select(
            DictionaryWord.extra_data,
            func.count(MessageDictionary.id).label('count')
        )
        .join(MessageDictionary)
        .where(
            and_(
                MessageDictionary.message_id.in_(message_ids),
                DictionaryWord.extra_data.isnot(None)
            )
        )
        .group_by(DictionaryWord.extra_data)
    )

    # شمارش صنایع
    industry_counter = Counter()
    for row in result:
        extra_data = row.extra_data or {}
        industry_name = extra_data.get('industry_name')
        if industry_name:
            industry_counter[industry_name] += row.count

    # Top 10
    return [
        {"name": name, "count": count}
        for name, count in industry_counter.most_common(limit)
    ]
```

---

## 📈 Performance

### بهینه‌سازی‌ها

1. **Indexes**:
```sql
CREATE INDEX idx_channel_analytics_channel_date
ON channel_analytics(channel_id, date);

CREATE INDEX idx_channel_analytics_date
ON channel_analytics(date);
```

2. **JSONB Indexing** (آینده):
```sql
CREATE INDEX idx_top_symbols
ON channel_analytics USING gin(top_symbols);
```

3. **Caching**:
```python
# استفاده از Redis برای cache کردن نتایج
cache_key = f"analytics:{channel_id}:{time_range}"
cached = await redis.get(cache_key)
if cached:
    return cached

# محاسبه...
await redis.setex(cache_key, 300, result)  # 5 min TTL
```

---

## 🐛 Debugging

### چک کردن Aggregates

```sql
-- آخرین aggregates
SELECT * FROM channel_analytics
ORDER BY created_at DESC
LIMIT 10;

-- aggregates یک کانال خاص
SELECT
  date,
  hour,
  message_count,
  match_count,
  top_symbols
FROM channel_analytics
WHERE channel_id = 'uuid-here'
ORDER BY date DESC, hour DESC
LIMIT 24;  -- 24 ساعت اخیر
```

### چک کردن Job

```python
# در Python shell
from src.database import db_manager
from src.core.analytics.channel_analytics_service import ChannelAnalyticsService

db_manager.init_engine()

async with db_manager.session() as session:
    service = ChannelAnalyticsService(session)

    # اجرای دستی
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = now - timedelta(hours=1)

    count = await service.compute_aggregates(
        start_datetime=start,
        end_datetime=now,
        granularity="hourly"
    )

    print(f"Created {count} records")
```

---

## 💡 نکات و ترفندها

### 1. تفسیر درصد تطابق

```
< 10%: کانال عمومی، محتوای متنوع
10-30%: کانال نیمه‌تخصصی
30-60%: کانال تخصصی
> 60%: کانال بسیار تخصصی
```

### 2. شناسایی Trending Topics

```python
# مقایسه امروز با دیروز
today_stats = get_stats(today)
yesterday_stats = get_stats(yesterday)

for symbol in today_stats.top_symbols:
    yesterday_count = get_count(yesterday_stats, symbol.word)
    growth = (symbol.count - yesterday_count) / yesterday_count * 100
    if growth > 50:
        print(f"{symbol.word} is trending! (+{growth}%)")
```

### 3. کانال‌های مشابه

```python
# پیدا کردن کانال‌های با primary_focus مشابه
similar_channels = await session.execute(
    select(ChannelAnalytics)
    .where(
        ChannelAnalytics.top_categories.contains([
            {"name": "نمادها"}
        ])
    )
    .distinct(ChannelAnalytics.channel_id)
)
```

---

## 🎯 موارد استفاده واقعی

### مثال 1: پیدا کردن بهترین کانال برای یک نماد

```python
# کدام کانال‌ها بیشتر درباره "فولاد" صحبت می‌کنند؟

# 1. گرفتن تمام aggregates 7 روز اخیر
analytics = await session.execute(
    select(ChannelAnalytics)
    .where(ChannelAnalytics.date >= last_week)
)

# 2. فیلتر کردن aggregates که فولاد در top symbols دارند
channels_with_foolad = []
for record in analytics:
    symbols = record.top_symbols or []
    for symbol in symbols:
        if symbol['word'] == 'فولاد':
            channels_with_foolad.append({
                'channel_id': record.channel_id,
                'count': symbol['count']
            })

# 3. Sort کردن بر اساس count
channels_with_foolad.sort(key=lambda x: x['count'], reverse=True)
```

### مثال 2: تحلیل الگوی زمانی کانال

```python
# کانال در چه ساعاتی فعال‌تر است؟

hourly_stats = await session.execute(
    select(
        ChannelAnalytics.hour,
        func.avg(ChannelAnalytics.message_count).label('avg_count')
    )
    .where(
        and_(
            ChannelAnalytics.channel_id == channel_id,
            ChannelAnalytics.hour.isnot(None),
            ChannelAnalytics.date >= last_month
        )
    )
    .group_by(ChannelAnalytics.hour)
    .order_by(ChannelAnalytics.hour)
)

# نمایش نمودار
for hour, avg_count in hourly_stats:
    bar = '█' * int(avg_count / 10)
    print(f"{hour:02d}:00 {bar} {avg_count:.1f}")
```

---

**آخرین به‌روزرسانی**: 2025-11-16
**نسخه**: 1.0
