#!/bin/bash
set -e

echo "🚀 Запуск enhanced-llm-retrieval..."

MODEL="${OLLAMA_MODEL:-llama3.1}"
OLLAMA_URL="${OLLAMA_HOST:-http://ollama:11434}"

echo "🔍 Проверка модели: $MODEL"

if curl -s "$OLLAMA_URL/api/tags" | grep -q "$MODEL"; then
    echo "✅ Модель '$MODEL' загружена"
else
    echo "⬇️  Загрузка модели (5-20 мин)..."
    curl -X POST "$OLLAMA_URL/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$MODEL\"}"
    echo "✅ Модель загружена"
fi

# Проверка Telegram токена
if [ "${TELEGRAM_ENABLED}" = "true" ]; then
    if [ -z "${TELEGRAM_BOT_TOKEN}" ]; then
        echo "⚠️  TELEGRAM_ENABLED=true но TELEGRAM_BOT_TOKEN не установлен"
        echo "💡 Отключаю Telegram Bot"
        export TELEGRAM_ENABLED=false
    else
        echo "✅ Telegram Bot включён"
    fi
fi

echo "🎯 Запуск main.py..."
exec python3 main.py "$@"