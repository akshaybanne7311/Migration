FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Persistent data (registry.db, per-session dbs, uploaded archives) lives
# here -- mount a volume at this path in production so sessions survive a
# container restart/redeploy.
ENV F5CI_DATA_DIR=/data
RUN mkdir -p /data && useradd --create-home --shell /bin/false f5ci \
    && chown -R f5ci:f5ci /app /data
USER f5ci

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/v1/health || exit 1

# 4 workers is a reasonable default for a small/medium deployment; override
# with WEB_CONCURRENCY if the host has more cores to spare.
ENV WEB_CONCURRENCY=4
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY} -b 0.0.0.0:8000 --access-logfile - --error-logfile -"]
