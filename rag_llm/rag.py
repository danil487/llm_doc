# rag_llm/rag.py
from hybrid_search.database import Database
from hybrid_search.utils import singleton, logger, Config, truncate_text
from typing import List, Dict


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
                'text': metadata.get('content', match.get('text', '')),
                'title': metadata.get('title', 'Без названия'),
                'section': metadata.get('section', ''),
                'url': metadata.get('url', ''),
                'document_id': metadata.get('document_id', ''),
                'score': match.get('rerank_score', match.get('score', 0))
            }
            if doc['text'].strip():
                documents.append(doc)

        logger.debug(f"📚 Извлечено документов: {len(documents)}")
        return documents

    def create_prompt(self, query: str, documents: List[Dict]) -> str:
        """Формирует структурированный промпт с метаданными"""
        if not documents:
            return f"Вопрос: {query}\nОтвет: (контекст не найден)"

        # ГРУППИРОВКА по документам в промпте
        doc_groups = {}
        for doc in documents:
            page_id = doc.get('document_id', 'unknown')
            if page_id not in doc_groups:
                doc_groups[page_id] = {
                    'title': doc['title'],
                    'url': doc['url'],
                    'chunks': []
                }
            doc_groups[page_id]['chunks'].append(doc['text'])

        # Формируем контекст
        context_parts = []
        total_tokens = 0

        for i, (page_id, doc_info) in enumerate(doc_groups.items(), 1):
            header = f"[ИСТОЧНИК {i}] — {doc_info['title']}"
            block = f"{header}\n"
            block += f"🔗 {doc_info['url']}\n"
            block += f"---\n"

            # ✅ Объединяем чанки одного документа
            combined_text = "\n\n...\n\n".join(doc_info['chunks'])
            block += f"{combined_text}\n"
            block += f"{'=' * 60}\n"

            # Проверяем лимит токенов
            block_tokens = len(block) // 4
            if total_tokens + block_tokens > Config.MAX_CONTEXT_TOKENS:
                logger.debug(f"⚠️  Достигнут лимит контекста ({Config.MAX_CONTEXT_TOKENS} токенов)")
                break

            context_parts.append(block)
            total_tokens += block_tokens

        context = "".join(context_parts)

        prompt = f"""Ты — помощник по внутренней документации компании Confluence.

=== КОНТЕКСТ ИЗ ДОКУМЕНТАЦИИ ===
{context}

=== ВОПРОС ПОЛЬЗОВАТЕЛЯ ===
{query}

=== ИНСТРУКЦИИ ДЛЯ ОТВЕТА ===
1. Отвечай СТРОГО на основе предоставленного контекста
2. Если информации недостаточно — честно скажи об этом
3. При ссылке на документ указывай его ID в формате [document_id], например [238485654]
4. Форматируй ответ в Markdown:
   • Используй **жирный** для ключевых терминов
   • Используй `код` для технических значений
   • Используй списки для шагов
   • Используй таблицы если уместно
5. После основного ответа добавь блок "📎 Источники" со ссылками

=== ФОРМАТ ОТВЕТА ===
[Твой ответ здесь]

📎 Источники:
• [Заголовок страницы](URL) — раздел
"""

        return prompt
