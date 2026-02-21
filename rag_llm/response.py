# rag_llm/response.py

from rag_llm import model, rag, context
from hybrid_search.utils import singleton, logger, Config, format_markdown_response
import re
from typing import List, Dict


@singleton
class Response:
    def __init__(self):
        self.model = model.Model()
        self.rag = rag.RAG()
        self.session_manager = context.RedisSession()
        logger.info("✅ Response инициализирован")

    def query_model(self, session_id: str, query: str, matches: Dict) -> str:
        """Генерирует ответ с Markdown-форматированием и ссылками"""
        documents = self.rag.get_documents(matches)

        if not documents:
            no_context = (
                "❌ **Информация не найдена**\n\n"
                "Я не нашёл релевантной информации в документации по этому вопросу.\n"
                "Попробуйте:\n"
                "• Переформулировать запрос\n"
                "• Использовать другие ключевые слова\n"
                "• Обратиться в техническую поддержку"
            )
            self.session_manager.store_conversation(session_id, 'user', query)
            self.session_manager.store_conversation(session_id, 'assistant', no_context)
            return no_context

        prompt = self.rag.create_prompt(query, documents)
        self.session_manager.store_conversation(session_id, 'user', query)

        messages = self.session_manager.get_conversation(session_id)
        system_message = {
            'role': 'system',
            'content': (
                "Ты — эксперт по внутренней документации компании. "
                "Отвечай ТОЛЬКО на основе предоставленного контекста. "
                "Используй Markdown для форматирования. "
                "Указывай источники в формате [document_id]. "
                "Будь краток и точен."
            )
        }
        messages = [system_message] + messages
        messages.append({'role': 'user', 'content': prompt})

        logger.info(f"Запрос в модель: {prompt}")
        response = self.model.get_response(messages)
        answer = response.get('message', {}).get('content', '❌ Ошибка генерации ответа')

        # Пост-обработка
        answer_formatted = self._format_response(answer, matches)

        self.session_manager.store_conversation(session_id, 'assistant', answer_formatted)
        return answer_formatted

    def _format_response(self, answer: str, matches: Dict) -> str:
        """
        Пост-обработка ответа:
        1. Извлекает упомянутые document_id из ответа
        2. Добавляет кликабельные ссылки на Confluence
        3. Форматирует в Markdown
        """
        # Извлекаем ID документов, которые упомянул LLM (паттерн [123456])
        mentioned_ids = set(re.findall(r'\[(\d+)\]', answer))

        # Сопоставляем с результатами поиска
        sources = []
        seen_ids = set()

        for match in matches.get('matches', []):
            doc_id = match.get('id', '')  # формат: "page_id-chunk_num"
            page_id = doc_id.split('-')[0]

            # Добавляем только если ID упомянут ИЛИ включён ALWAYS_SHOW_SOURCES
            if page_id in mentioned_ids or Config.ALWAYS_SHOW_SOURCES:
                if page_id in seen_ids:
                    continue
                seen_ids.add(page_id)

                metadata = match.get('metadata', {})
                url = metadata.get('url', '')
                title = metadata.get('title', 'Документ')
                section = metadata.get('section', '')

                sources.append({
                    'title': title,
                    'section': section,
                    'url': url,
                    'document_id': page_id
                })

        # Форматируем ответ с источниками
        formatted = format_markdown_response(answer, sources)

        return formatted

    def terminate(self, session_id: str):
        """Очищает историю сессии"""
        self.session_manager.clear_conversation(session_id)
