# rag_llm/model.py

import ollama
from hybrid_search.utils import load_env_variable, singleton, logger
import os


@singleton
class Model:
    def __init__(self):
        self.model_name = load_env_variable('OLLAMA_MODEL', default='llama3.1')
        ollama_host = os.getenv('OLLAMA_HOST', 'http://ollama:11434')

        self.client = ollama.Client(host=ollama_host, timeout=1200)
        logger.info(f"🤖 Ollama модель: {self.model_name}, хост: {ollama_host}")

    def get_response(self, messages: list[dict]) -> dict:
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options={'temperature': 0.7, 'top_p': 0.9, 'num_predict': 1024},
            )

            # ← Добавьте проверку структуры ответа:
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
            return {'message': {'content': f"⚠️ Ошибка: {str(e)[:200]}"}}

    def check_model_available(self) -> bool:
        """Проверяет, доступна ли модель в Ollama"""
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            available = any(self.model_name in m for m in model_names)

            if available:
                logger.info(f"✅ Модель {self.model_name} доступна")
            else:
                logger.warning(f"⚠️  Модель {self.model_name} не найдена")

            return available
        except Exception as e:
            logger.error(f"⚠️  Не удалось проверить модель: {e}")
            return False
