#!/bin/bash
set -e

echo "🚀 Запуск enhanced-llm-retrieval..."

REBUILD="${1:-}"

if [ "$REBUILD" = "--rebuild" ] || [ "$REBUILD" = "-r" ]; then
    echo "📦 Пересборка образов..."
    docker compose build --pull
elif [ "$REBUILD" = "--no-cache" ]; then
    echo "🧹 Полная пересборка..."
    docker compose build --no-cache
else
    echo "📦 Проверка образов..."
    docker compose build
fi

echo "🔗 Запуск контейнеров..."

# Проверка NVIDIA GPU
if command -v nvidia-smi &> /dev/null 2>&1 && [ "${2:-}" = "--gpu" ]; then
    echo "🎮 Запуск с GPU..."
    # Проверка Docker Compose версии
    if docker compose version &> /dev/null 2>&1; then
        docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
    else
        echo "⚠️  Docker Compose v2 не найден, пробуем v1..."
        docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
    fi
else
    echo "🖥️  Запуск в CPU-режиме..."
    docker compose up -d
fi

echo "⏳ Ожидание инициализации..."
sleep 15

echo ""
echo "============================================"
echo "✅ Система запущена!"
echo "============================================"
echo ""
echo "📋 Полезные команды:"
echo "   • docker compose logs -f app    - Логи приложения"
echo "   • docker compose logs -f ollama - Логи Ollama"
echo "   • docker compose exec app bash  - Вход в контейнер"
echo "   • ./stop.sh --down              - Остановка"
echo ""
echo "🤖 Telegram: https://t.me/your_bot_name"
echo "============================================"