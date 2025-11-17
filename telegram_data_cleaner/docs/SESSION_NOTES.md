# یادداشت‌های جلسات توسعه

## 📅 تاریخچه جلسات

این فایل شامل خلاصه تمام جلسات کاری و تصمیمات گرفته شده در طول توسعه پروژه است. در صورت قطع ارتباط، از این فایل برای ادامه کار استفاده کنید.

---

## جلسه 1: راه‌اندازی اولیه (روزهای اول)

### موضوعات بحث شده
- معرفی پروژه و نیازمندی‌ها
- طراحی معماری کلی
- انتخاب تکنولوژی‌ها

### تصمیمات
- ✅ استفاده از FastAPI برای backend
- ✅ PostgreSQL برای دیتابیس
- ✅ Alpine.js برای UI (lightweight)
- ✅ Real-time ingestion از API خارجی

### کارهای انجام شده
- ایجاد ساختار پروژه
- Setup مدل‌های اولیه (Channel, Message, Category)
- Ingestion service پایه
- UI ساده برای مدیریت

---

## جلسه 2: سیستم لغت‌نامه (میانه‌ی پروژه)

### موضوعات بحث شده
- نیاز به سیستم لغت‌نامه برای تطابق کلمات
- دسته‌بندی کلمات (نمادها، صنایع، و غیره)
- ذخیره اطلاعات اضافی (نام شرکت، صنعت)

### تصمیمات
- ✅ ایجاد مدل‌های Dictionary جدید
- ✅ استفاده از JSONB برای extra_data
- ✅ دسته‌بندی سلسله‌مراتبی
- ✅ Import از CSV برای نمادهای بورسی

### کارهای انجام شده
```python
# مدل‌های ایجاد شده:
- Dictionary (اصلی)
- DictionaryCategory (دسته‌بندی)
- DictionaryWord (کلمات)
- MessageDictionary (رابطه many-to-many)
```

### مشکلات حل شده
**مشکل**: چطور اطلاعات اضافی نماد را ذخیره کنیم؟

**راه‌حل**: استفاده از JSONB field:
```json
{
  "symbol_name": "فولاد",
  "company_name": "فولاد مبارکه اصفهان",
  "industry_name": "فلزات اساسی",
  "keywords": ["فولادمبارکه", "مبارکه"]
}
```

---

## جلسه 3: سیستم Matching و Text Processing

### موضوعات بحث شده
- پردازش متن فارسی
- نرمال‌سازی (تبدیل حروف عربی به فارسی)
- Matching الگوریتم

### تصمیمات
- ✅ استفاده از Hazm با fallback
- ✅ نرمال‌سازی قبل از matching
- ✅ ذخیره normalized text در دیتابیس

### کارهای انجام شده
- پیاده‌سازی TextNormalizer
- MatchingService
- UI برای نمایش تطابق‌ها

### کد کلیدی

```python
class TextNormalizer:
    def normalize(self, text: str) -> str:
        # تبدیل عربی به فارسی
        text = text.replace("ك", "ک")
        text = text.replace("ي", "ی")

        # حذف diacritics
        text = re.sub(r'[\u064B-\u065F]', '', text)

        # نرمال‌سازی فضاها
        text = re.sub(r'\s+', ' ', text)

        return text.strip()
```

---

## جلسه 4: مشکل Hashtag و حل آن ⭐

### موضوعات بحث شده
کاربر گزارش داد: **پیام‌هایی که `#فولای` دارند، match نمی‌شوند!**

### تحلیل مشکل

**مرحله 1: بررسی اولیه**
```python
# پیام واقعی:
"در بورس امروز #فولای رشد خوبی داشت"

# بعد از normalize:
"در بورس امروز  رشد خوبی داشت"  # ← هشتگ کامل حذف شده!
```

**علت**:
```python
# در TextNormalizer (خط 144):
text = re.sub(r'#\w+', '', text)  # ← این خط هشتگ را حذف می‌کند!
```

### راه‌حل (دو مرحله)

#### مرحله 1: اضافه کردن هشتگ به keywords

