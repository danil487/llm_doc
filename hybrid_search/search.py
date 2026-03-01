# hybrid_search/search.py
from collections import defaultdict
from typing import Dict, List, Optional

from hybrid_search.database import Database
from hybrid_search.embed import Embed
from hybrid_search.utils import singleton, logger, Config


@singleton
class SemanticSearch:
    def __init__(self):
        self.db = Database()
        self.embedder = Embed()
        logger.info("✅ SemanticSearch инициализирован (Parent-Child)")

    def search(self, query: str, n_results: int = None) -> Dict:
        """Parent-Child поиск"""
        try:
            n_results = n_results or Config.RETRIEVAL_TOP_K

            # 1. Поиск child-чанков
            dense_vector = self.embedder.embed_text(query)
            sparse_vector = self.embedder.embed_sparse(query)

            child_candidates = self.db.search_children(
                dense_vector, sparse_vector,
                n_results=n_results * 3
            )

            if not child_candidates:
                return {'matches': [], 'query': query, 'type': 'child_search'}

            # 2. Reranking child-чанков
            reranked_children = self.embedder.rerank(query, child_candidates)

            # 3. Фильтрация по порогу
            filtered_children = [
                c for c in reranked_children
                if c.get('rerank_score', c.get('score', 0)) >= Config.CHILD_MIN_SCORE
            ]

            if not filtered_children:
                return {'matches': [], 'query': query, 'type': 'child_search_filtered'}

            # 4. Группировка child → parent
            parent_groups = self._group_children_to_parents(filtered_children)

            # 5. Формирование финальных матчей с parent-текстами
            final_matches = []
            for parent_id, parent_data in parent_groups.items():
                # Проверяем что parent_text не пустой
                if not parent_data.get('text'):
                    logger.warning(f"⚠️  Parent {parent_id} без текста, пропускаем")
                    continue

                child_scores = parent_data['child_scores']

                final_matches.append({
                    'id': parent_id,
                    'text': parent_data['text'],
                    'metadata': parent_data['metadata'],
                    'score': max(child_scores) if child_scores else 0,
                    'child_count': len(child_scores),
                    'child_scores': child_scores,
                    'type': 'parent'
                })

            # 6. Сортировка по score
            final_matches = sorted(
                final_matches,
                key=lambda x: x.get('score', 0),
                reverse=True
            )[:Config.RERANK_TOP_K]

            logger.info(
                f"📊 Parent-Child поиск: "
                f"{len(child_candidates)} child → "
                f"{len(filtered_children)} после rerank → "
                f"{len(parent_groups)} parents → "
                f"{len(final_matches)} финальных"
            )

            return {
                'matches': final_matches,
                'query': query,
                'type': 'parent_child'
            }

        except Exception as e:
            logger.error(f"❌ Ошибка Parent-Child поиска: {e}")
            return {'matches': [], 'query': query, 'error': str(e), 'type': 'error'}

    def _group_children_to_parents(self, children: List[Dict]) -> Dict[str, Dict]:
        """
        Группирует child-чанки по parent_id и собирает parent_text из metadata

        Returns:
            Dict[parent_id, {
                'text': str,
                'metadata': dict,
                'child_scores': [float]
            }]
        """
        groups = defaultdict(lambda: {'child_scores': [], 'parent_text': '', 'metadata': {}})
        missing_parent_count = 0

        for child in children:
            # Получаем parent_id из metadata
            parent_id = (
                    child.get('metadata', {}).get('parent_id') or
                    child.get('parent_id') or
                    self._extract_parent_id_fallback(child)
            )

            if parent_id:
                score = child.get('rerank_score', child.get('score', 0))
                groups[parent_id]['child_scores'].append(score)

                # Берём parent_text из metadata child-чанка
                if not groups[parent_id]['parent_text']:
                    groups[parent_id]['parent_text'] = child.get('metadata', {}).get('parent_text', '')
                    groups[parent_id]['metadata'] = child.get('metadata', {}).copy()
            else:
                missing_parent_count += 1
                logger.warning(f"⚠️ Child chunk missing parent_id: {child.get('id', 'unknown_id')}")

        if missing_parent_count > 0:
            logger.warning(f"⚠️ {missing_parent_count} из {len(children)} детей без parent_id")

        # Преобразуем в формат для final_matches
        result = {}
        for parent_id, data in groups.items():
            result[parent_id] = {
                'text': data['parent_text'],
                'metadata': data['metadata'],
                'child_scores': data['child_scores']
            }

        return result

    def _extract_parent_id_fallback(self, child: Dict) -> Optional[str]:
        """Резервный метод извлечения parent_id из шаблона child_id"""
        child_id = child.get('id', '')
        if '-child-' in child_id:
            # Преобразуем child-5 в parent-5
            parts = child_id.split('-child-')
            if len(parts) == 2:
                return f"{parts[0]}-parent-{parts[1]}"
        return None
