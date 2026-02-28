#!/usr/bin/env python3
"""
🧪 Тест Parent-Child Retrieval на 5 документах
Проверяет:
1. Индексацию с parent_id
2. Структуру ChromaDB
3. Поиск и группировку child → parent
"""

import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from hybrid_search.database import Database
from hybrid_search.search import SemanticSearch
from hybrid_search.update import UpdateDatabase
from hybrid_search.confluence import ConfluenceAPI
from hybrid_search.utils import Config
from hybrid_search.chunk import ParentChildChunker


def print_separator(title: str, char: str = "="):
    print("\n" + char * 80)
    print(f"  {title}")
    print(char * 80)


def test_chunker():
    """Тест 1: Проверка чанкера"""
    print_separator("ТЕСТ 1: ParentChildChunker", "─")

    chunker = ParentChildChunker()

    # Тестовый текст с таблицей
    test_text = """
## Описание системы

Это тестовый документ для проверки чанкинга.

### Таблица параметров

| Параметр | Значение | Описание |
|----------|----------|----------|
| CPU | 8 cores | Процессор |
| RAM | 32 GB | Память |
| Disk | 500 GB | Диск |

### Дополнительные сведения

Система работает на базе Kubernetes.
Масштабирование автоматическое.
""" * 3  # Умножаем чтобы было больше чанков

    page_id = "test-12345"
    chunks = chunker.chunk_page(test_text, page_id, {})

    print(f"\n📊 Результаты чанкинга:")
    print(f"   Всего child-parent пар: {len(chunks)}")
    print(f"   Child размер: {Config.CHILD_CHUNK_SIZE}")
    print(f"   Parent размер: {Config.PARENT_BLOCK_SIZE}")

    # Проверки
    errors = []

    if len(chunks) == 0:
        errors.append("❌ Чанки не созданы")
    else:
        print(f"   ✅ Чанки созданы")

    # Проверяем что parent_id есть в metadata
    for i, chunk in enumerate(chunks[:3]):
        parent_id = chunk.get('metadata', {}).get('parent_id')
        if not parent_id:
            errors.append(f"❌ chunk {i}: parent_id отсутствует в metadata")
        else:
            print(f"   ✅ chunk {i}: parent_id = {parent_id}")

    # Проверяем что parent_text есть
    for i, chunk in enumerate(chunks[:3]):
        parent_text = chunk.get('parent_text', '')
        if not parent_text or len(parent_text) < 100:
            errors.append(f"❌ chunk {i}: parent_text слишком короткий ({len(parent_text)} символов)")
        else:
            print(f"   ✅ chunk {i}: parent_text = {len(parent_text)} символов")

    # Проверяем ID формат
    for i, chunk in enumerate(chunks[:3]):
        child_id = chunk.get('child_id', '')
        if '-child-' not in child_id:
            errors.append(f"❌ chunk {i}: неверный формат child_id ({child_id})")
        else:
            print(f"   ✅ chunk {i}: child_id = {child_id}")

    if errors:
        print(f"\n⚠️  ОШИБКИ ЧАНКЕРА:")
        for err in errors:
            print(f"   {err}")
        return False
    else:
        print(f"\n✅ ЧАНКЕР: Все проверки пройдены")
        return True


