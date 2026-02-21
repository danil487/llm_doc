#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "\033[0;34mℹ️  $1\033[0m"; }
log_success() { echo -e "\033[0;32m✅ $1\033[0m"; }

COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose не найден"
    exit 1
fi

echo ""
echo "============================================"
echo "🛑 Остановка системы"
echo "============================================"
echo ""

for arg in "$@"; do
    case $arg in
        --down|-d)
            log_info "Полная остановка с удалением..."
            $COMPOSE_CMD down --remove-orphans --volumes
            log_success "Система остановлена"
            exit 0
            ;;
        --clean|-c)
            log_info "Остановка с очисткой данных..."
            $COMPOSE_CMD down --remove-orphans --volumes --rmi all
            log_success "Система остановлена и очищена"
            exit 0
            ;;
    esac
done

log_info "Мягкая остановка..."
$COMPOSE_CMD stop
log_success "Контейнеры остановлены"

echo ""
echo "📋 Для полного удаления: ./stop.sh --down"
echo "📋 Для очистки данных: ./stop.sh --clean"
echo ""