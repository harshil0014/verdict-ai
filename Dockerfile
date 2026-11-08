FROM node:22-bookworm-slim AS web
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock.txt /app/backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY backend/ /app/backend/
COPY --from=web /build/frontend/dist /app/frontend/dist
RUN useradd --create-home verdict && mkdir -p /data && chown verdict:verdict /data
USER verdict
ENV VERDICT_DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh","-c","exec uvicorn ${VERDICT_APP_MODULE:-app:app} --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
