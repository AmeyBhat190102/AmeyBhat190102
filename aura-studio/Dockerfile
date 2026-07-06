FROM python:3.11-slim

# Chromium deps for the layout engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-liberation && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && playwright install --with-deps chromium

COPY tests ./tests
COPY migrations ./migrations

# api:    uvicorn aura.api.main:app --host 0.0.0.0 --port 8800
# worker: arq aura.worker.WorkerSettings
CMD ["uvicorn", "aura.api.main:app", "--host", "0.0.0.0", "--port", "8800"]
