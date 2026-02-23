# hybrid_search/search.py
from hybrid_search.database import Database
from hybrid_search.embed import Embed
from hybrid_search.utils import singleton, logger, Config
from typing import Dict, List
from collections import defaultdict


@singleton
class SemanticSearch:
    def __init__(self):
        self.db = Database()
        self.embedder = Embed()
        logger.info("✅ SemanticSearch инициализирован")

    def search(self, query: str, n_results: int = None) -> Dict:
        """✅ УЛУЧШЕННЫЙ поиск с группировкой по документам"""
        try:
            n_results = n_results or Config.RETRIEVAL_TOP_K

            # 1. Dense + Sparse поиск (берём больше кандидатов)
            dense_vector = self.embedder.embed_text(query)
            sparse_vector = self.embedder.embed_sparse(query)

            candidates = self.db.search(
                dense_vector,
                sparse_vector,
                n_results=n_results * 2  # Больше кандидатов для фильтрации
            )

            if not candidates:
                return {'matches': [], 'query': query}

            # 2. RERANK ПЕРЕД расширением (фильтруем шум раньше)
            reranked = self.embedder.rerank(query, candidates)

            # 3. РУППИРОВКА по документам (page_id)
            grouped = self._group_by_document(reranked)

            # 4. ДИНАМИЧЕСКОЕ расширение контекста
            expanded = self._expand_with_smart_neighbors(
                grouped,
                query,
                dense_vector,
                sparse_vector
            )

            # 5. ФИНАЛЬНЫЙ отбор топ-K
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

    def _group_by_document(self, chunks: List[Dict]) -> Dict[str, List[Dict]]:
        """Группирует чанки по document_id (page_id)"""
        grouped = defaultdict(list)
        for chunk in chunks:
            # Извлекаем page_id из chunk_id (формат: "page_id-chunk_num")
            page_id = chunk['id'].rsplit('-', 1)[0]
            grouped[page_id].append(chunk)

        # Сортировка: документы с бóльшим количеством чанков — выше
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

    def _expand_with_smart_neighbors(
            self,
            grouped: Dict[str, List[Dict]],
            query: str,
            dense_vector: list,
            sparse_vector: dict
    ) -> List[Dict]:
        """расширение контекста с приоритетом релевантных документов и ограничением чанков на документ"""
        expanded = []
        seen_ids = set()

        # Ограничение на количество чанков от одного документа
        max_chunks_per_doc = Config.MAX_CHUNKS_PER_DOC

        # Сначала добавляем ограниченное число лучших чанков из топ-документов
        for page_id, doc_chunks in list(grouped.items())[:5]:  # Топ-5 документов
            # Сортируем чанки документа по убыванию релевантности
            sorted_chunks = sorted(
                doc_chunks,
                key=lambda x: x.get('rerank_score', x.get('score', 0)),
                reverse=True
            )

            # Берём только первые max_chunks_per_doc
            top_chunks = sorted_chunks[:max_chunks_per_doc]

            # Добавляем выбранные чанки
            for chunk in top_chunks:
                if chunk['id'] not in seen_ids:
                    expanded.append(chunk)
                    seen_ids.add(chunk['id'])

            # Определяем окно расширения на основе максимального score в документе
            max_score = max(c.get('rerank_score', c.get('score', 0)) for c in doc_chunks)
            if max_score >= 0.7:
                window = 3
            elif max_score >= 0.5:
                window = 2
            else:
                window = 1

            # Расширяем соседями только для выбранных чанков (не для всех в документе)
            for chunk in top_chunks:
                neighbors = self.db.get_neighbors(chunk['id'], window=window)
                for neighbor in neighbors:
                    if neighbor['id'] not in seen_ids:
                        # Сохраняем оценку родительского чанка (с понижающим коэффициентом)
                        neighbor['score'] = chunk.get('rerank_score',
                                                      chunk.get('score', 0)) * Config.SEARCH_NEIGHBOR_SCORE_MULTIPLIER
                        neighbor['rerank_score'] = neighbor['score']
                        expanded.append(neighbor)
                        seen_ids.add(neighbor['id'])

        # Сортировка по score (rerank_score приоритет)
        expanded = sorted(
            expanded,
            key=lambda x: x.get('rerank_score', x.get('score', 0)),
            reverse=True
        )

        logger.info(f"🔗 После расширения: {len(expanded)} чанков")
        return expanded
