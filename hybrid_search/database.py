# hybrid_search/database.py
import chromadb
from chromadb.config import Settings
from hybrid_search.utils import singleton, logger, Config, extract_metadata_from_confluence
import os
import json
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

    def upsert_page(self, chunk_id: str, dense_vector: list, sparse_vector: dict,
                    text: str, metadata: Dict[str, Any]):
        """Добавление/обновление чанка с расширенными метаданными"""
        try:
            # ✅ Очистка метаданных от пустых списков (ChromaDB не принимает [])
            clean_metadata = {
                'content': text,
                'sparse_indices': json.dumps(sparse_vector['indices']),
                'sparse_values': json.dumps(sparse_vector['values'])
            }

            # Добавляем пользовательские метаданные, пропуская пустые списки
            for k, v in metadata.items():
                if isinstance(v, list) and len(v) == 0:
                    continue  # Пропускаем пустые списки
                if v is None:
                    continue  # Пропускаем None

                if isinstance(v, list):
                    clean_metadata[k] = json.dumps(v)
                elif isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                else:
                    clean_metadata[k] = str(v)  # Конвертируем остальное в строку

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
        """
        Поиск с поддержкой фильтрации по метаданным.
        """
        try:
            from collections import defaultdict
            n_results = n_results or Config.RETRIEVAL_TOP_K

            if isinstance(dense_vector[0], list):
                dense_vector = dense_vector[0]

            # Dense-поиск с фильтрацией
            dense_results = self.collection.query(
                query_embeddings=[dense_vector],
                n_results=n_results * 2,  # Берём больше для rerank
                where=where,
                include=['metadatas', 'documents', 'distances']
            )

            # Формируем список чанков для rerank
            chunks = []
            if dense_results.get('ids') and dense_results['ids'][0]:
                for i, doc_id in enumerate(dense_results['ids'][0]):
                    raw_metadata = dense_results['metadatas'][0][i] if dense_results.get('metadatas') else {}

                    # ✅ ДЕСЕРИАЛИЗАЦИЯ JSON-строк обратно в списки
                    metadata = {}
                    for k, v in raw_metadata.items():
                        if k in ['sparse_indices', 'sparse_values']:
                            try:
                                metadata[k] = json.loads(v) if isinstance(v, str) else v
                            except:
                                metadata[k] = v
                        else:
                            metadata[k] = v

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
                raw_metadata = result['metadatas'][0]
                # ✅ ДЕСЕРИАЛИЗАЦИЯ
                metadata = {}
                for k, v in raw_metadata.items():
                    if k in ['sparse_indices', 'sparse_values']:
                        try:
                            metadata[k] = json.loads(v) if isinstance(v, str) else v
                        except:
                            metadata[k] = v
                    else:
                        metadata[k] = v
                return metadata
        except Exception as e:
            logger.error(f"❌ Ошибка получения метаданных {id}: {e}")
        return None

    def upsert_batch(self, chunk_ids: list[str], dense_vectors: list[list[float]],
                     sparse_vectors: list[dict], texts: list[str],
                     metadatas: list[Dict[str, Any]]):
        """Пакетная запись в ChromaDB"""
        import json
        try:
            clean_metadatas = []
            for metadata, sparse_vector in zip(metadatas, sparse_vectors):
                clean_metadata = {
                    'content': texts[metadatas.index(metadata)],
                    'sparse_indices': json.dumps(sparse_vector['indices']),
                    'sparse_values': json.dumps(sparse_vector['values'])
                }
                for k, v in metadata.items():
                    if isinstance(v, list) and len(v) == 0:
                        continue
                    if v is None:
                        continue
                    if isinstance(v, list):
                        clean_metadata[k] = json.dumps(v)
                    elif isinstance(v, (str, int, float, bool)):
                        clean_metadata[k] = v
                    else:
                        clean_metadata[k] = str(v)
                clean_metadatas.append(clean_metadata)

            self.collection.upsert(
                ids=chunk_ids,
                embeddings=dense_vectors,
                metadatas=clean_metadatas,
                documents=texts
            )
        except Exception as e:
            logger.error(f"❌ Ошибка batch upsert: {e}")
            raise
