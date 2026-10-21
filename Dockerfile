FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and migrations
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

ENV PYTHONPATH=/app/src
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "stockguard.main:app", "--host", "0.0.0.0", "--port", "8000"]
