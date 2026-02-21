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

# ✅ ПРЕДЗАГРУЗКА МОДЕЛИ OLLAMA (чтобы не грузилась при первом запросе)
echo "⏳ Предзагрузка модели Ollama..."
OLLAMA_HOST=${OLLAMA_HOST:-http://ollama:11434}
OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.1}

# Ждём пока Ollama будет доступен
for i in {1..30}; do
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo "✅ Ollama доступен"
        break
    fi
    echo "⏳ Ожидание Ollama... ($i/30)"
    sleep 2
done

# ✅ Проверяем наличие модели и загружаем если нет
echo "📥 Проверка модели $OLLAMA_MODEL..."
if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "$OLLAMA_MODEL"; then
    echo "📥 Загрузка модели $OLLAMA_MODEL (это может занять несколько минут)..."
    ollama pull $OLLAMA_MODEL
else
    echo "✅ Модель $OLLAMA_MODEL уже доступна"
fi

# ✅ "Прогреваем" модель (первый запрос для загрузки в память)
echo "🔥 Прогрев модели..."
curl -X POST "$OLLAMA_HOST/api/generate" -d "{
    \"model\": \"$OLLAMA_MODEL\",
    \"prompt\": \"тест\",
    \"stream\": false
}" > /dev/null 2>&1 || true
echo "✅ Модель прогрета"

# Создание директорий
mkdir -p /app/data/chroma_db /app/.cache /app/logs

# Запуск приложения
exec python /app/main.py