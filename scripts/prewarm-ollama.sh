#!/bin/bash
# scripts/prewarm-ollama.sh — Предзагружает модель в Ollama

MODEL="${1:-llama3.1}"
OLLAMA_HOST="${2:-http://localhost:11434}"

echo "🔥 Pre-warm Ollama: загрузка модели $MODEL..."

# Проверяем, есть ли модель
if curl -s "${OLLAMA_HOST}/api/tags" | grep -q "\"name\":\"${MODEL}\""; then
    echo "✅ Модель $MODEL уже загружена"
    exit 0
fi

echo "⬇️  Загрузка модели (это может занять 5-20 минут)..."
curl -X POST "${OLLAMA_HOST}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${MODEL}\"}"

if [ $? -eq 0 ]; then
    echo "✅ Модель $MODEL загружена"

    # Прогрев: делаем тестовый запрос
    echo "🔥 Прогрев модели..."
    curl -s -X POST "${OLLAMA_HOST}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"${MODEL}\", \"prompt\": \"ok\", \"stream\": false}" > /dev/null

    echo "✅ Модель готова к работе"
else
    echo "❌ Ошибка загрузки модели"
    exit 1
fi