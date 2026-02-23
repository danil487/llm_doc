# hybrid_search/update.py

import time
from datetime import datetime, timezone
from typing import Dict, Any

from hybrid_search import database, confluence, embed, chunk
from hybrid_search.utils import html_to_text, get_redis_client, logger, parse_datetime, format_datetime


class UpdateDatabase:
    def __init__(self):
        self.db = database.Database()
        self.confluence_api = confluence.ConfluenceAPI()
        self.chunker = chunk.SemanticChunk()
        self.embedder = embed.Embed()
        self.redis = get_redis_client()
        logger.info("✅ UpdateDatabase инициализирован")

    def update_page(self, page_id: str, page_metadata: Dict[str, Any] = None) -> bool:
        """Обновляет одну страницу с расширенными метаданными"""
        try:
            # Получаем контент + метаданные
            page_data = self.confluence_api.get_page_full(page_id)
            html_data = page_data['content']
            base_metadata = page_data['metadata'] if page_metadata is None else page_metadata

            text = html_to_text(html_data)
            if not text.strip():
                logger.warning(f"⚠️  Страница {page_id} пустая")
                return False

            # Чанкинг
            chunks = self.chunker.split(text)
            total_chunks = len(chunks)

            for num, chunk_text in enumerate(chunks):
                # Векторизация
                dense_vector = self.embedder.embed_text(chunk_text)
                sparse_vector = self.embedder.embed_sparse(chunk_text)

                # Уникальный ID чанка
                chunk_id = f"{page_id}-{num}"

                # Метаданные чанка
                chunk_metadata = {
                    **base_metadata,
                    'chunk_index': num,
                    'total_chunks': total_chunks
                }

                # Сохранение в ChromaDB
                self.db.upsert_page(chunk_id, dense_vector, sparse_vector, chunk_text, chunk_metadata)

            # Сохраняем время обновления
            current_time = datetime.now(timezone.utc)
            self.redis.setex(f'update_time:{page_id}', 86400 * 30, format_datetime(current_time))

            logger.info(f"✅ Страница {page_id} обработана: {total_chunks} чанков")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении страницы {page_id}: {e}")
            return False

    def load_all(self):
        """Полная загрузка с расширенными метаданными"""
        logger.info("🔄 Запуск полной загрузки из Confluence...")

        space_id = self.confluence_api.get_space_id()
        pages = self.confluence_api.get_page_ids(space_id)
        total = len(pages)

        # Сбор текстов для BM25
        logger.info(f"📚 Сбор текстов для BM25 (0/{total})...")
        all_texts = []
        page_data_cache = {}

        for idx, (page_id, page_info) in enumerate(pages.items(), 1):
            if not isinstance(page_info, dict):
                logger.error(f"⚠️  Пропущена страница {page_id}: page_info имеет тип {type(page_info)}")
                continue

            try:
                full_data = self.confluence_api.get_page_full(page_id)

                if not isinstance(full_data, dict):
                    logger.error(f"⚠️  Пропущена страница {page_id}: get_page_full вернул {type(full_data)}")
                    continue

                text = html_to_text(full_data.get('content', ''))

                if text.strip():
                    all_texts.append(text)
                    page_data_cache[page_id] = {
                        'text': text,
                        'metadata': full_data.get('metadata', {})
                    }

                if idx % 100 == 0 or idx == total:
                    logger.info(f"📚 Сбор текстов: {idx}/{total} ({100 * idx // total}%)")

            except Exception as e:
                logger.error(f"⚠️  Пропущена страница {page_id}: {e}")

        # Инициализация BM25
        if all_texts:
            logger.info(f"🔧 Инициализация BM25 на {len(all_texts)} документах...")
            self.embedder.fit_bm25(all_texts)

        # Индексация
        logger.info("📥 Начало индексации...")
        for idx, (page_id, page_info) in enumerate(pages.items(), 1):
            if not isinstance(page_info, dict):
                logger.warning(f"⚠️  Пропущена страница {page_id}: page_info не dict")
                continue

            logger.info(f"📥 [{idx}/{total}] {page_info.get('title', page_id)}")

            if page_id in page_data_cache:
                text = page_data_cache[page_id]['text']
                metadata = page_data_cache[page_id]['metadata']
            else:
                try:
                    full_data = self.confluence_api.get_page_full(page_id)
                    if not isinstance(full_data, dict):
                        logger.warning(f"⚠️  Пропущена страница {page_id}: full_data не dict")
                        continue
                    text = html_to_text(full_data.get('content', ''))
                    metadata = full_data.get('metadata', {})
                except Exception as e:
                    logger.error(f"❌ Ошибка: {e}")
                    continue

            self._process_text(page_id, text, metadata)

            if idx % 100 == 0 or idx == total:
                logger.info(f"✅ Прогресс: {idx}/{total} ({100 * idx // total}%)")

        logger.info(f"🎉 Загрузка завершена: {len(page_data_cache)} страниц проиндексировано")

    def _process_text(self, page_id: str, text: str, metadata: Dict[str, Any]):
        """Внутренний метод обработки текста с метаданными"""
        try:
            chunks = self.chunker.split(text)
            total_chunks = len(chunks)

            for num, chunk_text in enumerate(chunks):
                dense_vector = self.embedder.embed_text(chunk_text)
                sparse_vector = self.embedder.embed_sparse(chunk_text)
                chunk_id = f"{page_id}-{num}"

                chunk_metadata = {
                    **metadata,
                    'chunk_index': num,
                    'total_chunks': total_chunks
                }

                # Удаляем пустые списки
                chunk_metadata = {
                    k: v for k, v in chunk_metadata.items()
                    if not (isinstance(v, list) and len(v) == 0)
                }

                self.db.upsert_page(chunk_id, dense_vector, sparse_vector, chunk_text, chunk_metadata)

                current_time = datetime.now(timezone.utc)
                self.redis.setex(f'update_time:{page_id}', 86400 * 30, format_datetime(current_time))

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке {page_id}: {e}")

    def sync_changed_pages(self, max_pages: int = None) -> dict:
        """Синхронизация только изменённых страниц"""
        stats = {'checked': 0, 'updated': 0, 'new': 0, 'errors': 0}

        try:
            space_id = self.confluence_api.get_space_id()
            pages = self.confluence_api.get_page_ids(space_id)

            if max_pages:
                pages = dict(list(pages.items())[:max_pages])

            for page_id, page_info in pages.items():
                stats['checked'] += 1

                try:
                    confluence_time_str = self.confluence_api.get_time(page_id)
                    stored_time_str = self.redis.get(f'update_time:{page_id}')

                    need_update = False

                    if stored_time_str is None:
                        logger.info(f"🆕 Новая страница: {page_info.get('title')}")
                        stats['new'] += 1
                        need_update = True
                    else:
                        confluence_time = parse_datetime(confluence_time_str)
                        stored_time = parse_datetime(stored_time_str)

                        if confluence_time and stored_time and confluence_time > stored_time:
                            logger.info(f"🔄 Изменена: {page_info.get('title')}")
                            need_update = True

                    if need_update:
                        if self.update_page(page_id, page_info):
                            stats['updated'] += 1

                except Exception as e:
                    logger.error(f"⚠️  Пропущена страница {page_id}: {e}")
                    stats['errors'] += 1
                    continue

            logger.info(f"✅ Синхронизация: {stats['updated']} обновлено, {stats['new']} новых")

        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации: {e}")

        return stats

    def periodic_update(self, check_interval: int = 300, max_pages_per_cycle: int = 50):
        """Фоновая задача периодического обновления"""
        logger.info(f"🔄 Периодическое обновление (интервал: {check_interval} сек)...")

        while True:
            try:
                stats = self.sync_changed_pages(max_pages=max_pages_per_cycle)

                if stats['updated'] > 0:
                    logger.info(f"✅ Обновлено: {stats['updated']}/{stats['checked']}")
                else:
                    logger.info(f"✅ Изменений нет ({stats['checked']} проверено)")

                logger.info(f"⏳ Следующая проверка через {check_interval} сек...\n")
                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"❌ Ошибка в periodic_update: {e}")
                time.sleep(check_interval)
