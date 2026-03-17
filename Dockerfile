FROM python:3.11-slim

# Install Node.js 20 and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# === BACKEND ===
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-bake embedding model
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding('sentence-transformers/all-MiniLM-L6-v2').embed(['warmup']))"
COPY backend/app/ ./app/
RUN mkdir -p /app/data/uploads /app/data/chroma

# === FRONTEND ===
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# === RUN ===
COPY supervisord.conf /etc/supervisor/conf.d/app.conf
WORKDIR /app
EXPOSE 3000
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/app.conf"]
