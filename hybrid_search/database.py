# hybrid_search/database.py
import json
import os
from typing import Optional, Dict, Any, List

import chromadb
from chromadb.config import Settings

from hybrid_search.utils import singleton, logger, Config


@singleton
class Database:
    def __init__(self):
        self.persist_dir = Config.CHROMA_DB_PATH
        self.index_name = Config.CHROMA_COLLECTION
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

        self.collection = self.client.get_or_create_collection(
            name=self.index_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:search_ef": 100,
                "hnsw:construction_ef": 100
            }
        )

        self.startup()

    def startup(self):
        count = self.collection.count()
        logger.info(f"✅ ChromaDB: {self.persist_dir}/{self.index_name} ({count} child-чанков)")

    def count(self) -> int:
        return self.collection.count()

    def clear_all(self):
        logger.warning("⚠️  Очистка базы данных...")
        while True:
            items = self.collection.get(limit=100)
            if not items['ids']:
                break
            self.collection.delete(ids=items['ids'])
        logger.info("✅ База очищена")

    def _serialize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Сериализует метаданные для ChromaDB с защитой от переполнения"""
        clean_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, list):
                if len(v) == 0:
                    continue
                # Сериализуем списки в JSON
                json_str = json.dumps(v, ensure_ascii=False)
                if len(json_str) < 1500:  # Лимит на поле
                    clean_metadata[k] = json_str
            elif isinstance(v, dict):
                # Сериализуем dict в JSON
                json_str = json.dumps(v, ensure_ascii=False)
                if len(json_str) < 1500:  # Лимит на поле
                    clean_metadata[k] = json_str
            elif v is None:
                continue
            elif isinstance(v, (str, int, float, bool)):
                if isinstance(v, str) and len(v) < 2000:  # Лимит на строку
                    clean_metadata[k] = v
            # else: пропускаем неподдерживаемые типы
        return clean_metadata

    def _deserialize_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Десериализует JSON-строки обратно"""
        if not raw_metadata:
            return {}
        metadata = {}
        for k, v in raw_metadata.items():
            if isinstance(v, str):
                if v.startswith('[') or v.startswith('{'):
                    try:
                        metadata[k] = json.loads(v)
                    except:
                        metadata[k] = v
                else:
                    metadata[k] = v
            else:
                metadata[k] = v
        return metadata

    def upsert_child_chunk(self, chunk_id: str, dense_vector: list, sparse_vector: dict,
                           child_text: str, parent_text: str, metadata: Dict[str, Any]):
        """Добавление child-чанка с гарантированным сохранением parent_id"""
        try:
            compressed_parent = self._compress_parent_text(parent_text)

            parent_id = metadata.get('parent_id')
            if not parent_id:
                parent_id = chunk_id.replace('-child-', '-parent-')

            full_metadata = {
                'parent_id': parent_id,
                'content': child_text,
                'parent_text': compressed_parent,
                'sparse_indices': sparse_vector['indices'],
                'sparse_values': sparse_vector['values'],
            }

            for k, v in metadata.items():
                if k not in full_metadata:
                    full_metadata[k] = v

            clean_metadata = self._serialize_metadata(full_metadata)

            logger.debug(f"📦 Upsert {chunk_id}: parent_id={clean_metadata.get('parent_id', '❌ НЕТ')}, "
                         f"fields={len(clean_metadata)}, size={sum(len(str(v)) for v in clean_metadata.values())}")

            if 'parent_id' not in clean_metadata:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: parent_id потерян перед upsert! chunk_id={chunk_id}")
                logger.error(f"   full_metadata keys: {list(full_metadata.keys())}")
                logger.error(f"   clean_metadata keys: {list(clean_metadata.keys())}")
                raise ValueError(f"parent_id потерян для {chunk_id}")

            if isinstance(dense_vector[0], list):
                dense_vector = dense_vector[0]

            self.collection.upsert(
                ids=[chunk_id],
                embeddings=[dense_vector],
                metadatas=[clean_metadata],
                documents=[child_text]
            )

            verify = self.collection.get(ids=[chunk_id], include=['metadatas'])
            if verify.get('metadatas') and verify['metadatas'][0]:
                stored_parent = verify['metadatas'][0].get('parent_id')
                if not stored_parent:
                    logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: parent_id потерян ПОСЛЕ upsert! chunk_id={chunk_id}")
                else:
                    logger.debug(f"✅ parent_id сохранён: {stored_parent}")

        except Exception as e:
            logger.error(f"❌ Ошибка upsert child {chunk_id}: {e}")
            raise

    def _compress_parent_text(self, text: str, max_chars: int = 3000) -> str:
        """Сжимает parent текст для хранения в метаданных"""
        if len(text) <= max_chars:
            return text
        return text[:max_chars // 2] + "\n...[сокращено]...\n" + text[-max_chars // 2:]

    def search_children(self, dense_vector: list, sparse_vector: dict,
                        n_results: int = None, where: Dict = None) -> List[Dict]:
        """Поиск child-чанков"""
        try:
            n_results = n_results or Config.RETRIEVAL_TOP_K

            if isinstance(dense_vector[0], list):
                dense_vector = dense_vector[0]

            dense_results = self.collection.query(
                query_embeddings=[dense_vector],
                n_results=n_results * 3,
                where=where,
                include=['metadatas', 'documents', 'distances']
            )

            chunks = []
            if dense_results.get('ids') and dense_results['ids'][0]:
                for i, doc_id in enumerate(dense_results['ids'][0]):
                    raw_metadata = dense_results['metadatas'][0][i] if dense_results.get('metadatas') else {}
                    metadata = self._deserialize_metadata(raw_metadata)

                    chunk = {
                        'id': doc_id,
                        'text': dense_results['documents'][0][i] if dense_results.get('documents') else '',
                        'metadata': metadata,
                        'score': 1.0 - (dense_results['distances'][0][i] if dense_results.get('distances') else 1.0)
                    }
                    chunks.append(chunk)

            # Boosting по sparse-совпадениям
            if sparse_vector.get('indices') and sparse_vector['indices'][0] != 0:
                query_indices = set(sparse_vector['indices'])
                for chunk in chunks:
                    doc_sparse = set(chunk['metadata'].get('sparse_indices', []))
                    overlap = len(query_indices & doc_sparse)
                    if overlap > 0:
                        chunk['score'] += 0.1 * overlap

            return chunks

        except Exception as e:
            logger.error(f"❌ Ошибка поиска child-чанков: {e}")
            return []

    def get_parents_by_ids(self, parent_ids: List[str]) -> Dict[str, Dict]:
        """Массовая загрузка parent-блоков по ID"""
        if not parent_ids:
            return {}

        results = {}
        batch_size = 100

        for i in range(0, len(parent_ids), batch_size):
            batch = parent_ids[i:i + batch_size]
            try:
                batch_result = self.collection.get(ids=batch, include=['metadatas'])
                if batch_result.get('metadatas'):
                    for idx, pid in enumerate(batch_result['ids']):
                        if idx < len(batch_result['metadatas']):
                            raw_meta = batch_result['metadatas'][idx]
                            metadata = self._deserialize_metadata(raw_meta)
                            parent_text = metadata.get('parent_text', '')
                            results[pid] = {
                                'text': parent_text,
                                'metadata': metadata
                            }
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки parents: {e}")

        return results

    def get_text(self, id: str) -> str:
        """Получение текста по ID"""
        try:
            result = self.collection.get(ids=[id], include=['metadatas'])
            if result['metadatas'] and result['metadatas'][0]:
                return result['metadatas'][0].get('content', '')
        except Exception as e:
            logger.error(f"❌ Ошибка получения текста {id}: {e}")
        return ""

    def get_metadata(self, id: str) -> Optional[Dict[str, Any]]:
        """Получение метаданных по ID"""
        try:
            result = self.collection.get(ids=[id], include=['metadatas'])
            if result['metadatas'] and result['metadatas'][0]:
                return self._deserialize_metadata(result['metadatas'][0])
        except Exception as e:
            logger.error(f"❌ Ошибка получения метаданных {id}: {e}")
        return None