**اسکریپت**: `/tmp/add_hashtag_to_symbols.py`

```python
async def add_hashtags_to_symbols():
    # گرفتن تمام نمادها
    symbols = await session.execute(
        select(DictionaryWord)
        .where(DictionaryWord.category_id == symbols_category_id)
    )

    for symbol in symbols:
        hashtag = f"#{symbol.word}"

        # اضافه کردن به keywords
        if 'keywords' not in symbol.extra_data:
            symbol.extra_data['keywords'] = []

        if hashtag not in symbol.extra_data['keywords']:
            symbol.extra_data['keywords'].append(hashtag)

            # مهم: برای update شدن JSONB
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(symbol, 'extra_data')

    await session.commit()
```

**نتیجه**: 2917 نماد به‌روز شد

#### مرحله 2: تغییر TextNormalizer

```python
# قبل:
text = re.sub(r'#\w+', '', text)  # حذف کامل هشتگ

# بعد:
text = re.sub(r'#(\w+)', r'\1', text)  # نگه‌داشتن متن، حذف #
```

**نتیجه**:
```python
# قبل:
"#فولای" → ""  # ❌ خالی!

# بعد:
"#فولای" → "فولای"  # ✅ match می‌شود!
```

### تست و تایید

**اسکریپت دیباگ**: `/tmp/debug_matching.py`

```python
# تست نرمال‌سازی:
normalizer = TextNormalizer()

test = "#فولای"
result = normalizer.normalize(test)
print(f"'{test}' → '{result}'")
# خروجی: '#فولای' → 'فولای' ✅
```

**نتایج واقعی**:
- قبل از fix: 69 match
- بعد از fix + sync جدید: 196 match
- افزایش: **127 match جدید** 🎉

### مشکل پیام‌های قدیمی

**سوال کاربر**: چطور باید با پیام‌های قدیمی برخورد کنیم؟

**بحث**:
1. **Re-normalize**: پردازش دوباره تمام پیام‌ها
   - ✅ مزیت: داده کامل
   - ❌ معایب: زمان‌بر، سنگین

2. **Skip**: پیام‌های قدیمی را رها کنیم
   - ✅ مزیت: ساده، سریع
   - ✅ پیام‌های قدیمی طبق retention policy حذف می‌شوند

**تصمیم نهایی**: Skip شد (گزینه 2)

---

## جلسه 5: بحث Generic Words (حل نشده)

### مشکل مطرح شده

**کاربر گفت**:
> "برخی کلمات خیلی عمومی هستند مثل 'بورس'، 'سلام'، 'ارزش'، 'رشد'. نباید این‌ها match بشوند."

### راه‌حل‌های پیشنهادی

#### 1. Stopwords List
```python
STOPWORDS = {
    "بورس", "سلام", "ارزش", "رشد", "افزایش",
    "کاهش", "قیمت", "امروز", "دیروز"
}

# در matching:
if word in STOPWORDS:
    skip
```

**مزایا**: ساده، سریع
**معایب**: نیاز به نگهداری دستی

#### 2. TF-IDF Filtering
```python
from sklearn.feature_extraction.text import TfidfVectorizer

# محاسبه TF-IDF برای تمام پیام‌ها
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(all_messages)

# کلماتی با TF-IDF پایین → generic
generic_words = [word for word, tfidf in scores if tfidf < threshold]
```

**مزایا**: خودکار، دقیق
**معایب**: پیچیده، نیاز به محاسبه

#### 3. Document Frequency Threshold
```python
# کلماتی که در بیش از 50% پیام‌ها هست → generic
word_doc_count = Counter()
for message in messages:
    unique_words = set(message.split())
    for word in unique_words:
        word_doc_count[word] += 1

total_docs = len(messages)
generic_words = [
    word for word, count in word_doc_count.items()
    if count / total_docs > 0.5
]
```

**مزایا**: منطقی، قابل تنظیم
**معایب**: نیاز به آپدیت دوره‌ای

