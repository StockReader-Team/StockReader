FROM python:3.11-slim

WORKDIR /app

# نصب dependencies سیستمی
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# نصب Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# کپی فایل‌های dependency
COPY pyproject.toml poetry.lock ./

# نصب dependencies (بدون dev dependencies)
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# کپی کد اپلیکیشن
COPY . .

# ساخت پوشه‌های ضروری
RUN mkdir -p /app/logs

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Expose port
EXPOSE 8000

# اجرای اپلیکیشن
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
