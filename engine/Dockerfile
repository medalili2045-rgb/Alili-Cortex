FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ALILI_ENGINE_HOST=0.0.0.0 \
    ALILI_ENGINE_PORT=8765 \
    ALILI_ENGINE_DB_PATH=/data/jobs.sqlite3

WORKDIR /app
COPY engine/alili_engine /app/alili_engine
RUN mkdir -p /data && useradd --system --uid 10001 engine && chown -R engine:engine /data /app
USER engine

EXPOSE 8765
CMD ["python", "-m", "alili_engine.api"]
