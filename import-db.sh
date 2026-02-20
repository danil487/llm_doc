#!/bin/bash
# import-db.sh — Импорт ChromaDB + Redis tracking

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_PATH="${1:-}"

if [ -z "$ARCHIVE_PATH" ] || [ ! -f "$ARCHIVE_PATH" ]; then
    echo "Использование: $0 <путь_к_архиву>"
    echo ""
    echo "Пример:"
    echo "  $0 ./backups/rag-db-20260220_120000.tar.gz"
    exit 1
fi

echo "📥 Импорт базы данных из: $ARCHIVE_PATH"
echo ""

# Создаём временную директорию
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Распаковываем архив
echo "📦 Распаковка..."
tar -xzf "$ARCHIVE_PATH" -C "$TEMP_DIR"

# Извлекаем имена файлов из manifest
CHROMA_ARCHIVE=$(grep "chroma-data:" "$TEMP_DIR"/*.manifest | awk '{print $2}')
REDIS_ARCHIVE=$(grep "redis-data:" "$TEMP_DIR"/*.manifest | awk '{print $2}')
OLLAMA_ARCHIVE=$(grep "ollama-data:" "$TEMP_DIR"/*.manifest | awk '{print $2}')

# Останавливаем сервисы для безопасного импорта
echo "🛑 Остановка сервисов..."
docker-compose -f "${SCRIPT_DIR}/docker-compose.prebuilt.yml" down || true

# Импортируем ChromaDB
if [ -f "$TEMP_DIR/$CHROMA_ARCHIVE" ]; then
    echo "🗄️  Импорт ChromaDB..."
    docker run --rm \
        -v enhanced-llm-retrieval_chroma-/target \
        -v "$TEMP_DIR":/source \
        alpine sh -c "tar -xzf \"/source/$CHROMA_ARCHIVE\" -C /target"
    echo "✅ ChromaDB импортирован"
fi

# Импортируем Redis
if [ -f "$TEMP_DIR/$REDIS_ARCHIVE" ]; then
    echo "🗄️  Импорт Redis..."
    docker run --rm \
        -v enhanced-llm-retrieval_redis-/target \
        -v "$TEMP_DIR":/source \
        alpine sh -c "tar -xzf \"/source/$REDIS_ARCHIVE\" -C /target"
    echo "✅ Redis импортирован"
fi

# Импортируем Ollama (опционально, если модель уже загружена — можно пропустить)
if [ -f "$TEMP_DIR/$OLLAMA_ARCHIVE" ]; then
    echo "🤖 Импорт Ollama моделей..."
    docker run --rm \
        -v enhanced-llm-retrieval_ollama-/target \
        -v "$TEMP_DIR":/source \
        alpine sh -c "tar -xzf \"/source/$OLLAMA_ARCHIVE\" -C /target"
    echo "✅ Ollama модели импортированы"
fi

echo ""
echo "✅ Импорт завершён!"
echo ""
echo "Запустите систему:"
echo "  cd ${SCRIPT_DIR}"
echo "  ./quick-start.sh"