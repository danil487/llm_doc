# rag_llm/rag.py
from typing import List, Dict

from hybrid_search.database import Database
from hybrid_search.utils import singleton, logger, Config
from hybrid_search.dynamic_config import dynamic_config

@singleton
class RAG:
    def __init__(self):
        self.db = Database()
        logger.info("✅ RAG инициализирован")

    def get_documents(self, results: Dict) -> List[Dict]:
        """Извлекает документы с метаданными из результатов поиска"""
        documents = []
        matches = results.get('matches', [])

        for match in matches:
            metadata = match.get('metadata', {})
            doc = {
                'text': match.get('text', ''),
                'title': metadata.get('title', 'Без названия'),
                'section': metadata.get('section', ''),
                'url': metadata.get('url', ''),
                'document_id': metadata.get('document_id', ''),
                'score': match.get('score', 0)
            }
            if doc['text'].strip():
                documents.append(doc)

        logger.debug(f"📚 Извлечено документов: {len(documents)}")
        return documents

    def create_prompt(self, query: str, documents: List[Dict]) -> str:
        """Формирует структурированный промпт с parent-блоками"""
        if not documents:
            return f"Вопрос: {query}\nОтвет: (контекст не найден)"

        context_parts = []
        total_tokens = 0

        for i, doc in enumerate(documents[:dynamic_config.get('MAX_PARENT_BLOCKS')], 1):
            metadata = doc.get('metadata', {})

            header = f"[ИСТОЧНИК {i}] — {doc['title']}"
            block = f"{header}\n"

            url = doc.get('url', '')
            section = doc.get('section', '')
            if url:
                block += f"🔗 {url}"
                if section and dynamic_config.get('INCLUDE_SECTION_IN_PROMPT'):
                    block += f" → {section}"
                block += "\n"

            block += f"{'=' * 60}\n"
            block += f"{doc['text']}\n"
            block += f"{'=' * 60}\n\n"

            block_tokens = len(block) // 4
            if total_tokens + block_tokens > dynamic_config.get('MAX_CONTEXT_TOKENS'):
                logger.debug(f"⚠️  Достигнут лимит контекста ({dynamic_config.get('MAX_CONTEXT_TOKENS')} токенов)")
                break

            context_parts.append(block)
            total_tokens += block_tokens

        context = "\n".join(context_parts)

        prompt = f"""Ты — эксперт по технической документации Confluence.

=== КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ===
{context}

=== ВОПРОС ПОЛЬЗОВАТЕЛЯ ===
{query}

=== ИНСТРУКЦИИ ===
1. Отвечай СТРОГО на основе контекста выше
2. Если информации недостаточно — честно скажи "В документации нет ответа на этот вопрос"
3. Цитируй конкретные разделы, используя [ИСТОЧНИК N]
4. Для таблиц — интерпретируй данные, а не копируй сырой текст
5. Форматируй ответ в Markdown: списки, **жирный** для терминов, `код` для значений

=== ФОРМАТ ОТВЕТА ===
[Твой ответ]

📎 Источники:
• [Заголовок](URL) — раздел
"""
        return prompt
