# hybrid_search/update.py
import time
from datetime import datetime, timezone
from typing import Dict, Any

from hybrid_search import database, confluence, embed, chunk
from hybrid_search.utils import get_redis_client, logger, format_datetime


class UpdateDatabase:
    def __init__(self):
        self.db = database.Database()
        self.confluence_api = confluence.ConfluenceAPI()
        self.chunker = chunk.ParentChildChunker()
        self.embedder = embed.Embed()
        self.redis = get_redis_client()
        logger.info("✅ UpdateDatabase инициализирован (Parent-Child)")

    def update_page(self, page_id: str, page_metadata: Dict[str, Any] = None) -> bool:
        """Обновляет одну страницу с Parent-Child чанкингом"""
        try:
            page_data = self.confluence_api.get_page_full(page_id)
            text = page_data['content']
            structure_meta = page_data.get('structure_metadata', {})
            base_metadata = page_data['metadata'] if page_metadata is None else page_metadata

            if not text.strip():
                logger.warning(f"⚠️  Страница {page_id} пустая")
                return False

            # Parent-Child чанкинг
            chunk_pairs = self.chunker.chunk_page(text, page_id, structure_meta)

            for chunk_pair in chunk_pairs:
                dense_vector = self.embedder.embed_text(chunk_pair['child_text'])
                sparse_vector = self.embedder.embed_sparse(chunk_pair['child_text'])

                chunk_metadata = {
                    **base_metadata,
                    **chunk_pair['metadata']
                }

                self.db.upsert_child_chunk(
                    chunk_id=chunk_pair['child_id'],
                    dense_vector=dense_vector,
                    sparse_vector=sparse_vector,
                    child_text=chunk_pair['child_text'],
                    parent_text=chunk_pair['parent_text'],
                    metadata=chunk_metadata
                )

            current_time = datetime.now(timezone.utc)
            self.redis.setex(f'update_time:{page_id}', 86400 * 30, format_datetime(current_time))

            logger.info(f"✅ Страница {page_id} обработана: {len(chunk_pairs)} child-parent пар")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении страницы {page_id}: {e}")
            return False

    def load_all(self):
        """Полная загрузка с Parent-Child чанкингом"""
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

                text = full_data.get('content', '')
                if text.strip():
                    all_texts.append(text)
                    page_data_cache[page_id] = {
                        'text': text,
                        'metadata': full_data.get('metadata', {}),
                        'structure_meta': full_data.get('structure_metadata', {})
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
                structure_meta = page_data_cache[page_id]['structure_meta']
            else:
                try:
                    full_data = self.confluence_api.get_page_full(page_id)
                    if not isinstance(full_data, dict):
                        logger.warning(f"⚠️  Пропущена страница {page_id}: full_data не dict")
                        continue
                    text = full_data.get('content', '')
                    metadata = full_data.get('metadata', {})
                    structure_meta = full_data.get('structure_metadata', {})
                except Exception as e:
                    logger.error(f"❌ Ошибка: {e}")
                    continue

            self._process_text(page_id, text, metadata, structure_meta)

            if idx % 100 == 0 or idx == total:
                logger.info(f"✅ Прогресс: {idx}/{total} ({100 * idx // total}%)")

        logger.info(f"🎉 Загрузка завершена: {len(page_data_cache)} страниц проиндексировано")

    def _process_text(self, page_id: str, text: str, metadata: Dict[str, Any], structure_meta: dict = None):
        """Внутренний метод обработки текста с Parent-Child чанкингом"""
        try:
            chunk_pairs = self.chunker.chunk_page(text, page_id, structure_meta)

            for chunk_pair in chunk_pairs:
                dense_vector = self.embedder.embed_text(chunk_pair['child_text'])
                sparse_vector = self.embedder.embed_sparse(chunk_pair['child_text'])

                chunk_metadata = {
                    **metadata,
                    **chunk_pair['metadata']
                }

                self.db.upsert_child_chunk(
                    chunk_id=chunk_pair['child_id'],
                    dense_vector=dense_vector,
                    sparse_vector=sparse_vector,
                    child_text=chunk_pair['child_text'],
                    parent_text=chunk_pair['parent_text'],
                    metadata=chunk_metadata
                )

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
                        from hybrid_search.utils import parse_datetime
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
