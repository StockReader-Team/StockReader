# Database Schema - Telegram Data Cleaner

## 📊 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATABASE SCHEMA                              │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│     categories       │
├──────────────────────┤
│ id (UUID) PK        │◄──┐
│ name (String) UQ     │   │
│ parent_id (UUID) FK  │───┘ (self-referential)
│ description (Text)   │
│ created_at           │
│ updated_at           │
└──────────────────────┘
         │ 1
         │
         │ N
         ▼
┌──────────────────────┐
│      channels        │
├──────────────────────┤
│ id (UUID) PK        │
│ telegram_id (String) │ UQ, IDX
│ name (String)        │
│ username (String)    │ IDX
│ category_id (UUID)   │ FK
│ is_active (Boolean)  │
│ last_sync (DateTime) │
│ created_at           │
│ updated_at           │
└──────────────────────┘
         │ 1
         │
         │ N
         ▼
┌──────────────────────────────────┐
│          messages                │
├──────────────────────────────────┤
│ id (UUID) PK                    │
│ telegram_message_id (BigInt)    │
│ channel_id (UUID) FK             │ IDX
│ text (Text)                      │
│ text_normalized (Text)           │
│ date (DateTime)                  │ IDX
│ views (Integer)                  │
│ forwards (Integer)               │
│ extra_data (JSONB)               │
│ created_at                       │
│ updated_at                       │
└──────────────────────────────────┘
         │ N                        │ N
         │                          │
         │                          │
         ▼                          ▼
┌─────────────────────┐    ┌──────────────────┐
│   message_tags      │    │      tags        │
├─────────────────────┤    ├──────────────────┤
│ message_id (UUID)PK │◄───│ id (UUID) PK    │
│ tag_id (UUID) PK    │───►│ name (String) UQ │ IDX
│ matched_at          │    │ tag_type (Enum)  │ IDX
└─────────────────────┘    │ condition (JSONB)│
                           │ description      │
                           │ is_active (Bool) │
                           │ created_at       │
                           │ updated_at       │
                           └──────────────────┘
```

## 🔑 Indexes

### Performance Indexes:
1. **categories**
   - `ix_categories_id` - Primary key index
   - `ix_categories_name` - Unique name lookup
   - `ix_categories_parent_id` - Tree navigation

2. **channels**
   - `ix_channels_id` - Primary key index
   - `ix_channels_telegram_id` - Unique telegram ID
   - `ix_channels_username` - Username search
   - `ix_channels_category_id` - Category filtering

3. **messages**
   - `ix_messages_id` - Primary key index
   - `ix_messages_channel_id` - Channel filtering
   - `ix_messages_date` - Time-based queries
   - `idx_channel_date` - Composite (channel_id, date)
   - `idx_channel_telegram_id` - Unique (channel_id, telegram_message_id)

4. **tags**
   - `ix_tags_id` - Primary key index
   - `ix_tags_name` - Unique name lookup
   - `ix_tags_tag_type` - Type filtering

## 📋 Table Details

### 1. categories
**Purpose**: دسته‌بندی سلسله‌مراتبی کانال‌ها

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | شناسه یکتا |
| name | String(255) | UNIQUE, NOT NULL | نام دسته |
| parent_id | UUID | FK → categories.id | دسته والد |
| description | Text | NULL | توضیحات |
| created_at | DateTime | NOT NULL | تاریخ ساخت |
| updated_at | DateTime | NOT NULL | تاریخ به‌روزرسانی |

**Relationships**:
- Self-referential: category → parent category
- One-to-Many: category → channels

---

### 2. channels
**Purpose**: کانال‌های تلگرام

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | شناسه یکتا |
| telegram_id | String(255) | UNIQUE, NOT NULL | شناسه تلگرام |
| name | String(255) | NOT NULL | نام کانال |
| username | String(255) | NULL | نام کاربری |
| category_id | UUID | FK → categories.id | دسته‌بندی |
| is_active | Boolean | NOT NULL, DEFAULT=True | وضعیت فعال |
| last_sync | DateTime | NULL | آخرین sync |
| created_at | DateTime | NOT NULL | تاریخ ساخت |
| updated_at | DateTime | NOT NULL | تاریخ به‌روزرسانی |

**Relationships**:
- Many-to-One: channel → category
- One-to-Many: channel → messages

---

### 3. messages
**Purpose**: پیام‌های دریافتی از کانال‌ها

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | شناسه یکتا |
| telegram_message_id | BigInteger | NOT NULL | شناسه پیام تلگرام |
| channel_id | UUID | FK → channels.id | کانال مربوطه |
| text | Text | NULL | متن اصلی |
| text_normalized | Text | NULL | متن نرمال شده |
| date | DateTime | NOT NULL | تاریخ ارسال |
| views | Integer | NULL | تعداد بازدید |
| forwards | Integer | NULL | تعداد forward |
| extra_data | JSONB | NULL | داده‌های اضافی |
| created_at | DateTime | NOT NULL | تاریخ ساخت |
| updated_at | DateTime | NOT NULL | تاریخ به‌روزرسانی |

**Unique Constraint**:
- (channel_id, telegram_message_id) - جلوگیری از duplicate

**Relationships**:
- Many-to-One: message → channel
- Many-to-Many: message ↔ tags (via message_tags)

---

### 4. tags
**Purpose**: تگ‌ها برای دسته‌بندی پیام‌ها

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | شناسه یکتا |
| name | String(255) | UNIQUE, NOT NULL | نام تگ |
| tag_type | Enum | NOT NULL | نوع تگ |
| condition | JSONB | NULL | شرایط match |
| description | Text | NULL | توضیحات |
| is_active | Boolean | NOT NULL, DEFAULT=True | وضعیت فعال |
| created_at | DateTime | NOT NULL | تاریخ ساخت |
| updated_at | DateTime | NOT NULL | تاریخ به‌روزرسانی |

**Tag Types (Enum)**:
- `CHARACTER_COUNT`: بر اساس تعداد کاراکتر
- `WORD_COUNT`: بر اساس تعداد کلمه
- `CUSTOM`: شرایط سفارشی

**Condition Examples**:
```json
// CHARACTER_COUNT
{"min": 100, "max": 500}