#### 4. Context-Aware Matching
```python
# فقط match کن اگر با کلمات دیگر همراه باشد
# مثلاً "بورس تهران" ✅ ولی "بورس" به تنهایی ❌

if word == "بورس":
    # چک کن کلمات اطراف
    context = get_context_words(text, word)
    if not any(ctx in VALID_CONTEXT for ctx in context):
        skip
```

#### 5. Whitelisting برای نمادها
```python
# برای دسته "نمادها"، فقط exact match
# برای بقیه، flexible match

if category.name == "نمادها":
    # فقط کلمه دقیق
    if word != text_token:
        skip
else:
    # flexible matching
    if word in text_token or text_token in word:
        match
```

### تصمیم

**کاربر گفت**:
> "دارم روی این فکر می‌کنم. بذار فعلاً skip کنیم و بریم سراغ Analytics."

**وضعیت**: ⏸️ Postponed (به آینده موکول شد)

---

## جلسه 6: سیستم Analytics (آخرین جلسه - امروز) ⭐

### درخواست کاربر

**کاربر گفت**:
> "بخش بعدی که باید کامل کنیم این است که باید محتواها را از دید کانال‌ها بررسی کنیم:
> - تعداد پیام‌های یک کانال
> - تعداد پیام یک کانل در مورد چه نماد یا صنعتی هست
> - بر اساس روز هفته / ساعت / بازه زمانی (5 دقیقه، 30 دقیقه، 60 دقیقه)
> - براساس لغت‌نامه‌ها بفهمیم محتوای یک کانال بیشتر در مورد کدوم نماد/صنعت/لغت‌نامه است"

### پاسخ و طراحی

**پیشنهاد معماری**:

```
1. جدول channel_analytics برای aggregates
2. Background job هر 5 دقیقه
3. API endpoints کامل
4. Excel export
5. UI با نمودارها
```

### تایید کاربر

**کاربر پرسید**:
1. ✅ Aggregation هر 5 دقیقه؟ → بله
2. ✅ Top 10؟ → بله (نماد، صنعت، لغت‌نامه)
3. ✅ مقایسه کانال‌ها؟ → بله
4. ✅ Excel export؟ → بله، API هم باید باشد
5. ✅ UI در داشبورد؟ → بله، با لینک در header

### کارهای انجام شده

#### 1. Database
```sql
CREATE TABLE channel_analytics (
  id UUID PRIMARY KEY,
  channel_id UUID NOT NULL,
  date DATE NOT NULL,
  hour INTEGER,
  day_of_week INTEGER,
  message_count INTEGER,
  match_count INTEGER,
  top_symbols JSONB,
  top_industries JSONB,
  top_categories JSONB,
  UNIQUE(channel_id, date, hour)
);
```

**Migration**: `2025_11_16_1326-ce268f39526d_add_channel_analytics_table.py`

#### 2. Service Layer
**فایل**: `src/core/analytics/channel_analytics_service.py`

**متدهای کلیدی**:
```python
class ChannelAnalyticsService:
    async def compute_aggregates(granularity: str)  # hourly/daily
    async def get_realtime_stats(channel_id, minutes)  # 5, 30, 60 min
    async def get_channel_content_profile(channel_id, days)
```

#### 3. Background Job
**فایل**: `src/services/scheduler_service.py`

```python
async def _analytics_aggregation_job(self):
    """هر 5 دقیقه اجرا می‌شود"""
    analytics_service = ChannelAnalyticsService(session)

    now = datetime.utcnow()
    start_hour = now.replace(minute=0, second=0, microsecond=0)

    await analytics_service.compute_aggregates(
        start_datetime=start_hour,
        end_datetime=now,
        granularity="hourly"
    )
```

**اضافه شده به start()**:
```python
def start(self):
    self.add_ingestion_job()
    self.add_cleanup_job()
    self.add_health_check_job()
    self.add_analytics_aggregation_job()  # ← جدید
```

#### 4. API Endpoints
**فایل**: `src/api/routes/analytics.py`

```python
GET  /api/analytics/channels/{id}/stats
GET  /api/analytics/channels/{id}/content-profile
GET  /api/analytics/channels/compare
GET  /api/analytics/channels/{id}/export/excel
POST /api/analytics/compute-aggregates
```

