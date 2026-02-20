# hybrid_search/chunk.py

from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from hybrid_search.utils import singleton, logger


@singleton
class SemanticChunk:
    def __init__(self):
        try:
            self.hf_embedder = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-mpnet-base-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            # ✅ БЫСТРЫЙ сплиттер вместо SemanticChunker
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            self._use_langchain = True
            logger.info("✅ RecursiveCharacterTextSplitter инициализирован (быстрый)")
        except Exception as e:
            logger.warning(f"⚠️  LangChain не доступен: {e}")
            self._use_langchain = False

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

    def _fallback_split(self, text: str, max_chunk_size: int = 500) -> list[str]:
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