// WORD_COUNT
{"min": 20, "max": 100}

// CUSTOM
{"keywords": ["سهام", "بورس"], "operator": "OR"}
```

**Relationships**:
- Many-to-Many: tag ↔ messages (via message_tags)

---

### 5. message_tags
**Purpose**: جدول رابط many-to-many

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| message_id | UUID | PK, FK → messages.id | شناسه پیام |
| tag_id | UUID | PK, FK → tags.id | شناسه تگ |
| matched_at | DateTime | NOT NULL | زمان match |

**Composite Primary Key**: (message_id, tag_id)

---

## 🔄 Data Flow

```
1. API Response
   └─► Parse JSON
       └─► Extract Channel Info
           └─► Save/Update Channel
               └─► Extract Messages
                   └─► Normalize Text (hazm)
                       └─► Save Message
                           └─► Apply Tags (matching)
                               └─► Save MessageTag
```

## 📊 Sample Queries

### Get messages with channel info:
```sql
SELECT m.*, c.name as channel_name, c.username
FROM messages m
JOIN channels c ON m.channel_id = c.id
WHERE m.date > NOW() - INTERVAL '7 days'
ORDER BY m.date DESC;
```

### Get tagged messages:
```sql
SELECT m.text, t.name as tag_name
FROM messages m
JOIN message_tags mt ON m.id = mt.message_id
JOIN tags t ON mt.tag_id = t.id
WHERE t.is_active = TRUE;
```

### Channel statistics:
```sql
SELECT
    c.name,
    COUNT(m.id) as message_count,
    AVG(m.views) as avg_views,
    MAX(m.date) as last_message
FROM channels c
LEFT JOIN messages m ON c.id = m.channel_id
GROUP BY c.id, c.name
ORDER BY message_count DESC;
```

### Category tree:
```sql
WITH RECURSIVE category_tree AS (
    SELECT id, name, parent_id, 0 as level
    FROM categories
    WHERE parent_id IS NULL

    UNION ALL

    SELECT c.id, c.name, c.parent_id, ct.level + 1
    FROM categories c
    JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT * FROM category_tree ORDER BY level, name;
```

---

## 💾 Storage Estimates

**Assumptions**:
- 200 channels
- 4,500 messages/day
- 15 days retention
- Average message: 200 chars

**Calculations**:
```
Messages in 15 days: 4,500 × 15 = 67,500 messages
Storage per message: ~2KB (with indexes)
Total message storage: 67,500 × 2KB ≈ 135 MB

Channels: 200 × 1KB = 200 KB
Tags: 100 × 500B = 50 KB
Message-Tags: ~10 tags/message × 67,500 = 675,000 records × 100B ≈ 68 MB

Total: ~203 MB (for 15 days)
```

**Growth per month**: ~400 MB

---

## 🔐 Security Considerations

1. **No sensitive data** stored in plain text
2. **UUID** prevents sequential ID guessing
3. **Foreign keys** ensure referential integrity
4. **Indexes** optimize common queries
5. **JSONB** allows flexible metadata without schema changes

---

## 🚀 Performance Tips

1. **Use composite indexes** for common query patterns
2. **Partition messages table** by date (for large datasets)
3. **Archive old data** after 15 days
4. **Use EXPLAIN ANALYZE** for query optimization
5. **Monitor index usage** with pg_stat_user_indexes

---

## 📈 Future Enhancements (فاز 2+)

- [ ] Add message_analytics table
- [ ] Add user_subscriptions for personalized tags
- [ ] Add scheduled_reports table
- [ ] Add api_logs for audit trail
- [ ] Implement table partitioning for messages
- [ ] Add full-text search indexes
