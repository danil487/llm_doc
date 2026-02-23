#!/bin/bash
set -e

# ============================================
# 🎨 Цвета для вывода
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# ⚙️ Конфигурация
# ============================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
MAX_WAIT_TIME=120
WAIT_INTERVAL=5

# ============================================
# 📋 Функции
# ============================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_env_file() {
    # Проверка существования и валидности .env файла
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Файл .env не найден: $ENV_FILE"
        log_info "Создайте файл .env на основе .env.example"
        exit 1
    fi

    # Проверка критичных переменных
    source "$ENV_FILE" 2>/dev/null || true

    if [ -z "$CONFLUENCE_API_KEY" ]; then
        log_error "CONFLUENCE_API_KEY не установлен в .env"
        exit 1
    fi

    if [ "$TELEGRAM_ENABLED" = "true" ] && [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        log_error "TELEGRAM_ENABLED=true но TELEGRAM_BOT_TOKEN не установлен"
        exit 1
    fi

    log_success "Файл .env проверен"
}

check_docker() {
    # Проверка доступности Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker демон не запущен"
        exit 1
    fi

    log_success "Docker доступен"
}

check_gpu_support() {
    log_info "🔍 Проверка GPU поддержки..."

    # ✅ ТЕСТ 1: Проверка nvidia-smi внутри WSL (быстрая)
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi --query-gpu=name --format=csv,noheader &> /dev/null; then
            log_success "✅ GPU обнаружен в системе (WSL2)"
            GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
            log_info "   Видеокарта: $GPU_NAME"

            # ✅ ТЕСТ 2: Проверка Docker с правильным образом
            if docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 \
                nvidia-smi --query-gpu=name --format=csv,noheader &> /dev/null; then
                log_success "✅ Docker видит GPU"
                return 0
            else
                log_warning "⚠️  Docker не видит GPU (но WSL видит)"
                log_info "💡 Попробуйте: wsl --shutdown && перезапустите Docker Desktop"
                return 1
            fi
        fi
    fi

    # ✅ ТЕСТ 3: Альтернативная проверка через torch
    if docker run --rm --gpus all pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime \
        python -c "import torch; print('CUDA:', torch.cuda.is_available())" &> /dev/null; then
        log_success "✅ PyTorch CUDA проверка успешна"
        return 0
    fi

    log_warning "⚠️  GPU поддержка Docker не доступна"
    return 1
}

check_docker_compose() {
    # Определение команды Docker Compose
    if docker compose version &> /dev/null; then
        echo "docker compose"
    elif docker-compose version &> /dev/null; then
        echo "docker-compose"
    else
        log_error "Docker Compose не найден"
        exit 1
    fi
}

wait_for_service() {
    # Ожидание готовности сервиса по health check
    local service_name=$1
    local max_attempts=$((MAX_WAIT_TIME / WAIT_INTERVAL))
    local attempt=0

    log_info "Ожидание готовности $service_name..."

    while [ $attempt -lt $max_attempts ]; do
        if docker compose ps --format json 2>/dev/null | grep -q "\"Service\":\"$service_name\".*\"Health\":\"healthy\""; then
            log_success "$service_name готов"
            return 0
        fi

        # Fallback: просто проверяем статус
        if docker compose ps | grep -q "$service_name.*Up"; then
            log_success "$service_name запущен"
            return 0
        fi

        sleep $WAIT_INTERVAL
        attempt=$((attempt + 1))
        echo -n "."
    done

    echo ""
    log_warning "Таймаут ожидания $service_name (но продолжаем...)"
    return 0
}

cleanup_on_error() {
    # Очистка при ошибке запуска
    log_warning "Ошибка запуска, выполняем очистку..."
    docker compose down --remove-orphans 2>/dev/null || true
}

# ============================================
# 🚀 Основной скрипт
# ============================================

echo ""
echo "============================================"
echo "🚀 Enhanced LLM Retrieval System"
echo "============================================"
echo ""

# Проверка Docker
check_docker

# Проверка .env
check_env_file

