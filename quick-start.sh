#!/bin/bash
# quick-start.sh — Умный запуск RAG-системы

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.prebuilt.yml"

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка зависимостей
check_prerequisites() {
    log_info "Проверка зависимостей..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose не найден"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon не запущен"
        exit 1
    fi

    log_success "Docker готов"
}

# Настройка .env
setup_env() {
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env не найден, создаю из шаблона..."
        cp "${SCRIPT_DIR}/.env.example" "$ENV_FILE"

        echo ""
        log_info "Отредактируйте $ENV_FILE и укажите:"
        echo "  • CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_KEY"
        echo "  • CONFLUENCE_SPACE_NAME (ключ пространства)"
        echo ""
        read -p "Нажмите Enter после редактирования..."
    fi

    # Проверка обязательных переменных
    for var in CONFLUENCE_URL CONFLUENCE_API_KEY CONFLUENCE_SPACE_NAME; do
        if ! grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
            log_error "Отсутствует $var в $ENV_FILE"
            exit 1
        fi
    done

    log_success ".env настроен"
}

# Проверка/сборка образа
setup_image() {
    log_info "Проверка образа..."

    # Проверяем наличие pre-built образа
    if docker images -q llm-retrieval:prebuilt &> /dev/null; then
        log_success "Pre-built образ найден"
    else
        log_warn "Pre-built образ не найден, собираю..."
        docker-compose -f "$COMPOSE_FILE" build --pull

        if [ $? -ne 0 ]; then
            log_error "Сборка образа не удалась"
            exit 1
        fi
        log_success "Образ собран"
    fi
}

# Проверка/загрузка модели Ollama
setup_ollama() {
    local model="${OLLAMA_MODEL:-llama3.1}"
    log_info "Проверка модели Ollama: $model"

    # Проверяем через API
    if curl -s --max-time 5 http://localhost:11434/api/tags | grep -q "\"name\":\"$model"; then
        log_success "Модель $model уже загружена"
        return 0
    fi

    log_warn "Модель $model не найдена, запускаю загрузку..."
    log_info "Это займёт 5-20 минут в зависимости от интернета..."

    # Запускаем ollama и ждём готовности
    docker-compose -f "$COMPOSE_FILE" up -d ollama

    # Ждём готовности API
    for i in {1..60}; do
        if curl -s --max-time 2 http://localhost:11434/api/tags &> /dev/null; then
            break
        fi
        sleep 2
    done

    # Загружаем модель
    curl -X POST http://localhost:11434/api/pull \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$model\"}"

    log_success "Модель $model загружена"
}

# Проверка базы данных
check_database() {
    log_info "Проверка базы данных..."

    # Запускаем временный контейнер для проверки
    local count=$(docker-compose -f "$COMPOSE_FILE" run --rm app python3 -c \
        "from hybrid_search.database import Database; print(Database().collection.count())" 2>/dev/null || echo "0")

    if [ "$count" -gt 0 ]; then
        log_success "База данных содержит $count документов"
        return 0
    else
        log_warn "База данных пуста"
        return 1
    fi
}

# Предложение импорта базы
offer_import() {
    echo ""
    log_info "Варианты:"
    echo "  1) Начать с пустой базы и загрузить из Confluence"
    echo "  2) Импортировать базу из файла (export-db.sh)"
    echo "  3) Выйти и настроить вручную"
    echo ""
    read -p "Выберите вариант [1-3]: " -n 1 -r
    echo

    case $REPLY in
        1)
            log_info "Запуск с загрузкой из Confluence..."
            export FORCE_RELOAD=true
            export SKIP_LOAD=false
            ;;
        2)
            read -p "Укажите путь к архиву базы: " db_archive
            if [ -f "$db_archive" ]; then
                log_info "Импорт базы из $db_archive..."
                "${SCRIPT_DIR}/import-db.sh" "$db_archive"
                log_success "База импортирована"
            else
                log_error "Файл не найден: $db_archive"
                exit 1
            fi
            ;;
        3)
            log_info "Выход"
            exit 0
            ;;
        *)
            log_error "Неверный выбор"
            exit 1
            ;;
    esac
}

# Запуск сервисов
start_services() {
    log_info "Запуск сервисов..."

    # Запускаем зависимости
    docker-compose -f "$COMPOSE_FILE" up -d redis ollama

    # Ждём готовности
    log_info "Ожидание готовности зависимостей..."
    "${SCRIPT_DIR}/scripts/wait-for.sh" redis:6379 -t 30
    "${SCRIPT_DIR}/scripts/wait-for.sh" ollama:11434 -t 60

    # Запускаем app
    docker-compose -f "$COMPOSE_FILE" up -d app

    log_success "Сервисы запущены"
}

# Подключение к интерактивному режиму
interactive_mode() {
    echo ""
    log_success "🎯 RAG-система готова!"
    echo ""
    echo "Команды:"
    echo "  • Введите вопрос для поиска по документации"
    echo "  • /clear — очистить историю"
    echo "  • /exit — выйти"
    echo "  • /sync — принудительная синхронизация"
    echo ""

    read -p "Подключиться к интерактивному режиму? [Y/n]: " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]] || [ -z "$REPLY" ]; then
        log_info "Подключение..."
        docker-compose -f "$COMPOSE_FILE" exec -it app python3 main.py
    else
        log_info "Сервисы работают в фоне"
        log_info "Для подключения позже: docker-compose exec -it app python3 main.py"
    fi
}

# Основная функция
main() {
    echo "🚀 Quick Start: RAG-система для документации"
    echo "=============================================="
    echo ""

    check_prerequisites
    setup_env
    setup_image
    setup_ollama

    if ! check_database; then
        offer_import
    fi

    start_services
    interactive_mode

    echo ""
    log_success "Готово! Удачной работы! 🎉"
}

# Запуск
main "$@"