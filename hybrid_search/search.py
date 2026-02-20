# hybrid_search/search.py

from hybrid_search import database, embed
from hybrid_search.utils import logger, Config
from typing import List, Dict, Optional


class SemanticSearch:
    def __init__(self):
        self.db = database.Database()
        self.embedder = embed.Embed()
        logger.info("✅ SemanticSearch инициализирован")

    def search(self, query: str,
               where_filter: Optional[Dict] = None,
               use_rerank: bool = True) -> Dict:
        """
        Полный пайплайн поиска: retrieval → rerank → format.

        Args:
            query: Поисковый запрос
            where_filter: Фильтр по метаданным (ChromaDB where-синтаксис)
            use_rerank: Использовать ли cross-encoder reranking

        Returns:
            Dict с полями: matches (список чанков), query, metadata
        """
        try:
            # 1. Векторизация запроса
            dense_vector = self.embedder.embed_text(query)
            sparse_vector = self.embedder.embed_sparse(query)

            # 2. Первичный поиск (retrieval)
            chunks = self.db.search(
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                n_results=Config.RETRIEVAL_TOP_K,
                where=where_filter
            )

            if not chunks:
                logger.warning("⚠️  Поиск не вернул результатов")
                return {'matches': [], 'query': query}

            logger.debug(f"🔍 Retrieval: найдено {len(chunks)} чанков")

            # 3. Ранжирование (reranking)
            if use_rerank and Config.RERANK_TOP_K > 0:
                chunks = self.embedder.rerank(query, chunks)
                logger.debug(f"🔄 Rerank: осталось {len(chunks)} чанков после фильтрации")

            # 4. Форматирование результата
            matches = []
            for chunk in chunks:
                match = {
                    'id': chunk.get('id'),
                    'score': chunk.get('rerank_score') or chunk.get('score', 0),
                    'text': chunk.get('text', ''),
                    'metadata': {
                        'title': chunk.get('metadata', {}).get('title', ''),
                        'section': chunk.get('metadata', {}).get('section', ''),
                        'url': chunk.get('metadata', {}).get('url', ''),
                        'document_id': chunk.get('metadata', {}).get('document_id', ''),
                        'content': chunk.get('metadata', {}).get('content', '')  # текст чанка
                    }
                }
                matches.append(match)

            return {
                'matches': matches,
                'query': query,
                'metadata': {
                    'retrieved': len(chunks),
                    'reranked': use_rerank,
                    'model': Config.RERANKER_MODEL
                }
            }

        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return {'matches': [], 'query': query, 'error': str(e)}
