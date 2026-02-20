# hybrid_search/context.py

import json
import os
from hybrid_search.utils import singleton, get_redis_client, logger


@singleton
class RedisSession:
    def __init__(self):
        self.redis = get_redis_client()
        self.default_ttl = int(os.getenv("REDIS_TTL_SECONDS", 3600))
        logger.info(f"✅ RedisSession инициализирован (TTL: {self.default_ttl} сек)")

    def store_conversation(self, session_id: str, role: str, content: str):
        """Добавляет сообщение в историю диалога"""
        try:
            conversation_raw = self.redis.get(session_id)

            if conversation_raw:
                conversation = json.loads(conversation_raw)
            else:
                conversation = []

            conversation.append({'role': role, 'content': content})

            # Ограничиваем историю последними 20 сообщениями
            conversation = conversation[-20:]

            self.redis.setex(
                session_id,
                self.default_ttl,
                json.dumps(conversation, ensure_ascii=False)
            )

        except json.JSONDecodeError as e:
            logger.warning(f"⚠️  Ошибка парсинга истории сессии {session_id}: {e}")
            self.clear_conversation(session_id)
        except Exception as e:
            logger.error(f"⚠️  Ошибка сохранения истории сессии {session_id}: {e}")

    def get_conversation(self, session_id: str) -> list[dict]:
        """Получает историю диалога для сессии"""
        try:
            conversation_raw = self.redis.get(session_id)
            if conversation_raw:
                return json.loads(conversation_raw)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️  Ошибка парсинга истории сессии {session_id}: {e}")
            self.clear_conversation(session_id)
        except Exception as e:
            logger.error(f"⚠️  Ошибка получения истории сессии {session_id}: {e}")

        return []

    def clear_conversation(self, session_id: str):
        """Очищает историю диалога для сессии"""
        try:
            self.redis.delete(session_id)
            logger.debug(f"🧹 Сессия {session_id} очищена")
        except Exception as e:
            logger.error(f"⚠️  Ошибка очистки сессии {session_id}: {e}")

    def get_conversation_as_prompt(self, session_id: str, max_messages: int = 10) -> str:
        """Форматирует историю диалога как промпт для LLM"""
        conversation = self.get_conversation(session_id)
        recent = conversation[-max_messages:] if len(conversation) > max_messages else conversation

        lines = []
        for msg in recent:
            role = "Пользователь" if msg['role'] == 'user' else "Ассистент"
            lines.append(f"{role}: {msg['content']}")

        return "\n".join(lines)
