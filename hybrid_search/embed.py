# hybrid_search/embed.py
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from hybrid_search.utils import singleton, logger, Config
import re
import os
from scipy.special import expit


@singleton
class Embed:
    def __init__(self):
        self.device = self._get_device()
        logger.info(f"🔧 Используемое устройство: {self.device}")

        # Dense embedding модель
        logger.info("🔧 Загрузка embedding модели...")
        self.dense_model = SentenceTransformer(
            "sentence-transformers/all-mpnet-base-v2",
            device=self.device
        )

        # Reranker (cross-encoder) для точного ранжирования
        logger.info(f"🔧 Загрузка reranker модели: {Config.RERANKER_MODEL}")
        self.reranker = CrossEncoder(
            Config.RERANKER_MODEL,
            device=self.device
        )

        # Sparse: BM25
        self.bm25 = None
        self.corpus_tokens = []
        self._bm25_initialized = False
        logger.info("✅ Embed + Reranker готовы")

    def _get_device(self) -> str:
        """✅ Автоматическое определение доступного устройства"""
        force_cpu = os.getenv("FORCE_CPU", "false").lower() == "true"
        if force_cpu:
            logger.info("⚠️  Принудительное использование CPU (FORCE_CPU=true)")
            return "cpu"

        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
                logger.info(f"✅ CUDA доступна: {gpu_name} ({gpu_memory:.1f} GB)")
                return device
            else:
                logger.warning("⚠️  CUDA не доступна, используем CPU")
                return "cpu"
        except ImportError:
            logger.warning("⚠️  PyTorch не установлен, используем CPU")
            return "cpu"
        except Exception as e:
            logger.warning(f"⚠️  Ошибка проверки CUDA: {e}, используем CPU")
            return "cpu"

    def _tokenize(self, text: str) -> list[str]:
        """Токенизация для BM25"""
        return re.findall(r'\b[a-zа-яё0-9]{2,}\b', text.lower())

    def embed_text(self, text: str) -> list[float]:
        """Возвращает dense-вектор (768-dim)"""
        dense_embeddings = self.dense_model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        dense_vector = dense_embeddings.tolist()
        if isinstance(dense_vector[0], list):
            dense_vector = dense_vector[0]
        return dense_vector

    def embed_sparse(self, text: str) -> dict:
        """Возвращает sparse-вектор для BM25"""
        tokens = self._tokenize(text)
        if self._bm25_initialized and self.bm25 and tokens:
            scores = self.bm25.get_scores(tokens)
            indices = [i for i, s in enumerate(scores) if s > 1e-6]
            values = [float(scores[i]) for i in indices]
        else:
            indices, values = [0], [1e-9]
        return {"indices": indices, "values": values}

    def rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        """Ранжирует чанки с помощью cross-encoder"""
        if not chunks:
            return []

        # Формируем пары (query, chunk_text) для reranker
        pairs = [[query, chunk.get('text', chunk.get('content', ''))] for chunk in chunks]

        # Предсказываем scores
        try:
            scores = self.reranker.predict(pairs)
            logger.info(f"Raw scores: {scores}")
            # ПРИМЕНЯЕМ SIGMOID для нормализации в 0-1
            scores = expit(scores)

        except Exception as e:
            logger.error(f"❌ Ошибка rerank: {e}")
            return sorted(chunks, key=lambda x: x.get('score', 0), reverse=True)

        # Добавляем rerank_score к чанкам
        for chunk, score in zip(chunks, scores):
            chunk['rerank_score'] = float(score)

        # Фильтруем по порогу и сортируем
        filtered = [c for c in chunks if c.get('rerank_score', 0) >= Config.RERANK_MIN_SCORE]
        sorted_chunks = sorted(filtered, key=lambda x: x.get('rerank_score', 0), reverse=True)

        # Возвращаем топ-K
        return sorted_chunks[:Config.RERANK_TOP_K]

    def fit_bm25(self, documents: list[str]):
        """Инициализация BM25 на корпусе документов"""
        if not documents:
            logger.warning("⚠️  Нет документов для инициализации BM25")
            return

        logger.info(f"🔧 Инициализация BM25 на {len(documents)} документах...")
        corpus_tokens = [self._tokenize(doc) for doc in documents if doc and doc.strip()]
        corpus_tokens = [t for t in corpus_tokens if t]

        if corpus_tokens:
            self.bm25 = BM25Okapi(corpus_tokens)
            self.corpus_tokens = corpus_tokens
            self._bm25_initialized = True
            total_tokens = sum(len(t) for t in corpus_tokens)
            logger.info(f"✅ BM25 инициализирован: {len(corpus_tokens)} документов, {total_tokens} токенов")
        else:
            logger.warning("⚠️  BM25 не инициализирован")

    def embed_texts_batch(self, texts: list[str]) -> list[list[float]]:
        """Пакетная генерация эмбеддингов (быстрее в 5-10 раз)"""
        if not texts:
            return []

        dense_embeddings = self.dense_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False
        )

        if len(dense_embeddings.shape) == 1:
            dense_embeddings = dense_embeddings.reshape(1, -1)

        return dense_embeddings.tolist()

    def embed_sparse_batch(self, texts: list[str]) -> list[dict]:
        """Пакетная генерация sparse-векторов"""
        results = []
        for text in texts:
            results.append(self.embed_sparse(text))
        return results
