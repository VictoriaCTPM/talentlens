FROM python:3.10-slim

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-bake the embedding model into the image so Railway never downloads it at runtime
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding('sentence-transformers/all-MiniLM-L6-v2').embed(['warmup']))"

# Copy application code
COPY app/ ./app/

# Create data directories
RUN mkdir -p data/uploads data/chroma

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
