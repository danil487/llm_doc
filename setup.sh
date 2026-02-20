#!/bin/bash
set -e

echo "🔧 Настройка enhanced-llm-retrieval"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose не найден"
    exit 1
fi

# Создание .env
if [ ! -f ".env" ]; then
    echo "📋 Копируем .env.example → .env"
    cp .env.example .env
    echo "⚠️  ОТРЕДАКТИРУЙТЕ .env: укажите Confluence API-ключи!"
    echo "   OLLAMA_MODEL=llama3.1 (по умолчанию)"
fi

# Проверка обязательных переменных
REQUIRED=("CONFLUENCE_API_KEY" "CONFLUENCE_URL")
MISSING=0
for var in "${REQUIRED[@]}"; do
    if ! grep -q "^${var}=" .env 2>/dev/null; then
        echo "❌ Отсутствует $var в .env"
        MISSING=1
    fi
done

if [ $MISSING -eq 1 ]; then
    echo "💡 Заполните обязательные переменные в .env"
    exit 1
fi

# Проверка GPU
if command -v nvidia-smi &> /dev/null 2>&1; then
    echo "✅ NVIDIA GPU обнаружен. Для GPU: ./start.sh --gpu"
fi

echo "✅ Настройка завершена!"
echo "🚀 Запустите: ./start.sh"