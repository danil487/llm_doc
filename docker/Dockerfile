# docker/Dockerfile
FROM python:3.11-slim-bookworm

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    jq \
    libgl1 \
    libglib2.0-0 \
    wget \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ✅ КОПИРУЕМ ТОЛЬКО requirements.txt СНАЧАЛА (для кэша)
COPY requirements.txt .

# ✅ УСТАНАВЛИВАЕМ ЗАВИСИМОСТИ (кешируется отдельно)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ✅ КОПИРУЕМ ИСХОДНЫЙ КОД (после зависимостей)
COPY hybrid_search/ ./hybrid_search/
COPY rag_llm/ ./rag_llm/
COPY telegram_bot/ ./telegram_bot/
COPY controllers/ ./controllers/
COPY main.py .

# ✅ Создаём директории для данных (НЕ копируем данные!)
RUN mkdir -p /app/data/chroma_db /app/.cache /app/logs

# ✅ Копируем только entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 8443

ENV PYTHONPATH=/app
ENV TOKENIZERS_PARALLELISM=true
ENV FORCE_CPU=false

ENTRYPOINT ["/entrypoint.sh"]