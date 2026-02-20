#!/bin/sh
# scripts/wait-for.sh — Ждёт доступности хоста:порт

set -e

HOST="${1%%:*}"
PORT="${1##*:}"
TIMEOUT="${2:-30}"
SLEEP_INTERVAL=2

if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    echo "Использование: $0 host:port [timeout_seconds]"
    exit 1
fi

echo "⏳ Ожидание ${HOST}:${PORT} (таймаут: ${TIMEOUT}s)..."

for i in $(seq 1 $((TIMEOUT / SLEEP_INTERVAL))); do
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "✅ ${HOST}:${PORT} доступен"
        exit 0
    fi
    sleep $SLEEP_INTERVAL
done

echo "❌ Таймаут ожидания ${HOST}:${PORT}"
exit 1