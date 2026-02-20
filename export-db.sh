#!/bin/bash
# export-db.sh — Экспорт ChromaDB + Redis tracking (универсальная версия)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="rag-db-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}"

# Создаём директорию для бэкапов
mkdir -p "$OUTPUT_DIR"

echo "💾 Экспорт базы данных..."
echo "   ChromaDB + Redis + Ollama → $ARCHIVE_PATH"
echo ""

# 🔍 Автоматический поиск volumes
echo "🔍 Поиск volumes..."
CHROMA_VOLUME=$(docker volume ls --format '{{.Name}}' | grep -E "chroma.*data" | head -1)
REDIS_VOLUME=$(docker volume ls --format '{{.Name}}' | grep -E "redis.*data" | head -1)
OLLAMA_VOLUME=$(docker volume ls --format '{{.Name}}' | grep -E "ollama.*data" | head -1)

if [ -z "$CHROMA_VOLUME" ]; then
    echo "⚠️  Chroma volume не найден. Возможно, контейнеры не запускались."
    echo "   Запустите: docker-compose up -d"
    exit 1
fi

echo "✅ Найдены volumes:"
echo "   ChromaDB: $CHROMA_VOLUME"
echo "   Redis: ${REDIS_VOLUME:-не найден}"
echo "   Ollama: ${OLLAMA_VOLUME:-не найден}"
echo ""

# Экспортируем ChromaDB
if [ -n "$CHROMA_VOLUME" ]; then
    echo "📦 Экспорт ChromaDB..."
    docker run --rm \
        -v "$CHROMA_VOLUME":/source \
        -v "$OUTPUT_DIR":/backup \
        alpine tar -czf "/backup/${ARCHIVE_NAME}.chroma" -C /source .
    echo "✅ ChromaDB экспортирован"
fi

# Экспортируем Redis (если есть)
if [ -n "$REDIS_VOLUME" ]; then
    echo "📦 Экспорт Redis..."
    docker run --rm \
        -v "$REDIS_VOLUME":/source \
        -v "$OUTPUT_DIR":/backup \
        alpine tar -czf "/backup/${ARCHIVE_NAME}.redis" -C /source .
    echo "✅ Redis экспортирован"
fi

# Экспортируем Ollama (если есть)
if [ -n "$OLLAMA_VOLUME" ]; then
    echo "📦 Экспорт Ollama моделей..."
    docker run --rm \
        -v "$OLLAMA_VOLUME":/source \
        -v "$OUTPUT_DIR":/backup \
        alpine tar -czf "/backup/${ARCHIVE_NAME}.ollama" -C /source .
    echo "✅ Ollama экспортирована"
fi

# Создаём manifest
cat > "${OUTPUT_DIR}/${ARCHIVE_NAME}.manifest" << EOF
RAG Database Export
===================
Timestamp: $(date -Iseconds)
Hostname: $(hostname)
Project: $(cd "$SCRIPT_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")

Volumes:
  - chroma-data: ${CHROMA_VOLUME}
  - redis-data: ${REDIS_VOLUME:-N/A}
  - ollama-data: ${OLLAMA_VOLUME:-N/A}
EOF

# Объединяем в один архив
echo "📦 Создание итогового архива..."
tar -czf "$ARCHIVE_PATH" \
    -C "$OUTPUT_DIR" \
    "${ARCHIVE_NAME}.chroma" \
    "${ARCHIVE_NAME}.redis" \
    "${ARCHIVE_NAME}.ollama" \
    "${ARCHIVE_NAME}.manifest" 2>/dev/null || \
tar -czf "$ARCHIVE_PATH" \
    -C "$OUTPUT_DIR" \
    "${ARCHIVE_NAME}.chroma" \
    "${ARCHIVE_NAME}.manifest"

# Удаляем временные файлы
rm -f "${OUTPUT_DIR}/${ARCHIVE_NAME}.chroma"
rm -f "${OUTPUT_DIR}/${ARCHIVE_NAME}.redis"
rm -f "${OUTPUT_DIR}/${ARCHIVE_NAME}.ollama"
rm -f "${OUTPUT_DIR}/${ARCHIVE_NAME}.manifest"

echo ""
echo "✅ Экспорт завершён: $ARCHIVE_PATH"
echo "   Размер: $(du -h "$ARCHIVE_PATH" | cut -f1)"
echo ""
echo "Для импорта на другой машине:"
echo "  ./import-db.sh $ARCHIVE_PATH"