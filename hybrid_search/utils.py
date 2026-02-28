# hybrid_search/utils.py
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """✅ Централизованная конфигурация RAG-пайплайна (Parent-Child)"""

    # ===== Confluence =====
    CONFLUENCE_URL: str = os.getenv("CONFLUENCE_URL", "").rstrip('/')
    CONFLUENCE_API_KEY: str = os.getenv("CONFLUENCE_API_KEY", "")
    CONFLUENCE_SPACE_NAME: str = os.getenv("CONFLUENCE_SPACE_NAME", "")

    # ===== LLM Provider =====
    USE_LLM_API: bool = os.getenv("USE_LLM_API", "false").lower() == "true"
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))

    # ===== Ollama =====
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")

    # ===== ChromaDB =====
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "/app/data/chroma_db")
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "confluence_index")

    # ===== Redis =====
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_TTL_SECONDS: int = int(os.getenv("REDIS_TTL_SECONDS", "3600"))

    # ===== Parent-Child Retrieval =====
    CHILD_CHUNK_SIZE: int = int(os.getenv("CHILD_CHUNK_SIZE", "250"))
    CHILD_CHUNK_OVERLAP: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "30"))
    PARENT_BLOCK_SIZE: int = int(os.getenv("PARENT_BLOCK_SIZE", "2000"))
    PARENT_CHUNK_OVERLAP: int = int(os.getenv("PARENT_CHUNK_OVERLAP", "200"))
    CHILDREN_PER_PARENT: int = int(os.getenv("CHILDREN_PER_PARENT", "8"))
    MAX_PARENT_BLOCKS: int = int(os.getenv("MAX_PARENT_BLOCKS", "4"))
    CHILD_MIN_SCORE: float = float(os.getenv("CHILD_MIN_SCORE", "0.30"))

    # ===== RAG Pipeline =====
    FORCE_CPU: bool = os.getenv("FORCE_CPU", "false").lower() == "true"
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "20"))
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "12"))
    RERANK_MIN_SCORE: float = float(os.getenv("RERANK_MIN_SCORE", "0.35"))
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-large")
    DENSE_MODEL: str = os.getenv("DENSE_MODEL", "sentence-transformers/all-mpnet-base-v2")

    MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
    INCLUDE_SECTION_IN_PROMPT: bool = os.getenv("INCLUDE_SECTION_IN_PROMPT", "true").lower() == "true"
    RESPONSE_FORMAT: str = os.getenv("RESPONSE_FORMAT", "markdown")
    ALWAYS_SHOW_SOURCES: bool = os.getenv("ALWAYS_SHOW_SOURCES", "true").lower() == "true"
    MAX_SOURCE_LINKS: int = int(os.getenv("MAX_SOURCE_LINKS", "3"))

    # ===== Структура контента =====
    TABLE_FORMAT: str = os.getenv("TABLE_FORMAT", "markdown")
    INCLUDE_HEADERS_IN_CHUNKS: bool = os.getenv("INCLUDE_HEADERS_IN_CHUNKS", "true").lower() == "true"
    MAX_HEADER_DEPTH: int = int(os.getenv("MAX_HEADER_DEPTH", "3"))

    # ===== Telegram Bot =====
    TELEGRAM_ENABLED: bool = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    TELEGRAM_WEBHOOK_PORT: int = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443"))

    # ===== Синхронизация =====
    FORCE_RELOAD: bool = os.getenv("FORCE_RELOAD", "false").lower() == "true"
    SKIP_LOAD: bool = os.getenv("SKIP_LOAD", "false").lower() == "true"
    ENABLE_PERIODIC_SYNC: bool = os.getenv("ENABLE_PERIODIC_SYNC", "true").lower() == "true"

    # ===== Логирование =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def log(cls):
        """Логирование текущей конфигурации"""
        logger.info("📋 RAG Pipeline Config (Parent-Child):")
        logger.info(f"   • Confluence: {cls.CONFLUENCE_URL}/{cls.CONFLUENCE_SPACE_NAME}")
        logger.info(f"   • ChromaDB: {cls.CHROMA_DB_PATH}/{cls.CHROMA_COLLECTION}")

        if cls.USE_LLM_API:
            logger.info(f"   • 🌐 LLM API: {cls.LLM_MODEL} @ {cls.LLM_API_BASE}")
        else:
            logger.info(f"   • 🖥️  Ollama: {cls.OLLAMA_MODEL} @ {cls.OLLAMA_HOST}")

        logger.info(f"   • Redis: {cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}")
        logger.info(
            f"   • Parent-Child: child={cls.CHILD_CHUNK_SIZE}, parent={cls.PARENT_BLOCK_SIZE}, max_blocks={cls.MAX_PARENT_BLOCKS}")
        logger.info(
            f"   • Retrieval: top_k={cls.RETRIEVAL_TOP_K}, rerank_top_k={cls.RERANK_TOP_K}, min_score={cls.RERANK_MIN_SCORE}")
        logger.info(f"   • Context: max_tokens={cls.MAX_CONTEXT_TOKENS}, tables={cls.TABLE_FORMAT}")
        logger.info(f"   • Telegram: enabled={cls.TELEGRAM_ENABLED}")
        logger.info(f"   • Device: force_cpu={cls.FORCE_CPU}")

        estimated_tokens = cls.MAX_PARENT_BLOCKS * (cls.PARENT_BLOCK_SIZE // 4)
        logger.info(f"   • ⚠️  Оценка контекста: ~{estimated_tokens} токенов (лимит: {cls.MAX_CONTEXT_TOKENS})")


def load_env_variable(var_name, default=None):
    """Безопасная загрузка переменной окружения"""
    value = os.getenv(var_name, default)
    if value is None:
        raise EnvironmentError(f"Missing environment variable: {var_name}")
    return value


def make_request(url: str, auth_token: str, params: dict = None, method: str = 'GET') -> dict:
    """Делает запрос к Confluence API с retry-логикой"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                timeout=30,
                verify=True
            )
            logger.debug(f"API [{response.status_code}]: {url.split('?')[0][-60:]}")

            if response.status_code == 401:
                raise ValueError("❌ 401: Неверный токен или формат аутентификации")
            elif response.status_code == 403:
                raise ValueError("❌ 403: Нет прав доступа")
            elif response.status_code == 404:
                raise ValueError(f"❌ 404: Эндпоинт не найден: {url}")
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', retry_delay * (attempt + 1)))
                logger.warning(f"⚠️  Rate limit, ждём {retry_after} сек...")
                time.sleep(retry_after)
                continue
            elif response.status_code >= 500:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️  Серверная ошибка {response.status_code}, попытка {attempt + 2}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise ValueError(f"❌ Ошибка сервера {response.status_code}")
            elif response.status_code >= 400:
                preview = response.text[:300].replace('\n', ' ')
                raise ValueError(f"❌ Ошибка {response.status_code}: {preview}")

            if not response.text.strip():
                return {}

            return response.json()

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️  Таймаут, попытка {attempt + 2}")
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise ValueError(f"❌ Таймаут после {max_retries} попыток")
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️  Ошибка соединения, попытка {attempt + 2}")
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise ValueError(f"❌ Ошибка соединения: {e}")
        except json.JSONDecodeError as e:
            preview = response.text[:400].replace('\n', ' ') if 'response' in locals() else "Нет ответа"
            raise ValueError(f"❌ Не JSON-ответ:\n{preview}\nОшибка: {e}")

    raise ValueError("❌ Превышено количество попыток")


def initialize_auth():
    """Возвращает токен для Bearer-аутентификации"""
    return load_env_variable("CONFLUENCE_API_KEY")


def extract_metadata_from_confluence(page_data: dict, page_id: str, api_url: str) -> Dict[str, Any]:
    """Извлекает расширенные метаданные из ответа Confluence API."""
    if not isinstance(page_data, dict):
        logger.warning(f"⚠️  extract_metadata_from_confluence: page_data имеет тип {type(page_data)}")
        return {
            'document_id': str(page_id),
            'title': 'Без названия',
            'section': '',
            'url': f"{api_url}/pages/viewpage.action?pageId={page_id}",
            'page_version': '1',
            'last_updated': '',
            'space_key': '',
            'space_name': '',
            'content_type': 'page',
        }

    version_data = page_data.get('version', {})
    if not isinstance(version_data, dict):
        version_data = {}
    space_data = page_data.get('space', {})
    if not isinstance(space_data, dict):
        space_data = {}
    extensions_data = page_data.get('extensions', {})
    if not isinstance(extensions_data, dict):
        extensions_data = {}
    position_data = extensions_data.get('position', {})
    if not isinstance(position_data, dict):
        position_data = {}
    labels_data = page_data.get('labels', {})
    if not isinstance(labels_data, dict):
        labels_data = {}

    metadata = {
        "document_id": str(page_id),
        "title": page_data.get('title', 'Без названия'),
        "section": position_data.get('position', ''),
        "url": f"{api_url}/pages/viewpage.action?pageId={page_id}",
        "page_version": str(version_data.get('number', 1)),
        "last_updated": version_data.get('when', ''),
        "space_key": space_data.get('key', ''),
        "space_name": space_data.get('name', ''),
        "content_type": "page",
    }

    labels_results = labels_data.get('results', [])
    if isinstance(labels_results, list) and labels_results:
        tags = [lbl.get('name', '') for lbl in labels_results if isinstance(lbl, dict) and lbl.get('name')]
        if tags:
            metadata['tags'] = tags

    return metadata


def singleton(cls):
    """Потокобезопасный singleton"""
    instances = {}
    import threading
    lock = threading.Lock()

    def get_instance(*args, **kwargs):
        with lock:
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
            return instances[cls]

    return get_instance


def get_redis_client():
    """Создаёт Redis-клиент с настройками из env"""
    import redis
    return redis.Redis(
        host=load_env_variable("REDIS_HOST", "redis"),
        port=int(load_env_variable("REDIS_PORT", 6379)),
        db=int(load_env_variable("REDIS_DB", 0)),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30
    )


def format_datetime(dt: datetime) -> str:
    """Форматирует datetime для Redis"""
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%f%z')


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Парсит строку времени из Redis"""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        try:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f+0000")
        except ValueError:
            logger.warning(f"⚠️  Не удалось распарсить дату: {dt_str}")
            return None


def format_markdown_response(text: str, sources: List[Dict[str, str]] = None) -> str:
    """Форматирует ответ в Markdown с источниками."""
    if not sources or not Config.ALWAYS_SHOW_SOURCES:
        return text

    source_lines = []
    for src in sources[:Config.MAX_SOURCE_LINKS]:
        title = src.get('title', 'Документ')
        url = src.get('url', '#')
        section = src.get('section', '')
        if section and Config.INCLUDE_SECTION_IN_PROMPT:
            display_title = f"{title} — {section}"
        else:
            display_title = title
        source_lines.append(f"• [{display_title}]({url})")

    if source_lines:
        return f"{text}\n\n📎 **Источники**:\n" + "\n".join(source_lines)

    return text
