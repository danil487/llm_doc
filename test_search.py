#!/usr/bin/env python3
"""
Скрипт для тестирования Parent-Child поиска с новыми параметрами.
Запуск: python test_search.py "ваш запрос"
"""

import os
import sys

# Устанавливаем новые параметры (можно менять)
os.environ['CHILD_MIN_SCORE'] = '0.55'
os.environ['RETRIEVAL_TOP_K'] = '20'
os.environ['RERANK_TOP_K'] = '5'
# Оставляем остальные как в .env, при необходимости можно добавить ещё

# Убедимся, что корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Теперь импортируем всё остальное
from hybrid_search.search import SemanticSearch
from rag_llm.rag import RAG
from hybrid_search.utils import Config  # для вывода значений


def print_separator(char='=', length=80):
    print(char * length)


def truncate_text(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...\n[обрезано]"


def main():
    # Покажем текущие настройки (для проверки)
    print("🔧 Используемые настройки:")
    print(f"   CHILD_MIN_SCORE = {Config.CHILD_MIN_SCORE}")
    print(f"   RETRIEVAL_TOP_K = {Config.RETRIEVAL_TOP_K}")
    print(f"   RERANK_TOP_K = {Config.RERANK_TOP_K}")
    print_separator()

    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
    else:
        query = input("Введите поисковый запрос: ").strip()
        if not query:
            print("Запрос не может быть пустым.")
            sys.exit(1)

    print(f"🔍 Поисковый запрос: {query}")
    print_separator()

    try:
        searcher = SemanticSearch()
        rag = RAG()
    except Exception as e:
        print(f"❌ Ошибка инициализации компонентов: {e}")
        sys.exit(1)

    print("⏳ Выполняется поиск...")
    try:
        result = searcher.search(query)
    except Exception as e:
        print(f"❌ Ошибка выполнения поиска: {e}")
        sys.exit(1)

    matches = result.get('matches', [])
    if not matches:
        print("⚠️  Ничего не найдено.")
        return

    print(f"\n📊 Статистика поиска:")
    print(f"   Найдено родительских документов: {len(matches)}")
    print_separator('-')
    print("📄 Найденные документы:")
    for idx, doc in enumerate(matches, 1):
        doc_id = doc.get('id', 'N/A')
        metadata = doc.get('metadata', {})
        title = metadata.get('title', 'Без названия')
        url = metadata.get('url', '')
        score = doc.get('score', 0)
        child_count = doc.get('child_count', 0)
        text = doc.get('text', '')

        print(f"\n{idx}. [{doc_id}] {title}")
        print(f"   🔗 URL: {url}")
        print(f"   ⭐ Score: {score:.4f} (на основе {child_count} child-чанков)")
        print(f"   📝 Фрагмент текста ({len(text)} символов):")
        print(truncate_text(text, 600))
        print()

    print_separator('~')
    print("🤖 Промпт, который будет отправлен в LLM:")
    print_separator('~')

    docs_for_prompt = rag.get_documents(result)
    if not docs_for_prompt:
        print("⚠️  Не удалось подготовить документы для промпта.")
        return

    prompt = rag.create_prompt(query, docs_for_prompt)
    print(prompt)
    print_separator('~')
    print("✅ Тестирование завершено.")


if __name__ == "__main__":
    main()
