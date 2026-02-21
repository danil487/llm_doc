# 🚀 Enhanced LLM Retrieval System (RAG)

**Система интеллектуального поиска по документации Confluence с использованием RAG (Retrieval-Augmented Generation)**

---

## 📋 Оглавление

- [О проекте](#-о-проекте)
- [Архитектура](#-архитектура)
- [Быстрый старт](#-быстрый-старт)
- [Конфигурация](#-конфигурация)
- [Переменные окружения](#-переменные-окружения)
- [Использование](#-использование)
- [Режимы работы](#-режимы-работы)
- [Мониторинг и отладка](#-мониторинг-и-отладка)
- [Troubleshooting](#-troubleshooting)
- [Производительность](#-производительность)

---

## 📖 О проекте

Система предоставляет AI-ассистента для поиска ответов в документации Confluence с использованием:

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **Поиск** | Hybrid Search (Dense + Sparse) | Векторный + BM25 поиск |
| **Ранжирование** | Cross-Encoder Reranker | Точное ранжирование результатов |
| **Генерация** | Ollama (Llama 3.1) | Генерация ответов на естественном языке |
| **Хранение** | ChromaDB | Векторная база данных |
| **Кэш** | Redis | История диалогов, метаданные |
| **Интерфейс** | Telegram Bot + CLI | Удобное взаимодействие |

### ✨ Ключевые возможности

- 🔍 **Гибридный поиск** — комбинация семантического и keyword поиска
- 🎯 **Reranking** — cross-encoder для точного ранжирования
- 🔗 **Расширение контекста** — добавление соседних чанков
- 🔄 **Авто-синхронизация** — периодическое обновление изменённых страниц
- 💬 **История диалогов** — сохранение контекста беседы
- 📱 **Telegram бот** — доступ из мессенджера

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        Пользователь                              │
│              (Telegram Bot / CLI интерфейс)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ AppController│  │BotController │  │SyncController│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       RAG Pipeline                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │SemanticSearch│  │    RAG       │  │   Response   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Components                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   ChromaDB   │  │    Embed     │  │   Confluence │          │
│  │  (Vector DB) │  │ (Embeddings) │  │    API       │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Infrastructure                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Redis     │  │   Ollama     │  │    Docker    │          │
│  │  (Session)   │  │    (LLM)     │  │  Container   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Быстрый старт

### 1. Требования

| Компонент | Версия | Примечание |
|-----------|--------|------------|
| Docker | 20.10+ | Обязательно |
| Docker Compose | 2.0+ | Рекомендуется v2 |
| NVIDIA GPU | Опционально | Для ускорения (CUDA 11+) |
| RAM | 8GB+ | 16GB рекомендуется |
| Disk | 10GB+ | Для векторной базы |

### 2. Клонирование и настройка

```bash
# Клонирование репозитория
git clone <repository-url>
cd enhanced-llm-retrieval

# Копирование шаблона конфигурации
cp .env.example .env

# Редактирование конфигурации
nano .env  # или ваш любимый редактор
```

### 3. Минимальная конфигурация (.env)

```bash
# ===== Confluence (ОБЯЗАТЕЛЬНО) =====
CONFLUENCE_URL=https://your-confluence.com
CONFLUENCE_API_KEY=your_api_token
CONFLUENCE_SPACE_NAME=YOUR_SPACE

# ===== Telegram Bot (ОПЦИОНАЛЬНО) =====
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token

# ===== Ollama =====
OLLAMA_MODEL=llama3.1
OLLAMA_HOST=http://ollama:11434
```

### 4. Запуск

```bash
# CPU режим (по умолчанию)
./start.sh

# GPU режим (требуется NVIDIA GPU)
./start.sh --gpu

# С пересборкой образов
./start.sh --rebuild

# Полная пересборка без кэша
./start.sh --no-cache
```

### 5. Проверка статуса

```bash
# Статус контейнеров
docker compose ps

# Логи приложения
docker compose logs -f app

# Логи Ollama
docker compose logs -f ollama

# Вход в контейнер
docker compose exec app bash
```

### 6. Остановка

```bash
# Мягкая остановка
./stop.sh

# Полная остановка с удалением
./stop.sh --down

# Остановка с очисткой данных
./stop.sh --clean
```

---

## ⚙️ Конфигурация

### Переменные окружения

#### 📊 Таблица влияния переменных на производительность и качество

| Категория | Переменная | Значение по умолчанию | Влияние | Рекомендации |
|-----------|------------|----------------------|---------|--------------|
| **Загрузка** | `FORCE_RELOAD` | `false` | Полная переиндексация базы | `true` только при изменении схемы |
| **Загрузка** | `SKIP_LOAD` | `false` | Пропуск индексации при старте | `true` если база уже готова |
| **Загрузка** | `ENABLE_PERIODIC_SYNC` | `true` | Авто-обновление изменённых страниц | `true` для актуальности данных |
| **Поиск** | `RETRIEVAL_TOP_K` | `20` | Количество кандидатов для поиска | ↑ = больше контекста, ↓ = быстрее |
| **Ранжирование** | `RERANK_TOP_K` | `15` | Количество после reranking | 10-20 оптимально |
| **Ранжирование** | `RERANK_MIN_SCORE` | `0.3` | Порог отсечения reranker | ↑ = качественнее, ↓ = больше результатов |
| **Ранжирование** | `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Модель для reranking | MiniLM — баланс скорость/качество |
| **Контекст** | `MAX_CONTEXT_TOKENS` | `2048` | Максимум токенов в промпте | ↑ = больше контекста, ↑ = дороже |
| **Контекст** | `INCLUDE_SECTION_IN_PROMPT` | `true` | Включать разделы в промпт | `true` для лучшей навигации |
| **Контекст** | `SEARCH_NEIGHBOR_WINDOW` | `1` | Количество соседних чанков | 1-2 оптимально для связности |
| **Контекст** | `SEARCH_NEIGHBOR_SCORE_MULTIPLIER` | `0.8` | Вес соседних чанков | 0.5-0.9 |
| **Ответ** | `RESPONSE_FORMAT` | `markdown` | Формат ответа | `markdown` или `plain` |
| **Ответ** | `ALWAYS_SHOW_SOURCES` | `true` | Показывать источники | `true` для прозрачности |
| **Ответ** | `MAX_SOURCE_LINKS` | `3` | Максимум ссылок в ответе | 3-5 оптимально |
| **ChromaDB** | `CHROMA_DB_PATH` | `/app/data/chroma_db` | Путь к базе данных | Не менять без необходимости |
| **ChromaDB** | `CHROMA_COLLECTION` | `confluence_index` | Имя коллекции | Уникальное для проекта |
| **Confluence** | `CONFLUENCE_URL` | — | URL Confluence | Обязательно |
| **Confluence** | `CONFLUENCE_API_KEY` | — | API токен | Обязательно |
| **Confluence** | `CONFLUENCE_SPACE_NAME` | — | Ключ пространства | Обязательно |
| **Ollama** | `OLLAMA_MODEL` | `llama3.1` | Модель для генерации | llama3.1, mistral, mixtral |
| **Ollama** | `OLLAMA_HOST` | `http://ollama:11434` | Хост Ollama | Не менять в Docker |
| **Redis** | `REDIS_HOST` | `redis` | Хост Redis | Не менять в Docker |
| **Redis** | `REDIS_PORT` | `6379` | Порт Redis | Не менять в Docker |
| **Redis** | `REDIS_TTL_SECONDS` | `3600` | Время жизни сессии | 3600-86400 |
| **Telegram** | `TELEGRAM_ENABLED` | `false` | Включить бота | `true` для продакшена |
| **Telegram** | `TELEGRAM_BOT_TOKEN` | — | Токен бота | Обязательно если включён |
| **Telegram** | `TELEGRAM_WEBHOOK_URL` | — | URL webhook | Пусто = polling режим |
| **Система** | `FORCE_CPU` | `false` | Принудительный CPU | `true` если нет GPU |
| **Система** | `LOG_LEVEL` | `INFO` | Уровень логирования | `DEBUG` для отладки |
| **Система** | `TOKENIZERS_PARALLELISM` | `true` | Параллелизм токенизатора | `true` для производительности |

#### 📈 Влияние на производительность

```
┌────────────────────────────────────────────────────────────────┐
│                    ПАРАМЕТРЫ ПРОИЗВОДИТЕЛЬНОСТИ                 │
├────────────────────────────────────────────────────────────────┤
│  RETRIEVAL_TOP_K ↑  →  Поиск медленнее, но больше кандидатов   │
│  RERANK_TOP_K ↑     →  Reranking медленнее, но точнее         │
│  MAX_CONTEXT_TOKENS ↑ →  Больше контекста, дороже генерация   │
│  SEARCH_NEIGHBOR_WINDOW ↑ →  Больше чанков, лучше связность   │
├────────────────────────────────────────────────────────────────┤
│  Рекомендации для продакшена:                                  │
│  • RETRIEVAL_TOP_K = 20-30                                     │
│  • RERANK_TOP_K = 10-15                                        │
│  • MAX_CONTEXT_TOKENS = 2048-4096                              │
│  • SEARCH_NEIGHBOR_WINDOW = 1-2                                │
└────────────────────────────────────────────────────────────────┘
```

#### 🎯 Влияние на качество ответов

```
┌────────────────────────────────────────────────────────────────┐
│                    ПАРАМЕТРЫ КАЧЕСТВА                           │
├────────────────────────────────────────────────────────────────┤
│  RERANK_MIN_SCORE ↑  →  Меньше результатов, но качественнее   │
│  ALWAYS_SHOW_SOURCES = true →  Прозрачность ответов           │
│  INCLUDE_SECTION_IN_PROMPT = true →  Лучшая навигация         │
├────────────────────────────────────────────────────────────────┤
│  Рекомендации для качества:                                    │
│  • RERANK_MIN_SCORE = 0.3-0.5                                  │
│  • ALWAYS_SHOW_SOURCES = true                                  │
│  • MAX_SOURCE_LINKS = 3-5                                      │
└────────────────────────────────────────────────────────────────┘
```

---

## 💻 Использование

### CLI интерфейс

```bash
# После запуска системы
docker compose exec app bash

# Внутри контейнера
❓ Ваш вопрос: Как настроить аутентификацию?

🔍 Поиск...
🤖 Ответ:
------------------------------------------------------------
Для настройки аутентификации выполните следующие шаги:
1. Откройте настройки безопасности
2. Выберите метод аутентификации
3. Сохраните изменения
------------------------------------------------------------

📎 Источники:
   1. 238485654 (score: 0.9234)
   2. 238485655 (score: 0.8765)
   3. 238485656 (score: 0.8234)
```

### Команды CLI

| Команда | Описание |
|---------|----------|
| `/clear` | Очистить историю диалога |
| `/exit`, `/quit`, `/q` | Выход из системы |
| `/help` | Показать справку |
| `/sync` | Принудительная синхронизация |

### Telegram бот

| Команда | Описание |
|---------|----------|
| `/start` | Начать диалог |
| `/clear` | Очистить историю |
| `/help` | Показать справку |
| `/status` | Статус системы |

**Просто отправьте вопрос боту** — он найдёт ответ в документации.

---

## 🔧 Режимы работы

### 1. CPU режим (по умолчанию)

```bash
./start.sh
```

- ✅ Работает на любом сервере
- ⚠️ Медленнее (особенно embedding и reranking)
- 💡 Рекомендуется для тестирования

### 2. GPU режим

```bash
./start.sh --gpu
```

- ✅ Быстрее в 5-10 раз
- ⚠️ Требуется NVIDIA GPU + nvidia-container-toolkit
- 💡 Рекомендуется для продакшена

**Проверка GPU:**

```bash
# Проверка доступности GPU
docker compose exec app python -c "import torch; print(torch.cuda.is_available())"

# Информация о GPU
docker compose exec app nvidia-smi
```

### 3. Режим отладки

```bash
# В .env
LOG_LEVEL=DEBUG
FORCE_CPU=true

# Запуск
./start.sh --rebuild
```

---

## 📊 Мониторинг и отладка

### Логи

```bash
# Логи приложения (real-time)
docker compose logs -f app

# Логи Ollama
docker compose logs -f ollama

# Логи Redis
docker compose logs -f redis

# Последние 100 строк
docker compose logs --tail=100 app
```

### Статус системы

```bash
# Через Telegram бота
/status

# Через CLI
docker compose exec app python -c "from hybrid_search.database import Database; print(Database().count())"
```

### Метрики производительности

```bash
# Время ответа Ollama
docker compose logs app | grep "Ollama"

# Время поиска
docker compose logs app | grep "Поиск"

# Количество документов
docker compose logs app | grep "документов"
```

---

## 🔴 Troubleshooting

### Проблема: Бот не отвечает

**Причины:**
1. Неправильный токен Telegram
2. Бот в Process вместо Thread (конфликт singleton)
3. Webhook без HTTPS

**Решение:**

```bash
# Проверка токена
docker compose logs app | grep "Telegram"

# Использование polling (рекомендуется)
TELEGRAM_WEBHOOK_URL=  # оставить пустым

# Перезапуск бота
docker compose restart app
```

### Проблема: Ollama модель не найдена

**Решение:**

```bash
# Проверка доступных моделей
docker compose exec ollama ollama list

# Загрузка модели
docker compose exec ollama ollama pull llama3.1

# Проверка в логах
docker compose logs app | grep "Ollama"
```

### Проблема: Confluence 401/403

**Причины:**
1. Неверный API ключ
2. Нет прав доступа к пространству

**Решение:**

```bash
# Проверка подключения
docker compose exec app python -c "
from hybrid_search.confluence import ConfluenceAPI
api = ConfluenceAPI()
print(api.get_space_id())
"

# Проверка токена
echo $CONFLUENCE_API_KEY
```

### Проблема: Медленный поиск

**Решение:**

```bash
# Включить GPU
FORCE_CPU=false

# Уменьшить TOP_K
RETRIEVAL_TOP_K=10
RERANK_TOP_K=5

# Проверка устройства
docker compose logs app | grep "Устройство"
```

### Проблема: Недостаточно памяти

**Решение:**

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 16G  # увеличить лимит
```

```bash
# Очистка кэша
docker compose exec app rm -rf /app/.cache/*

# Пересборка
./start.sh --no-cache
```

---

## ⚡ Производительность

### Бенчмарки (ориентировочные)

| Операция | CPU | GPU | Ускорение |
|----------|-----|-----|-----------|
| Embedding (1 чанк) | 50ms | 5ms | 10x |
| Reranking (20 чанков) | 500ms | 50ms | 10x |
| Генерация ответа | 3000ms | 1000ms | 3x |
| **Всего запрос** | **~4с** | **~1с** | **4x** |

### Оптимизация

```bash
# 1. Включить батчинг
TOKENIZERS_PARALLELISM=true

# 2. Использовать GPU
FORCE_CPU=false

# 3. Оптимизировать параметры
RETRIEVAL_TOP_K=20      # не больше 30
RERANK_TOP_K=15         # не больше 20
MAX_CONTEXT_TOKENS=2048 # баланс качество/скорость
```

### Масштабирование

```yaml
# Для продакшена увеличить ресурсы
deploy:
  resources:
    limits:
      memory: 16G
      cpus: '4'
    reservations:
      memory: 8G
      cpus: '2'
```

---

## 📁 Структура проекта

```
enhanced-llm-retrieval/
├── controllers/              # Контроллеры приложения
│   ├── app_controller.py     # Основной контроллер
│   ├── bot_controller.py     # Telegram бот
│   └── sync_controller.py    # Синхронизация
├── hybrid_search/            # Поиск и индексация
│   ├── chunk.py              # Чанкинг текста
│   ├── confluence.py         # Confluence API
│   ├── database.py           # ChromaDB
│   ├── embed.py              # Embeddings + Reranker
│   ├── search.py             # Поиск
│   ├── update.py             # Обновление базы
│   └── utils.py              # Утилиты + Config
├── rag_llm/                  # LLM компоненты
│   ├── model.py              # Ollama клиент
│   ├── rag.py                # RAG логика
│   └── response.py           # Генерация ответов
├── telegram_bot/             # Telegram бот
│   └── bot.py                # Бот логика
├── docker/                   # Docker файлы
│   ├── Dockerfile
│   └── entrypoint.sh
├── main.py                   # Точка входа
├── requirements.txt          # Зависимости
├── docker-compose.yml        # Docker Compose
├── docker-compose.gpu.yml    # GPU конфигурация
├── start.sh                  # Скрипт запуска
├── stop.sh                   # Скрипт остановки
└── .env                      # Конфигурация
```

---

## 🔐 Безопасность

### Рекомендации

1. **API ключи** — хранить в `.env`, не коммитить в git
2. **Redis** — не открывать порт 6379 наружу
3. **Telegram Webhook** — использовать только с HTTPS
4. **Confluence** — ограничить права API токена

### .env в .gitignore

```bash
# .gitignore
.env
*.log
__pycache__/
*.pyc
data/
logs/
```

---

## 📞 Поддержка

### Логи для отладки

```bash
# Полные логи с начала
docker compose logs app > app.log

# Только ошибки
docker compose logs app | grep "❌\|Error\|Exception" > errors.log
```

### Полезные команды

```bash
# Проверка здоровья сервисов
docker compose ps

# Перезапуск отдельного сервиса
docker compose restart app

# Очистка и пересоздание
docker compose down --volumes
docker compose up -d

# Вход в контейнер для отладки
docker compose exec app bash

# Проверка базы данных
docker compose exec app python -c "
from hybrid_search.database import Database
db = Database()
print(f'Документов: {db.count()}')
"
```

---

## 📄 Лицензия

MIT License — свободное использование и модификация.

---

## 🎯 Чеклист перед продакшеном

- [ ] `.env` настроен с правильными значениями
- [ ] `CONFLUENCE_API_KEY` действителен
- [ ] `TELEGRAM_BOT_TOKEN` установлен (если нужен бот)
- [ ] GPU доступен (если требуется производительность)
- [ ] `LOG_LEVEL=INFO` (не DEBUG)
- [ ] `ENABLE_PERIODIC_SYNC=true` для авто-обновления
- [ ] Резервное копирование `chroma-data` настроено
- [ ] Мониторинг ресурсов настроен
- [ ] `.env` добавлен в `.gitignore`

---

**🚀 Система готова к использованию!**