#### 5. Excel Export
**کتابخانه**: `openpyxl`

**نصب**:
```bash
poetry add openpyxl
```

**Sheets**:
1. Overview: خلاصه آمار
2. Categories: دسته‌بندی‌ها
3. Top Symbols: نمادها
4. Top Industries: صنایع

#### 6. UI Dashboard
**فایل**: `src/templates/analytics.html`

**امکانات**:
- ✅ انتخاب کانال
- ✅ انتخاب بازه زمانی (5min, 30min, 1hour, today, 7days, 30days)
- ✅ کارت‌های آمار (4 کارت)
- ✅ نمودار Bar برای نمادها (Chart.js)
- ✅ نمودار Pie برای دسته‌بندی‌ها
- ✅ جدول صنایع با progress bar
- ✅ دکمه Excel export
- ✅ Modal راهنما (دکمه "آموزش")

**لینک در header**: تمام صفحات به‌روز شد

#### 7. Documentation
**فایل‌های ایجاد شده**:
1. `docs/PROJECT_SUMMARY.md` - خلاصه کامل پروژه
2. `docs/API_GUIDE.md` - راهنمای کامل API
3. `docs/ANALYTICS_GUIDE.md` - راهنمای سیستم Analytics
4. `docs/SESSION_NOTES.md` - این فایل

---

## 📊 آمار کلی پروژه

### خطوط کد (تقریبی)
```
Backend Python: ~5000 lines
Frontend HTML/JS: ~2000 lines
SQL Migrations: ~500 lines
Documentation: ~3000 lines
Total: ~10,500 lines
```

### فایل‌های اصلی
```
Models: 10 files
Services: 3 files
API Routes: 4 files
Templates: 4 files
Migrations: 4 files
Docs: 4 files
```

### Database Tables
```
1. categories
2. channels
3. messages
4. tags
5. message_tags
6. dictionaries
7. dictionary_categories
8. dictionary_words
9. message_dictionary
10. channel_analytics ⭐
```

---

## ⏭️ آینده پروژه

### Tasks باقی‌مانده (از todo list)
- [ ] تست کامل Analytics
- [ ] تست Excel export
- [ ] افزودن نمونه داده برای دمو

### ویژگی‌های آینده (پیشنهادی)
1. **Generic Words Filtering** (از جلسه 5)
2. **Authentication & Authorization**
3. **Advanced Analytics**:
   - Sentiment analysis
   - Trend detection
   - Anomaly detection
4. **Notifications**:
   - Alert برای spike در یک نماد
   - Daily/Weekly reports به ایمیل
5. **Performance Optimization**:
   - Redis caching
   - Database query optimization
   - Async improvements
6. **UI Enhancements**:
   - Dark mode
   - Mobile responsive
   - Advanced filters
7. **Integration**:
   - Webhook support
   - REST API v2
   - GraphQL (optional)

---

## 🎓 درس‌های آموخته شده

### 1. JSONB در SQLAlchemy
**مشکل**: تغییرات JSONB detect نمی‌شد

**راه‌حل**:
```python
from sqlalchemy.orm.attributes import flag_modified

symbol.extra_data['keywords'].append(new_keyword)
flag_modified(symbol, 'extra_data')  # ← ضروری
await session.commit()
```

### 2. Regex برای Hashtag
**مشکل**: `r'#\w+'` کل هشتگ را حذف می‌کرد

**راه‌حل**: استفاده از capturing group
```python
r'#(\w+)'  # capture می‌کند
r'\1'      # فقط متن را برمی‌گرداند
```

### 3. Aggregation Strategy
**سوال**: Real-time یا Pre-computed?

**پاسخ**: هر دو!
- Real-time برای بازه‌های کوتاه (< 1 ساعت)
- Pre-computed برای بازه‌های طولانی (> 1 روز)

### 4. Background Jobs
**یادگیری**: APScheduler قدرتمند است

```python
# IntervalTrigger برای دوره‌ای
IntervalTrigger(minutes=5)

# CronTrigger برای زمان مشخص
CronTrigger(hour=2, minute=0)
```

