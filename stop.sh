#!/bin/bash

echo "🛑 Остановка enhanced-llm-retrieval..."

case "${1:-}" in
    --clean)
        echo "🧹 Полная очистка..."
        read -p "Продолжить? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down -v
            echo "✅ Очистка завершена"
        else
            echo "⏭️  Отменено"
        fi
        ;;
    --down)
        echo "🔻 Остановка контейнеров..."
        docker-compose down
        echo "✅ Готово"
        ;;
    *)
        echo "⏸️  Пауза контейнеров"
        docker-compose pause
        echo "💡 Возобновить: docker-compose unpause"
        echo "💡 Полная остановка: ./stop.sh --down"
        ;;
esac