def test_indexing(max_pages: int = 5):
    """Тест 2: Индексация 5 страниц"""
    print_separator("ТЕСТ 2: Индексация 5 страниц", "─")

    try:
        confluence = ConfluenceAPI()
        db = Database()

        # Получаем список страниц
        space_id = confluence.get_space_id()
        all_pages = confluence.get_page_ids(space_id)

        if len(all_pages) == 0:
            print("❌ Нет страниц в Confluence")
            return False

        # Берём первые 5
        test_pages = dict(list(all_pages.items())[:max_pages])
        print(f"\n📚 Тестируем на {len(test_pages)} страницах:")
        for page_id, info in test_pages.items():
            print(f"   • {info.get('title', 'Без названия')} ({page_id})")

        # Очищаем базу перед тестом
        print(f"\n🧹 Очистка базы данных...")
        db.clear_all()

        # Индексируем
        updater = UpdateDatabase()
        indexed_count = 0

        for page_id, page_info in test_pages.items():
            print(f"\n📥 Индексация: {page_info.get('title', page_id)}")
            try:
                success = updater.update_page(page_id, page_info)
                if success:
                    indexed_count += 1
                    print(f"   ✅ Успешно")
                else:
                    print(f"   ❌ Ошибка")
            except Exception as e:
                print(f"   ❌ Исключение: {e}")

        print(f"\n📊 ИТОГИ ИНДЕКСАЦИИ:")
        print(f"   Запланировано: {len(test_pages)}")
        print(f"   Успешно: {indexed_count}")
        print(f"   Чанков в базе: {db.count()}")

        if indexed_count == 0:
            print(f"\n❌ ИНДЕКСАЦИЯ: Не удалось проиндексировать ни одну страницу")
            return False
        else:
            print(f"\n✅ ИНДЕКСАЦИЯ: {indexed_count}/{len(test_pages)} страниц")
            return True

    except Exception as e:
        print(f"❌ Ошибка индексации: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_structure():
    """Тест 3: Проверка структуры базы данных"""
    print_separator("ТЕСТ 3: Структура базы данных", "─")

    db = Database()
    count = db.count()

    print(f"\n📊 Всего чанков в базе: {count}")

    if count == 0:
        print("❌ База пуста")
        return False

    # Получаем первые 10 чанков
    raw = db.collection.get(limit=10, include=['metadatas', 'documents'])

    stats = {
        'total': 0,
        'has_parent_id': 0,
        'has_parent_text': 0,
        'child_format': 0,
        'old_format': 0,
    }

    print(f"\n🔍 Анализ первых 10 чанков:")

    for i, chunk_id in enumerate(raw.get('ids', []), 1):
        stats['total'] += 1

        # Формат ID
        if '-child-' in chunk_id:
            stats['child_format'] += 1
            print(f"\n   [{i}] {chunk_id} ✅ Child формат")
        else:
            stats['old_format'] += 1
            print(f"\n   [{i}] {chunk_id} ❌ Старый формат")

        # Метаданные
        raw_meta = raw['metadatas'][i - 1] if raw.get('metadatas') else {}
        metadata = db._deserialize_metadata(raw_meta)

        # parent_id
        parent_id = metadata.get('parent_id')
        if parent_id:
            stats['has_parent_id'] += 1
            print(f"       ✅ parent_id: {parent_id}")
        else:
            print(f"       ❌ parent_id: ОТСУТСТВУЕТ")

        # parent_text
        parent_text = metadata.get('parent_text', '')
        if parent_text and len(parent_text) > 100:
            stats['has_parent_text'] += 1
            print(f"       ✅ parent_text: {len(parent_text)} символов")
        else:
            print(f"       ❌ parent_text: {len(parent_text) if parent_text else 0} символов")

    print(f"\n📊 СТАТИСТИКА:")
    print(
        f"   Child формат: {stats['child_format']}/{stats['total']} ({100 * stats['child_format'] / max(stats['total'], 1):.1f}%)")
    print(
        f"   Старый формат: {stats['old_format']}/{stats['total']} ({100 * stats['old_format'] / max(stats['total'], 1):.1f}%)")
    print(
        f"   Есть parent_id: {stats['has_parent_id']}/{stats['total']} ({100 * stats['has_parent_id'] / max(stats['total'], 1):.1f}%)")
    print(
        f"   Есть parent_text: {stats['has_parent_text']}/{stats['total']} ({100 * stats['has_parent_text'] / max(stats['total'], 1):.1f}%)")

    # Проверки
    errors = []
    if stats['has_parent_id'] < stats['total'] * 0.8:
        errors.append(f"❌ Менее 80% чанков имеют parent_id")
    if stats['has_parent_text'] < stats['total'] * 0.8:
        errors.append(f"❌ Менее 80% чанков имеют parent_text")
    if stats['old_format'] > stats['total'] * 0.2:
        errors.append(f"❌ Более 20% чанков со старым форматом ID")

    if errors:
        print(f"\n⚠️  ОШИБКИ СТРУКТУРЫ:")
        for err in errors:
            print(f"   {err}")
        return False
    else:
        print(f"\n✅ СТРУКТУРА БД: Все проверки пройдены")
        return True


def test_search():
    """Тест 4: Поиск"""
    print_separator("ТЕСТ 4: Поиск", "─")

    db = Database()
    if db.count() == 0:
        print("❌ База пуста, сначала выполните индексацию")
        return False

    # Тестовые запросы
    test_queries = [
        "тест",
        "система",
        "документация",
    ]

    search = SemanticSearch()

    for query in test_queries:
        print(f"\n🔍 Запрос: '{query}'")

        try:
            results = search.search(query)

            matches = results.get('matches', [])
            print(f"   Найдено matches: {len(matches)}")

            if len(matches) == 0:
                print(f"   ⚠️  Нет результатов")
                continue

            # Проверяем что это parent-блоки
            parent_count = sum(1 for m in matches if m.get('type') == 'parent')
            print(f"   Parent-блоков: {parent_count}/{len(matches)}")

            # Проверяем что есть text
            for i, match in enumerate(matches[:3], 1):
                text_len = len(match.get('text', ''))
                score = match.get('score', 0)
                parent_id = match.get('id', 'N/A')
                print(f"   [{i}] {parent_id}: {text_len} символов, score={score:.4f}")

            if parent_count > 0:
                print(f"   ✅ Поиск работает (есть parent-блоки)")
            else:
                print(f"   ⚠️  Поиск вернул результаты но нет parent-блоков")

        except Exception as e:
            print(f"   ❌ Ошибка поиска: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n✅ ПОИСК: Тестирование завершено")
    return True


def test_full_pipeline():
    """Тест 5: Полный пайплайн (поиск + группировка)"""
    print_separator("ТЕСТ 5: Полный пайплайн", "─")

    db = Database()
    if db.count() == 0:
        print("❌ База пуста")
        return False

    search = SemanticSearch()

    # Берём случайный запрос
    query = "тест"
    print(f"\n🔍 Тестовый запрос: '{query}'")

    results = search.search(query)

    print(f"\n📊 Результаты поиска:")
    print(f"   Тип: {results.get('type', 'unknown')}")
    print(f"   Matches: {len(results.get('matches', []))}")

    if not results.get('matches'):
        print(f"\n⚠️  Нет результатов поиска")
        print(f"   Возможно нужно изменить тестовый запрос")
        return False

    # Проверяем логику группировки
    matches = results['matches']

    # Проверяем что у каждого match есть text
    missing_text = sum(1 for m in matches if not m.get('text'))
    if missing_text > 0:
        print(f"\n⚠️  {missing_text} matches без текста")

    # Проверяем что есть metadata
    missing_meta = sum(1 for m in matches if not m.get('metadata'))
    if missing_meta > 0:
        print(f"\n⚠️  {missing_meta} matches без metadata")

    # Проверяем parent_id в metadata
    missing_parent = sum(1 for m in matches if not m.get('metadata', {}).get('parent_id'))
    if missing_parent > 0:
        print(f"\n⚠️  {missing_parent} matches без parent_id в metadata")

    print(f"\n📊 Детали matches:")
    for i, match in enumerate(matches[:5], 1):
        print(f"\n   Match #{i}:")
        print(f"      ID: {match.get('id')}")
        print(f"      Type: {match.get('type')}")
        print(f"      Score: {match.get('score', 0):.4f}")
        print(f"      Text length: {len(match.get('text', ''))}")
        print(f"      Child count: {match.get('child_count', 'N/A')}")
        parent_id = match.get('metadata', {}).get('parent_id')
        print(f"      Parent ID: {parent_id if parent_id else '❌ НЕТ'}")

    print(f"\n✅ ПИПЛАЙН: Тестирование завершено")
    return True


def main():
    """Запуск всех тестов"""
    print_separator("🧪 ТЕСТ PARENT-CHILD RETRIEVAL", "=")

    print(f"\n📋 Конфигурация:")
    print(f"   CHILD_CHUNK_SIZE: {Config.CHILD_CHUNK_SIZE}")
    print(f"   PARENT_BLOCK_SIZE: {Config.PARENT_BLOCK_SIZE}")
    print(f"   MAX_PARENT_BLOCKS: {Config.MAX_PARENT_BLOCKS}")
    print(f"   CHILD_MIN_SCORE: {Config.CHILD_MIN_SCORE}")
    print(f"   ChromaDB: {Config.CHROMA_DB_PATH}")

    results = {}

    # Тест 1: Чанкер (не требует БД)
    results['chunker'] = test_chunker()

    # Тест 2: Индексация
    print("\n" + "=" * 80)
    response = input("Запустить индексацию 5 страниц? (да/нет): ").strip().lower()
    if response in ['да', 'yes', 'y']:
        results['indexing'] = test_indexing(max_pages=5)
    else:
        print("⏭️  Пропускаем индексацию")
        results['indexing'] = None

    # Тест 3: Структура БД
    print("\n" + "=" * 80)
    response = input("Проверить структуру базы данных? (да/нет): ").strip().lower()
    if response in ['да', 'yes', 'y']:
        results['database'] = test_database_structure()
    else:
        print("⏭️  Пропускаем проверку БД")
        results['database'] = None

    # Тест 4: Поиск
    print("\n" + "=" * 80)
    response = input("Запустить тест поиска? (да/нет): ").strip().lower()
    if response in ['да', 'yes', 'y']:
        results['search'] = test_search()
    else:
        print("⏭️  Пропускаем поиск")
        results['search'] = None

    # Тест 5: Полный пайплайн
    print("\n" + "=" * 80)
    response = input("Запустить тест полного пайплайна? (да/нет): ").strip().lower()
    if response in ['да', 'yes', 'y']:
        results['pipeline'] = test_full_pipeline()
    else:
        print("⏭️  Пропускаем пайплайн")
        results['pipeline'] = None

    # Итоги
    print_separator("📊 ИТОГИ ТЕСТИРОВАНИЯ", "=")

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    print(f"\n✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"⏭️  Пропущено: {skipped}")

    if failed > 0:
        print(f"\n⚠️  ЕСТЬ ОШИБКИ! Проверьте логи выше.")
        print(f"\n💡 Рекомендации:")
        print(f"   1. Проверьте что используется ParentChildChunker в update.py")
        print(f"   2. Проверьте что upsert_child_chunk() сохраняет parent_id")
        print(f"   3. Проверьте что search.py группирует child → parent")
        return 1
    else:
        print(f"\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
