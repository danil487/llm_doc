# hybrid_search/dynamic_config.py
import json
from hybrid_search.utils import get_redis_client, logger, Config as StaticConfig


class DynamicConfig:
    REDIS_KEY = "dynamic_config"
    # Список параметров, разрешённых для изменения (не влияют на индексацию)
    EDITABLE_PARAMS = [
        'RETRIEVAL_TOP_K',
        'RERANK_TOP_K',
        'RERANK_MIN_SCORE',
        'CHILD_MIN_SCORE',
        'MAX_PARENT_BLOCKS',
        'MAX_CONTEXT_TOKENS',
        'LLM_TEMPERATURE',
        'LLM_MAX_TOKENS',
        'INCLUDE_SECTION_IN_PROMPT',
        'ALWAYS_SHOW_SOURCES',
        'MAX_SOURCE_LINKS',
    ]

    def __init__(self):
        self.redis = get_redis_client()
        self._init_defaults()

    def _init_defaults(self):
        """Записывает значения по умолчанию в Redis, если ключ отсутствует."""
        if not self.redis.exists(self.REDIS_KEY):
            defaults = self._get_defaults_from_static()
            self.redis.set(self.REDIS_KEY, json.dumps(defaults))

    def _get_defaults_from_static(self):
        defaults = {}
        for param in self.EDITABLE_PARAMS:
            if hasattr(StaticConfig, param):
                defaults[param] = getattr(StaticConfig, param)
        return defaults

    def get(self, key: str):
        """Возвращает значение параметра (сначала из Redis, затем из статического Config)."""
        try:
            data = self.redis.get(self.REDIS_KEY)
            if data:
                config = json.loads(data)
                if key in config:
                    return config[key]
        except Exception as e:
            logger.error(f"DynamicConfig.get error for {key}: {e}")
        # fallback
        return getattr(StaticConfig, key, None)

    def get_all(self) -> dict:
        """Возвращает все текущие динамические настройки."""
        try:
            data = self.redis.get(self.REDIS_KEY)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"DynamicConfig.get_all error: {e}")
        return self._get_defaults_from_static()

    def set(self, updates: dict) -> dict:
        """Обновляет настройки, выполняет приведение типов и сохраняет в Redis."""
        current = self.get_all()
        for key, value in updates.items():
            if key not in self.EDITABLE_PARAMS:
                continue
            # Приведение типа на основе значения по умолчанию
            default_val = current.get(key, self._get_defaults_from_static().get(key))
            if default_val is not None:
                try:
                    if isinstance(default_val, bool):
                        value = str(value).lower() in ('true', '1', 'yes')
                    elif isinstance(default_val, int):
                        value = int(value)
                    elif isinstance(default_val, float):
                        value = float(value)
                    else:
                        value = str(value)
                except ValueError:
                    raise ValueError(f"Invalid value for {key}: {value}")
            current[key] = value
        self.redis.set(self.REDIS_KEY, json.dumps(current))
        return current


# Глобальный экземпляр
dynamic_config = DynamicConfig()