### 5. UI با Alpine.js
**یادگیری**: Alpine.js برای SPA های ساده عالی است

```javascript
x-data="appData()"      // state
x-model="variable"      // two-way binding
@click="function()"     // events
x-show="condition"      // conditional rendering
```

---

## 📝 نکات مهم برای ادامه کار

### اگر ارتباط قطع شد...

1. **وضعیت فعلی**:
   - ✅ سیستم Analytics کامل شده
   - ⏸️ Generic Words فیلترینگ postponed شد
   - ⏸️ تست‌های End-to-end باقی مانده

2. **اولویت‌ها برای جلسه بعد**:
   - [ ] تست کامل Analytics UI
   - [ ] تست Excel export
   - [ ] بررسی Performance
   - [ ] تصمیم‌گیری درباره Generic Words

3. **فایل‌های کلیدی برای ادامه**:
   ```
   src/core/analytics/channel_analytics_service.py
   src/api/routes/analytics.py
   src/templates/analytics.html
   docs/PROJECT_SUMMARY.md
   ```

4. **Commands مفید**:
   ```bash
   # اجرای سرور
   poetry run uvicorn src.main:app --reload

   # اجرای migration
   poetry run alembic upgrade head

   # تست analytics job دستی
   poetry run python scripts/test_analytics.py
   ```

5. **مشکلات احتمالی**:
   - Job اجرا نمی‌شود؟ → چک کنید scheduler start شده باشد
   - Excel download نمی‌شود؟ → چک کنید openpyxl نصب باشد
   - نمودارها نمایش داده نمی‌شود؟ → چک کنید Chart.js لود شده باشد

---

## 💬 نقل قول‌های کلیدی کاربر

1. **در مورد Hashtag**:
   > "نماد فولای هست با هشتگ ولی پیداش نکرده"

2. **در مورد Generic Words**:
   > "برخی کلمات جنرال هستند مثل بورس/سلام/ارزش/رشد"

3. **در مورد Analytics**:
   > "باید محتواها رو از دید کانل‌ها اوکی کنیم"

4. **در مورد Output**:
   > "خروجی هم اکسل باید باشه هم کل کاریهایی که میکنیم باید به صورت api خروجی بدیم چون چندین تا میکروسرویس هستند"

5. **در مورد Aggregation**:
   > "اگر پردازشش به سیستم ضرر نمیرسونه یا بار زیادی روی سرور نمیندازه هر ۵ دقیقه میخوام"

---

## ✅ Checklist برای ارائه

### قبل از دمو
- [ ] سرور اجرا شده باشد
- [ ] حداقل 2-3 کانال داده داشته باشد
- [ ] Aggregates حداقل یک بار اجرا شده باشد
- [ ] لغت‌نامه پر باشد (نمادها، صنایع)

### در حین دمو
1. **Ingestion**:
   - نشان دادن دریافت پیام
   - نشان دادن لیست کانال‌ها

2. **Dictionary**:
   - نشان دادن لیست نمادها
   - ویرایش یک نماد
   - Import از CSV

3. **Matching**:
   - نشان دادن صفحه Matches
   - فیلتر بر اساس نماد
   - فیلتر بر اساس کانال

4. **Analytics**:
   - انتخاب کانال
   - تغییر بازه زمانی
   - نمایش نمودارها
   - Export به Excel
   - نمایش راهنما

### بعد از دمو
- [ ] جمع‌آوری Feedback
- [ ] یادداشت نکات بهبود
- [ ] برنامه‌ریزی فاز بعدی

---

## 🎯 اهداف جلسه بعد

1. تست و اصلاح باگ‌های احتمالی Analytics
2. تصمیم‌گیری نهایی درباره Generic Words
3. بحث درباره Authentication (اگر لازم باشد)
4. برنامه‌ریزی برای Phase بعدی

---

**تاریخ آخرین به‌روزرسانی**: 2025-11-16, 13:30
**نسخه**: 1.0
**وضعیت**: ✅ آماده برای ادامه کار
