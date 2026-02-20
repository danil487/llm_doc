#!/bin/bash
set -e

echo "🚀 Запуск enhanced-llm-retrieval..."

REBUILD="${1:-}"

if [ "$REBUILD" = "--rebuild" ] || [ "$REBUILD" = "-r" ]; then
    echo "📦 Пересборка образов..."
    docker-compose build --pull
elif [ "$REBUILD" = "--no-cache" ]; then
    echo "🧹 Полная пересборка..."
    docker-compose build --no-cache
else
    echo "📦 Проверка образов..."
    docker-compose build
fi

echo "🔗 Запуск контейнеров..."
if command -v nvidia-smi &> /dev/null 2>&1 && [ "${2:-}" = "--gpu" ]; then
    echo "🎮 Запуск с GPU..."
    docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
else
    echo "🖥️  Запуск в CPU-режиме..."
    docker-compose up -d
fi

echo "⏳ Ожидание инициализации..."
sleep 15

echo ""
echo "📋 Подключение к интерактивному режиму..."
docker-compose exec -it app python3 main.py