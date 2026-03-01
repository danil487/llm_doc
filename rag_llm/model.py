# rag_llm/model.py
from hybrid_search.utils import singleton, logger, Config


@singleton
class Model:
    """
    Универсальный LLM-клиент с поддержкой:
    - DeepSeek API (OpenAI-совместимый)
    - Qwen API (DashScope)
    - Локальный Ollama
    """

    def __init__(self):
        self.use_api = Config.USE_LLM_API
        self.api_client = None
        self.ollama_client = None

        if self.use_api:
            self._init_api_client()
        else:
            self._init_ollama_client()

        logger.info(f"🤖 LLM режим: {'API' if self.use_api else 'Ollama'}")

    def _init_api_client(self):
        """Инициализация API клиента (DeepSeek/Qwen)"""
        try:
            from openai import OpenAI

            self.model_name = Config.LLM_MODEL
            self.api_base = Config.LLM_API_BASE
            self.api_key = Config.LLM_API_KEY
            self.temperature = Config.LLM_TEMPERATURE
            self.max_tokens = Config.LLM_MAX_TOKENS
            self.timeout = Config.LLM_TIMEOUT

            if not self.api_key:
                raise ValueError("LLM_API_KEY не установлен")

            self.api_client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout
            )

            logger.info(f"✅ API клиент инициализирован: {self.model_name} @ {self.api_base}")

        except ImportError:
            logger.error("❌ Package 'openai' not installed. Run: pip install openai")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации API клиента: {e}")
            raise

    def _init_ollama_client(self):
        """Инициализация локального Ollama клиента"""
        try:
            import ollama

            self.model_name = Config.OLLAMA_MODEL
            self.ollama_host = Config.OLLAMA_HOST

            self.ollama_client = ollama.Client(
                host=self.ollama_host,
                timeout=1200
            )

            logger.info(f"✅ Ollama клиент инициализирован: {self.model_name} @ {self.ollama_host}")

        except ImportError:
            logger.error("❌ Package 'ollama' not installed. Run: pip install ollama")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Ollama клиента: {e}")
            raise

    def get_response(self, messages: list[dict]) -> dict:
        """
        Получение ответа от модели

        Args:
            messages: Список сообщений в формате [{'role': 'user|assistant|system', 'content': '...'}]

        Returns:
            dict: {'message': {'content': '...'}}
        """
        try:
            if self.use_api:
                return self._get_api_response(messages)
            else:
                return self._get_ollama_response(messages)

        except Exception as e:
            logger.error(f"❌ Ошибка получения ответа: {e}")
            return {'message': {'content': f"⚠️ Ошибка LLM: {str(e)[:200]}"}}

    def _get_api_response(self, messages: list[dict]) -> dict:
        """Запрос к API (DeepSeek/Qwen)"""
        try:
            response = self.api_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )

            if not response or not response.choices:
                logger.error(f"❌ Пустой ответ от API: {response}")
                return {'message': {'content': '⚠️ Пустой ответ от API'}}

            content = response.choices[0].message.content.strip()

            if not content:
                logger.warning("⚠️  Пустой ответ от модели")
                return {'message': {'content': '⚠️ Модель вернула пустой ответ'}}

            # Логирование использования токенов
            if hasattr(response, 'usage') and response.usage:
                logger.debug(
                    f"📊 Токены: input={response.usage.prompt_tokens}, output={response.usage.completion_tokens}")

            return {'message': {'content': content}}

        except Exception as e:
            logger.error(f"❌ Ошибка API запроса: {e}")
            raise

    def _get_ollama_response(self, messages: list[dict]) -> dict:
        """Запрос к локальному Ollama"""
        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    'temperature': self.temperature if hasattr(self, 'temperature') else 0.7,
                    'top_p': 0.9,
                    'num_predict': self.max_tokens if hasattr(self, 'max_tokens') else 1024
                }
            )

            if not response or 'message' not in response:
                logger.error(f"❌ Неверный ответ Ollama: {response}")
                return {'message': {'content': '⚠️ Ошибка формата ответа'}}

            content = response['message'].get('content', '').strip()

            if not content:
                logger.warning("⚠️  Пустой ответ от модели")
                return {'message': {'content': '⚠️ Модель вернула пустой ответ'}}

            return response

        except Exception as e:
            logger.error(f"❌ Ошибка Ollama: {e}")
            raise

    def check_model_available(self) -> bool:
        """Проверяет доступность модели"""
        try:
            if self.use_api:
                # Для API просто проверяем ключ
                if not self.api_key:
                    logger.warning("⚠️  API ключ не установлен")
                    return False
                logger.info(f"✅ API ключ установлен для {self.model_name}")
                return True
            else:
                # Для Ollama проверяем наличие модели
                models = self.ollama_client.list()
                model_names = [m['name'] for m in models.get('models', [])]
                available = any(self.model_name in m for m in model_names)

                if available:
                    logger.info(f"✅ Модель {self.model_name} доступна в Ollama")
                else:
                    logger.warning(f"⚠️  Модель {self.model_name} не найдена в Ollama")

                return available

        except Exception as e:
            logger.error(f"⚠️  Не удалось проверить модель: {e}")
            return False

    def get_model_info(self) -> dict:
        """Возвращает информацию о текущей модели"""
        return {
            'mode': 'api' if self.use_api else 'ollama',
            'model_name': self.model_name,
            'endpoint': self.api_base if self.use_api else self.ollama_host,
            'temperature': self.temperature if hasattr(self, 'temperature') else 0.7,
            'max_tokens': self.max_tokens if hasattr(self, 'max_tokens') else 1024
        }
