FROM python:3.12-slim-trixie
ENV PYTHONUNBUFFERED=1 ENV=prod PORT=8080 DOCKER=true USE_SLIM_DOCKER=true \
    SCARF_NO_ANALYTICS=true DO_NOT_TRACK=true ANONYMIZED_TELEMETRY=false
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements-slim.lock ./
RUN pip install --no-cache-dir --no-deps --require-hashes -r requirements-slim.lock
COPY package.json CHANGELOG.md /app/
COPY backend/ ./
RUN mkdir -p /app/backend/data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD curl -fsS http://127.0.0.1:8080/health || exit 1
CMD ["bash", "start.sh"]
