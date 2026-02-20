# hybrid_search/search.py
from hybrid_search.database import Database
from hybrid_search.embed import Embed
from hybrid_search.utils import singleton, logger, Config
from typing import Dict, List


@singleton
class SemanticSearch:
    def __init__(self):
        self.db = Database()
        self.embedder = Embed()
        logger.info("✅ SemanticSearch инициализирован")

    def search(self, query: str, n_results: int = None) -> Dict:
        """Поиск с расширением контекста соседними чанками"""
        try:
            n_results = n_results or Config.RETRIEVAL_TOP_K

            dense_vector = self.embedder.embed_text(query)
            sparse_vector = self.embedder.embed_sparse(query)

            matches = self.db.search(dense_vector, sparse_vector, n_results=n_results)

            if not matches:
                return {'matches': [], 'query': query}

            # ✅ РАСШИРЕНИЕ СОСЕДЯМИ
            expanded_matches = self._expand_with_neighbors(matches, window=Config.SEARCH_NEIGHBOR_WINDOW)

            # Reranking
            reranked = self.embedder.rerank(query, expanded_matches)

            return {'matches': reranked, 'query': query}
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return {'matches': [], 'query': query, 'error': str(e)}

    def _expand_with_neighbors(self, matches: List[Dict], window: int = 1) -> List[Dict]:
        """✅ Добавляет соседние чанки к результатам поиска"""
        expanded = []
        seen_ids = set()

        for match in matches:
            chunk_id = match['id']

            if chunk_id not in seen_ids:
                expanded.append(match)
                seen_ids.add(chunk_id)

            neighbors = self.db.get_neighbors(chunk_id, window=window)
            for neighbor in neighbors:
                if neighbor['id'] not in seen_ids:
                    neighbor['score'] = match['score'] * Config.SEARCH_NEIGHBOR_SCORE_MULTIPLIER
                    expanded.append(neighbor)
                    seen_ids.add(neighbor['id'])

        return sorted(expanded, key=lambda x: x.get('score', 0), reverse=True)
