# 🚀 Enhanced LLM Retrieval System (RAG) — Parent-Child версия

**Система интеллектуального поиска по документации Confluence с использованием RAG (Retrieval-Augmented Generation) и Parent-Child чанкинга**

---

## 📋 Оглавление

- [О проекте](#-о-проекте)
- [Ключевые особенности](#-ключевые-особенности)
- [Архитектура Parent-Child поиска](#-архитектура-parent-child-поиска)
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

Система предоставляет AI-ассистента для поиска ответов в документации Confluence. В отличие от традиционных RAG-решений, здесь реализован **Parent-Child подход**, который сочетает точность поиска по мелким чанкам и полноту контекста за счёт возврата целых родительских документов.

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **Поиск** | Hybrid Search (Dense + Sparse) | Векторный + BM25 поиск |
| **Ранжирование** | Cross-Encoder Reranker | Точное ранжирование child-чанков |
| **Генерация** | Ollama или внешние API (OpenRouter, DeepSeek, Qwen) | Генерация ответов |
| **Хранение** | ChromaDB | Векторная база данных (child-чанки) |
| **Кэш** | Redis | История диалогов, метаданные |
| **Интерфейс** | Telegram Bot + CLI | Удобное взаимодействие |

---

## ✨ Ключевые особенности

- **Parent-Child чанкинг** – документы делятся на мелкие child-чанки (250 токенов) для точного поиска, но в ответ возвращаются полные родительские блоки (до 2000 токенов), что обеспечивает связность контекста.
- **Гибридный поиск** – комбинация dense-эмбеддингов (`intfloat/multilingual-e5-large`) и BM25.
- **Reranking** – cross-encoder (`BAAI/bge-reranker-v2-m3`) отсеивает нерелевантные child-чанки.
- **Динамический порог** – `CHILD_MIN_SCORE` настраивается для баланса между полнотой и точностью.
- **Поддержка нескольких LLM-провайдеров** – можно использовать Ollama (локально) или облачные API (OpenRouter, DeepSeek, Qwen).
- **Авто-синхронизация** – периодическое обновление изменённых страниц Confluence.
- **История диалогов** – сохраняется в Redis для поддержания контекста беседы.
- **Telegram бот** – доступ из мессенджера с индикацией "печатает..." во время длительных операций.

---

## 🏗️ Архитектура Parent-Child поиска

```
┌─────────────────────────────────────────────────────────────────┐
│                        Пользователь                              │
│              (Telegram Bot / CLI интерфейс)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SemanticSearch                              │
│  1. Поиск child-чанков (dense + sparse)                         │
│  2. Reranking child-чанков                                       │
│  3. Фильтрация по CHILD_MIN_SCORE                                │
│  4. Группировка child → parent                                   │
│  5. Возврат parent-блоков (до MAX_PARENT_BLOCKS)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                           RAG                                     │
│  • Формирование промпта с parent-текстами                       │
│  • Добавление истории диалога                                    │
│  • Вызов LLM (Ollama / API)                                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Components                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   ChromaDB   │  │    Embed     │  │   Confluence │          │
│  │ (child-чанки)│  │ (embeddings, │  │    API       │          │
│  │              │  │   reranker)  │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Детали Parent-Child чанкинга

1. **Child-чанки** – маленькие фрагменты (по умолчанию 250 токенов, overlap 30) для точного семантического поиска. Именно они индексируются в ChromaDB.
2. **Parent-блоки** – крупные смысловые блоки (2000 токенов, overlap 200), которые возвращаются в качестве контекста для LLM. Каждый child-чанк хранит ссылку на свой родительский блок и его полный текст.
3. **При поиске** – находятся релевантные child-чанки, они ранжируются, фильтруются, затем группируются по родителям, и только родительские тексты отправляются в промпт. Это даёт:
   - Высокую точность поиска (за счёт мелких чанков)
   - Полноту контекста (за счёт возврата целых разделов)
   - Экономию токенов (вместо множества мелких чанков в промпт попадают несколько цельных документов)

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

# ===== Выбор LLM провайдера =====
# Вариант 1: Ollama (локально)
USE_LLM_API=false
OLLAMA_MODEL=llama3.1
OLLAMA_HOST=http://ollama:11434

# Вариант 2: OpenRouter (пример)
USE_LLM_API=true
LLM_API_KEY=your_openrouter_key
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat
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

#### 📊 Основные параметры

| Категория | Переменная | По умолчанию | Описание |
|-----------|------------|--------------|----------|
| **Confluence** | `CONFLUENCE_URL` | — | URL вашего Confluence |
| | `CONFLUENCE_API_KEY` | — | API токен (Personal Access Token) |
| | `CONFLUENCE_SPACE_NAME` | — | Ключ пространства для индексации |
| **LLM (Ollama)** | `USE_LLM_API` | `false` | `false` – использовать Ollama, `true` – внешний API |
| | `OLLAMA_MODEL` | `llama3.1` | Модель в Ollama |
| | `OLLAMA_HOST` | `http://ollama:11434` | Адрес сервера Ollama |
| **LLM (внешний API)** | `LLM_API_KEY` | — | Ключ API (OpenRouter, DeepSeek, Qwen) |
| | `LLM_API_BASE` | — | Базовый URL API |
| | `LLM_MODEL` | — | Имя модели (например, `deepseek-chat`) |
| | `LLM_TEMPERATURE` | `0.7` | Температура генерации (0.0–1.0) |
| | `LLM_MAX_TOKENS` | `2048` | Максимум токенов в ответе |
| | `LLM_TIMEOUT` | `120` | Таймаут запроса в секундах |
| **ChromaDB** | `CHROMA_DB_PATH` | `/app/data/chroma_db` | Путь к базе данных |
| | `CHROMA_COLLECTION` | `confluence_index` | Имя коллекции |
| **Redis** | `REDIS_HOST` | `redis` | Хост Redis |
| | `REDIS_PORT` | `6379` | Порт Redis |
| | `REDIS_DB` | `0` | Номер базы данных |
| | `REDIS_TTL_SECONDS` | `3600` | Время жизни сессии |
| **Parent-Child чанкинг** | `CHILD_CHUNK_SIZE` | `250` | Размер child-чанков (для поиска) |
| | `CHILD_CHUNK_OVERLAP` | `30` | Перекрытие child-чанков |
| | `PARENT_BLOCK_SIZE` | `2000` | Размер родительских блоков (для контекста) |
| | `PARENT_CHUNK_OVERLAP` | `200` | Перекрытие родительских блоков |
| | `CHILDREN_PER_PARENT` | `8` | Макс. child-чанков в одном parent |
| | `MAX_PARENT_BLOCKS` | `4` | Макс. родительских блоков в контексте |
| | `CHILD_MIN_SCORE` | `0.51` | Минимальный score child-чанка (после rerank) |
| **Поиск** | `RETRIEVAL_TOP_K` | `20` | Количество child-кандидатов (умножается на 3 при поиске) |
| | `RERANK_TOP_K` | `8` | Количество финальных parent-блоков |
| | `RERANK_MIN_SCORE` | `0.43` | Порог для child-чанков до rerank (не используется напрямую) |
| | `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Модель для reranking |
| | `DENSE_MODEL` | `intfloat/multilingual-e5-large` | Модель для эмбеддингов |
| | `MAX_CONTEXT_TOKENS` | `8000` | Лимит токенов в промпте |
| **Форматирование** | `TABLE_FORMAT` | `markdown` | Формат таблиц в ответе |
| | `INCLUDE_HEADERS_IN_CHUNKS` | `true` | Включать заголовки в чанки |
| | `MAX_HEADER_DEPTH` | `3` | Максимальная глубина заголовков |
| **Telegram** | `TELEGRAM_ENABLED` | `false` | Включить Telegram бота |
| | `TELEGRAM_BOT_TOKEN` | — | Токен бота |
| | `TELEGRAM_WEBHOOK_URL` | — | URL для webhook (пусто = polling) |
| | `TELEGRAM_WEBHOOK_PORT` | `8443` | Порт для webhook |
| **Синхронизация** | `FORCE_RELOAD` | `false` | Принудительная полная переиндексация |
| | `SKIP_LOAD` | `false` | Пропустить загрузку при старте |
| | `ENABLE_PERIODIC_SYNC` | `false` | Включить фоновую синхронизацию |
| **Системные** | `LOG_LEVEL` | `INFO` | Уровень логирования |
| | `FORCE_CPU` | `false` | Принудительно использовать CPU |
| | `TOKENIZERS_PARALLELISM` | `true` | Параллелизм токенизатора |

#### 📈 Влияние ключевых параметров на производительность

```
┌────────────────────────────────────────────────────────────────┐
│  CHILD_CHUNK_SIZE ↓ → точнее поиск, но больше чанков           │
│  PARENT_BLOCK_SIZE ↑ → больше контекста, но больше токенов    │
│  CHILD_MIN_SCORE ↑ → меньше шума, но возможна потеря          │
│  RETRIEVAL_TOP_K ↑ → медленнее, но больше кандидатов          │
│  MAX_PARENT_BLOCKS ↑ → больше контекста, дороже генерация     │
├────────────────────────────────────────────────────────────────┤
│  Рекомендации для продакшена:                                  │
│  • CHILD_MIN_SCORE = 0.5–0.6 (после настройки)                │
│  • RETRIEVAL_TOP_K = 20                                        │
│  • MAX_PARENT_BLOCKS = 3–5                                     │
│  • CHILD_CHUNK_SIZE = 200–300                                  │
└────────────────────────────────────────────────────────────────┘
```

#### 🎯 Примеры конфигурации для разных LLM-провайдеров

**DeepSeek API:**
```ini
USE_LLM_API=true
LLM_API_KEY=sk-...
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=1024
```

**Qwen (DashScope):**
```ini
USE_LLM_API=true
LLM_API_KEY=sk-...
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

**OpenRouter (агрегатор):**
```ini
USE_LLM_API=true
LLM_API_KEY=sk-or-...
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

---

## 💻 Использование

### CLI интерфейс

```bash
# После запуска системы
docker compose exec app bash

# Внутри контейнера
❓ Ваш вопрос: Как завести дефекты в журнале осмотра?

🔍 Поиск...
🤖 Ответ:
------------------------------------------------------------
Для заведения дефектов в журнале осмотра выполните шаги:
1. Откройте вкладку "Дефекты" в карточке осмотра
2. Нажмите "Добавить дефект"
3. Заполните поля: адрес, название, описание
4. Приложите документы и фотографии
5. Сохраните запись
------------------------------------------------------------

📎 Источники:
   1. Строительный контроль. Промежуточная приемка (score: 0.5072)
   2. Инструкция по работе с журналом осмотров (score: 0.5009)
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

**Просто отправьте вопрос боту** — он найдёт ответ в документации. Во время длительной обработки (поиск, rerank, генерация) бот будет показывать статус "печатает...", обновляя его каждые 5 секунд.

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
# Время ответа LLM
docker compose logs app | grep "Ollama"

# Время поиска
docker compose logs app | grep "Поиск"

# Количество документов
docker compose logs app | grep "документов"

# Статистика Parent-Child поиска
docker compose logs app | grep "Parent-Child поиск"
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

# Уменьшить TOP_K и увеличить порог
RETRIEVAL_TOP_K=15
RERANK_TOP_K=5
CHILD_MIN_SCORE=0.55

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

### Проблема: В контекст попадает много шума

**Решение:**
- Повысьте `CHILD_MIN_SCORE` (например, до 0.55–0.6)
- Уменьшите `MAX_PARENT_BLOCKS` до 2–3
- Проверьте, есть ли в метаданных поле для фильтрации (например, `content_type`), и при необходимости добавьте `where` в поиск

---

## ⚡ Производительность

### Бенчмарки (ориентировочные для 4 ГБ VRAM)

| Операция | CPU | GPU | Ускорение |
|----------|-----|-----|-----------|
| Embedding (1 child-чанк) | 50ms | 5ms | 10x |
| Reranking (20 child-чанков) | 500ms | 50ms | 10x |
| Генерация ответа (llama3.1:8b) | 3000ms | 1000ms | 3x |
| **Полный цикл** | **~4с** | **~1с** | **4x** |

### Оптимизация для слабых GPU (4 ГБ)

```ini
# Перенести reranker на CPU (освободить VRAM)
RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
# или оставить на CPU, установив в коде device='cpu'

# Уменьшить количество кандидатов
RETRIEVAL_TOP_K=15
RERANK_TOP_K=5
CHILD_MIN_SCORE=0.55

# Использовать меньшую LLM
OLLAMA_MODEL=llama3.2:3b-instruct-q4_K_M
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
│   ├── chunk.py              # Parent-Child чанкинг
│   ├── confluence.py         # Confluence API
│   ├── database.py           # ChromaDB (с поддержкой child-parent)
│   ├── embed.py              # Embeddings + Reranker
│   ├── search.py             # Parent-Child поиск
│   ├── update.py             # Обновление базы (Parent-Child)
│   └── utils.py              # Утилиты + Config
├── rag_llm/                  # LLM компоненты
│   ├── model.py              # Клиент для Ollama / внешних API
│   ├── rag.py                # RAG логика (с дедупликацией)
│   └── response.py           # Генерация ответов
├── telegram_bot/             # Telegram бот
│   └── bot.py                # Бот логика с длительным "печатает..."
├── docker/                   # Docker файлы
│   ├── Dockerfile
│   └── entrypoint.sh
├── main.py                   # Точка входа
├── requirements.txt          # Зависимости
├── docker-compose.yml        # Docker Compose
├── docker-compose.gpu.yml    # GPU конфигурация
├── start.sh                  # Скрипт запуска
├── stop.sh                   # Скрипт остановки
└── .env.example              # Шаблон конфигурации
```

---

## 🔐 Безопасность

### Рекомендации

1. **API ключи** — хранить в `.env`, не коммитить в git. Использовать `.env.example` с заглушками.
2. **Redis** — не открывать порт 6379 наружу.
3. **Telegram Webhook** — использовать только с HTTPS.
4. **Confluence** — ограничить права API токена (только чтение).
5. **Регулярно отзывать старые токены** при утечке.

### .gitignore

```gitignore
.env
*.log
__pycache__/
*.pyc
data/
logs/
.cache/
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

# Тестирование поиска с новыми параметрами
docker compose exec app python test_search.py "ваш запрос"
```

---

## 📄 Лицензия

MIT License — свободное использование и модификация.

---

## 🎯 Чеклист перед продакшеном

- [ ] `.env` настроен с правильными значениями (токены заменены на заглушки в репозитории)
- [ ] `CONFLUENCE_API_KEY` действителен и имеет права только на чтение
- [ ] `TELEGRAM_BOT_TOKEN` установлен (если нужен бот)
- [ ] GPU доступен (если требуется производительность)
- [ ] `LOG_LEVEL=INFO` (не DEBUG)
- [ ] `ENABLE_PERIODIC_SYNC=true` для авто-обновления
- [ ] Резервное копирование `chroma-data` настроено
- [ ] Мониторинг ресурсов настроен
- [ ] `.env` добавлен в `.gitignore`
- [ ] Проведено тестирование с реальными запросами (например, через `test_search.py`)

---

**🚀 Система готова к использованию!**