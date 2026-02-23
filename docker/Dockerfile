# docker/Dockerfile
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    jq \
    libgl1 \
    libglib2.0-0 \
    wget \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY hybrid_search/ ./hybrid_search/
COPY rag_llm/ ./rag_llm/
COPY telegram_bot/ ./telegram_bot/
COPY controllers/ ./controllers/
COPY main.py .

RUN mkdir -p /app/data/chroma_db /app/.cache /app/logs

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 8443

ENV PYTHONPATH=/app
ENV TOKENIZERS_PARALLELISM=true
ENV FORCE_CPU=false
ENV CUDA_VISIBLE_DEVICES=0
ENV NVIDIA_VISIBLE_DEVICES=all

ENTRYPOINT ["/entrypoint.sh"]