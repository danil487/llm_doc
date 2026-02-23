#!/bin/bash
set -e

echo "🚀 Запуск RAG-системы..."

# Проверка переменных окружения
if [ -z "$CONFLUENCE_API_KEY" ]; then
    echo "❌ Ошибка: CONFLUENCE_API_KEY не установлен"
    exit 1
fi

if [ "$TELEGRAM_ENABLED" = "true" ] && [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Ошибка: TELEGRAM_ENABLED=true но TELEGRAM_BOT_TOKEN не установлен"
    exit 1
fi

# Создание директорий
mkdir -p /app/data/chroma_db /app/.cache /app/logs

# Запуск приложения
exec python /app/main.py