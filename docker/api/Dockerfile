FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY scripts /app/scripts
COPY backend /app/backend
COPY docker/api/entrypoint.sh /app/docker/api/entrypoint.sh
COPY docker/api/healthcheck.py /app/docker/api/healthcheck.py
COPY docker/api/validate_public_config.py /app/docker/api/validate_public_config.py

RUN sed -i 's/\r$//' /app/docker/api/entrypoint.sh \
    && chmod +x /app/docker/api/entrypoint.sh \
    && mkdir -p /app/backend/certs /app/backend/uploads

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=12 \
    CMD ["python", "/app/docker/api/healthcheck.py"]

ENTRYPOINT ["/app/docker/api/entrypoint.sh"]
CMD ["api"]
