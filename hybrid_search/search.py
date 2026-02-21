# hybrid_search/search.py
from hybrid_search.database import Database
from hybrid_search.embed import Embed
from hybrid_search.utils import singleton, logger, Config
from typing import Dict, List
from collections import defaultdict
import re


@singleton
class SemanticSearch:
    def __init__(self):
        self.db = Database()
        self.embedder = Embed()
        logger.info("✅ SemanticSearch инициализирован")

    def search(self, query: str, n_results: int = None) -> Dict:
        """✅ УЛУЧШЕННЫЙ поиск с приоритетом релевантных документов"""
        try:
            n_results = n_results or Config.RETRIEVAL_TOP_K

            # 1. Dense + Sparse поиск (берём больше кандидатов)
            dense_vector = self.embedder.embed_text(query)
            sparse_vector = self.embedder.embed_sparse(query)

            candidates = self.db.search(
                dense_vector,
                sparse_vector,
                n_results=n_results * 3  # ← Больше кандидатов для фильтрации
            )

            if not candidates:
                return {'matches': [], 'query': query}

            # 2. ✅ BOOST для заголовков с ключевыми словами
            candidates = self._boost_by_title(candidates, query)

            # 3. ✅ RERANK ПЕРЕД расширением
            reranked = self.embedder.rerank(query, candidates)

            # 4. ✅ ГРУППИРОВКА по документам
            grouped = self._group_by_document(reranked)

            # 5. ✅ ПРИОРИТЕТ документам с несколькими чанками
            expanded = self._expand_with_priority(grouped, query, dense_vector, sparse_vector)

            # 6. ✅ ФИНАЛЬНЫЙ отбор
            final_matches = expanded[:Config.RERANK_TOP_K]

            logger.info(
                f"📊 Поиск: {len(candidates)} кандидатов → "
                f"{len(reranked)} после rerank → "
                f"{len(grouped)} документов → "
                f"{len(final_matches)} финальных чанков"
            )

            return {'matches': final_matches, 'query': query}

        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return {'matches': [], 'query': query, 'error': str(e)}

    def _boost_by_title(self, chunks: List[Dict], query: str) -> List[Dict]:
        """✅ Повышает score чанкам из документов с ключевыми словами в title"""
        query_keywords = set(query.lower().split())
        technical_terms = {'модель', 'document', 'base', 'класс', 'инструкция', 'создание', 'реализация'}

        for chunk in chunks:
            title = chunk.get('metadata', {}).get('title', '').lower()

            # ✅ Boost если title содержит ключевые слова
            title_words = set(title.split())
            overlap = len(query_keywords & title_words)
            tech_overlap = len(technical_terms & title_words)

            if overlap >= 2 or tech_overlap >= 1:
                chunk['score'] = chunk.get('score', 0) * 1.5  # +50%
                chunk['rerank_score'] = chunk.get('rerank_score', chunk.get('score', 0)) * 1.5
                logger.debug(f"📈 Boost для '{title[:50]}': +50%")

        return sorted(chunks, key=lambda x: x.get('score', 0), reverse=True)

    def _group_by_document(self, chunks: List[Dict]) -> Dict[str, List[Dict]]:
        """✅ Группирует чанки по document_id (page_id)"""
        grouped = defaultdict(list)
        for chunk in chunks:
            page_id = chunk['id'].rsplit('-', 1)[0]
            grouped[page_id].append(chunk)

        # ✅ Сортировка: документы с бóльшим количеством чанков — выше
        sorted_docs = sorted(
            grouped.items(),
            key=lambda x: (
                len(x[1]),  # Количество чанков (приоритет)
                max(c.get('rerank_score', c.get('score', 0)) for c in x[1])  # Максимальный score
            ),
            reverse=True
        )

        logger.info(f"📁 Найдено документов: {len(sorted_docs)}")
        for doc_id, doc_chunks in sorted_docs[:5]:
            avg_score = sum(c.get('rerank_score', c.get('score', 0)) for c in doc_chunks) / len(doc_chunks)
            logger.info(f"   • {doc_id}: {len(doc_chunks)} чанков (avg score: {avg_score:.3f})")

        return dict(sorted_docs)

    def _expand_with_priority(
            self,
            grouped: Dict[str, List[Dict]],
            query: str,
            dense_vector: list,
            sparse_vector: dict
    ) -> List[Dict]:
        """✅ УМНОЕ расширение с приоритетом релевантных документов"""
        expanded = []
        seen_ids = set()

        # ✅ Сначала добавляем все чанки из топ-документов
        for page_id, doc_chunks in list(grouped.items())[:5]:  # Топ-5 документов
            for chunk in sorted(doc_chunks, key=lambda x: x.get('rerank_score', x.get('score', 0)), reverse=True):
                if chunk['id'] not in seen_ids:
                    expanded.append(chunk)
                    seen_ids.add(chunk['id'])

            # ✅ Расширение соседями для релевантных документов
            max_score = max(c.get('rerank_score', c.get('score', 0)) for c in doc_chunks)
            window = 3 if max_score >= 0.6 else 2 if max_score >= 0.4 else 1

            for chunk in doc_chunks:
                neighbors = self.db.get_neighbors(chunk['id'], window=window)
                for neighbor in neighbors:
                    if neighbor['id'] not in seen_ids:
                        neighbor['score'] = chunk.get('rerank_score',
                                                      chunk.get('score', 0)) * Config.SEARCH_NEIGHBOR_SCORE_MULTIPLIER
                        neighbor['rerank_score'] = neighbor['score']
                        expanded.append(neighbor)
                        seen_ids.add(neighbor['id'])

        # ✅ Сортировка по score
        expanded = sorted(
            expanded,
            key=lambda x: x.get('rerank_score', x.get('score', 0)),
            reverse=True
        )

        logger.info(f"🔗 После расширения: {len(expanded)} чанков")
        return expanded
