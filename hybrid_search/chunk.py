# hybrid_search/chunk.py
from langchain_text_splitters import RecursiveCharacterTextSplitter
from hybrid_search.embed import Embed  # ← Используем общий Embed
from hybrid_search.utils import singleton, logger, Config


@singleton
class SemanticChunk:
    def __init__(self):
        self.embedder = Embed()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            length_function=len,
            separators=self._parse_separators()
        )
        self._use_langchain = True
        logger.info(
            f"✅ RecursiveCharacterTextSplitter инициализирован (size={Config.CHUNK_SIZE}, overlap={Config.CHUNK_OVERLAP})")

    def _parse_separators(self) -> list[str]:
        """Парсит CHUNK_SEPARATORS из строки в список"""
        try:
            separators = Config.CHUNK_SEPARATORS.split(',')
            return [s.strip() for s in separators if s.strip()]
        except:
            return ["\n\n", "\n", ". ", " ", ""]

    def split(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        if self._use_langchain:
            try:
                docs = self.text_splitter.split_text(text)
                if docs:
                    return [d for d in docs if d.strip()]
            except Exception as e:
                logger.warning(f"⚠️  Ошибка чанкинга: {e}")
                return self._fallback_split(text)
        return self._fallback_split(text)

    def _fallback_split(self, text: str, max_chunk_size: int = None) -> list[str]:
        if max_chunk_size is None:
            max_chunk_size = Config.CHUNK_SIZE

        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += "\n" + para if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para
        if current_chunk:
            chunks.append(current_chunk)
        return chunks
