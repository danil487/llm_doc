# hybrid_search/chunk.py
from typing import List, Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from hybrid_search.utils import singleton, logger, Config


@singleton
class ParentChildChunker:
    """
    Parent-Child чанкер:
    - Child chunks: маленькие (250 токенов) для точного семантического поиска
    - Parent blocks: большие (2000 токенов) для подачи в LLM
    - Каждый child ссылается на свой parent_id
    """

    def __init__(self):
        # Child splitter для поиска
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHILD_CHUNK_SIZE,
            chunk_overlap=Config.CHILD_CHUNK_OVERLAP,
            length_function=len,
            separators=self._get_separators()
        )

        # Parent splitter для контекста
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.PARENT_BLOCK_SIZE,
            chunk_overlap=Config.PARENT_CHUNK_OVERLAP,
            length_function=len,
            separators=self._get_separators()
        )

        logger.info(f"✅ ParentChildChunker: child={Config.CHILD_CHUNK_SIZE}, parent={Config.PARENT_BLOCK_SIZE}")

    def _get_separators(self) -> List[str]:
        """Семантические разделители для сохранения структуры"""
        return [
            "\n## ", "\n### ", "\n#### ",
            "\n|",
            "\n```",
            "\n• ", "\n1. ",
            "\n\n", "\n", ". ", " ", ""
        ]

    def chunk_page(self, text: str, page_id: str, structure_meta: dict = None) -> List[Dict]:
        """
        Создаёт child-parent пары для индексации

        Returns:
            List[Dict]: [
                {
                    'child_id': 'page_123-child_5',
                    'child_text': '...',
                    'parent_id': 'page_123-parent_2',
                    'parent_text': '...',
                    'metadata': {...}
                },
                ...
            ]
        """
        if not text.strip():
            return []

        # 1. Создаём parent-блоки (большие, для контекста)
        parent_chunks = self.parent_splitter.split_text(text)
        parent_map = {}

        for p_idx, parent_text in enumerate(parent_chunks):
            parent_id = f"{page_id}-parent-{p_idx}"
            parent_map[parent_id] = parent_text

        # 2. Создаём child-чанки (маленькие, для поиска)
        child_chunks = self.child_splitter.split_text(text)

        # 3. Сопоставляем child → parent по перекрытию текста
        results = []
        for c_idx, child_text in enumerate(child_chunks):
            best_parent_id = None
            best_overlap = 0

            for parent_id, parent_text in parent_map.items():
                child_words = set(child_text.lower().split())
                parent_words = set(parent_text.lower().split())
                overlap = len(child_words & parent_words) / max(len(child_words), 1)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_parent_id = parent_id

            if not best_parent_id:
                best_parent_id = list(parent_map.keys())[0] if parent_map else f"{page_id}-parent-0"

            child_id = f"{page_id}-child-{c_idx}"

            results.append({
                'child_id': child_id,
                'child_text': child_text,
                'parent_id': best_parent_id,
                'parent_text': parent_map[best_parent_id],
                'metadata': {
                    'page_id': page_id,
                    'parent_id': best_parent_id,
                    'child_index': c_idx,
                    'parent_index': int(best_parent_id.split('-')[-1]),
                    'total_children': len(child_chunks),
                    'total_parents': len(parent_chunks),
                    'structure_meta': structure_meta or {}
                }
            })

        logger.debug(f"📦 {page_id}: {len(results)} child-parent пар")
        return results