# Определение Docker Compose команды
COMPOSE_CMD=$(check_docker_compose)
log_info "Используем: $COMPOSE_CMD"

# Обработка аргументов
REBUILD="${1:-}"
USE_GPU=false

# Обработка флагов
for arg in "$@"; do
    case $arg in
        --rebuild|-r)
            REBUILD="--rebuild"
            ;;
        --no-cache)
            REBUILD="--no-cache"
            ;;
        --gpu|-g)
            USE_GPU=true
            ;;
        --help|-h)
            echo "Использование: ./start.sh [OPTIONS]"
            echo ""
            echo "Опции:"
            echo "  --rebuild, -r      Пересборка образов"
            echo "  --no-cache         Полная пересборка без кэша"
            echo "  --gpu, -g          Запуск с GPU поддержкой"
            echo "  --help, -h         Показать справку"
            exit 0
            ;;
    esac
done

# Пересборка если нужно
if [ "$REBUILD" = "--rebuild" ] || [ "$REBUILD" = "-r" ]; then
    log_info "📦 Пересборка образов..."
    $COMPOSE_CMD build --pull
elif [ "$REBUILD" = "--no-cache" ]; then
    log_info "🧹 Полная пересборка без кэша..."
    $COMPOSE_CMD build --no-cache
else
    log_info "📦 Проверка образов..."
    $COMPOSE_CMD build
fi

# Определение режима запуска (GPU или CPU)
COMPOSE_FILES="-f docker-compose.yml"

if [ "$USE_GPU" = true ]; then
    if check_gpu_support; then
        log_info "🎮 Запуск с GPU поддержкой..."
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
    else
        log_warning "GPU запрошен но не доступен, запускаем на CPU"
        USE_GPU=false
    fi
fi

if [ "$USE_GPU" = false ]; then
    log_info "🖥️  Запуск в CPU режиме..."
fi

# Остановка старых контейнеров
log_info "🛑 Остановка существующих контейнеров..."
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true

# Запуск сервисов
log_info "🔗 Запуск контейнеров..."
if ! $COMPOSE_CMD $COMPOSE_FILES up -d; then
    log_error "Ошибка запуска контейнеров"
    cleanup_on_error
    exit 1
fi

# Ожидание готовности сервисов
echo ""
log_info "⏳ Ожидание инициализации сервисов..."

wait_for_service "redis"
wait_for_service "ollama"
wait_for_service "app"

# Финальная проверка
echo ""
if $COMPOSE_CMD ps | grep -q "app.*Up"; then
    log_success "Система успешно запущена!"
else
    log_warning "Контейнер app не в статусе Up, проверьте логи"
fi

# ============================================
# 📊 Информация о запуске
# ============================================
echo ""
echo "============================================"
echo "✅ Система запущена!"
echo "============================================"
echo ""
echo "📋 Контейнеры:"
$COMPOSE_CMD ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "📋 Полезные команды:"
echo "   • $COMPOSE_CMD logs -f app       - Логи приложения"
echo "   • $COMPOSE_CMD logs -f ollama    - Логи Ollama"
echo "   • $COMPOSE_CMD exec app bash     - Вход в контейнер"
echo "   • ./stop.sh --down               - Остановка"
echo "   • $COMPOSE_CMD ps                - Статус контейнеров"
echo ""

if [ "$TELEGRAM_ENABLED" = "true" ]; then
    echo "🤖 Telegram Bot: ✅ Включен"
    echo "   https://t.me/your_bot_name"
else
    echo "🤖 Telegram Bot: ❌ Выключен"
fi

if [ "$USE_GPU" = true ]; then
    echo "🎮 GPU: ✅ Активирован"
else
    echo "🎮 GPU: ❌ Не используется"
fi

echo ""
echo "============================================"
echo ""

# Проверка логов на ошибки при старте
log_info "Проверка логов на критические ошибки..."
if $COMPOSE_CMD logs --tail=50 app 2>/dev/null | grep -q "❌\|Error\|Exception"; then
    log_warning "Обнаружены ошибки в логах при старте!"
    log_info "Проверьте: $COMPOSE_CMD logs app"
fi

exit 0