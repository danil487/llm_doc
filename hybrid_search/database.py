# hybrid_search/database.py
import chromadb
from chromadb.config import Settings
from hybrid_search.utils import singleton, logger, Config
import os
import json  # ← Добавить
from typing import Optional, Dict, Any, List


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
        logger.info(f"✅ ChromaDB: {self.persist_dir}/{self.index_name} ({count} документов)")

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
        """✅ Сериализует все списки в JSON-строки для ChromaDB"""
        clean_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, list):
                if len(v) == 0:
                    continue  # Пропускаем пустые списки
                clean_metadata[k] = json.dumps(v)  # ← Сериализуем
            elif v is None:
                continue  # Пропускаем None
            elif isinstance(v, (str, int, float, bool)):
                clean_metadata[k] = v
            else:
                clean_metadata[k] = str(v)
        return clean_metadata

    def _deserialize_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """✅ Десериализует JSON-строки обратно в списки"""
        if not raw_metadata:
            return {}

        metadata = {}
        for k, v in raw_metadata.items():
            if isinstance(v, str):
                # Пробуем распарсить как JSON
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

    def upsert_page(self, chunk_id: str, dense_vector: list, sparse_vector: dict,
                    text: str, metadata: Dict[str, Any]):
        """Добавление/обновление чанка с расширенными метаданными"""
        try:
            # ✅ Сериализация метаданных
            clean_metadata = {
                'content': text,
                'sparse_indices': json.dumps(sparse_vector['indices']),  # ← JSON
                'sparse_values': json.dumps(sparse_vector['values'])  # ← JSON
            }

            # Добавляем пользовательские метаданные
            for k, v in metadata.items():
                if isinstance(v, list) and len(v) == 0:
                    continue
                if v is None:
                    continue
                if isinstance(v, list):
                    clean_metadata[k] = json.dumps(v)  # ← Сериализуем
                elif isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                else:
                    clean_metadata[k] = str(v)

            if isinstance(dense_vector[0], list):
                dense_vector = dense_vector[0]

            self.collection.upsert(
                ids=[chunk_id],
                embeddings=[dense_vector],
                metadatas=[clean_metadata],
                documents=[text]
            )
        except Exception as e:
            logger.error(f"❌ Ошибка upsert для {chunk_id}: {e}")
            raise

    def search(self, dense_vector: list, sparse_vector: dict,
               n_results: int = None, where: Dict = None) -> List[Dict]:
        """Поиск с поддержкой фильтрации по метаданным"""
        try:
            n_results = n_results or Config.RETRIEVAL_TOP_K

            if isinstance(dense_vector[0], list):
                dense_vector = dense_vector[0]

            dense_results = self.collection.query(
                query_embeddings=[dense_vector],
                n_results=n_results * 2,
                where=where,
                include=['metadatas', 'documents', 'distances']
            )

            chunks = []
            if dense_results.get('ids') and dense_results['ids'][0]:
                for i, doc_id in enumerate(dense_results['ids'][0]):
                    raw_metadata = dense_results['metadatas'][0][i] if dense_results.get('metadatas') else {}

                    # ✅ Десериализация метаданных
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
            logger.error(f"❌ Ошибка поиска: {e}")
            return []

    def get_neighbors(self, chunk_id: str, window: int = 1) -> List[Dict]:
        """✅ ПОЛУЧЕНИЕ СОСЕДНИХ ЧАНКОВ (решает проблему фрагментации)"""
        neighbors = []
        parts = chunk_id.rsplit('-', 1)
        if len(parts) != 2:
            return neighbors

        page_id, chunk_num = parts[0], int(parts[1])

        for offset in range(-window, window + 1):
            if offset == 0:
                continue

            neighbor_id = f"{page_id}-{chunk_num + offset}"
            try:
                result = self.collection.get(
                    ids=[neighbor_id],
                    include=['metadatas', 'documents']
                )
                if result['ids'] and result['ids'][0]:
                    raw_metadata = result['metadatas'][0][0] if result.get('metadatas') else {}
                    metadata = self._deserialize_metadata(raw_metadata)

                    neighbors.append({
                        'id': neighbor_id,
                        'text': result['documents'][0][0] if result.get('documents') else '',
                        'metadata': metadata,
                        'is_neighbor': True,
                        'offset': offset
                    })
            except Exception as e:
                logger.debug(f"⚠️  Сосед {neighbor_id} не найден: {e}")
                continue

        return neighbors

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
