#!/bin/sh
set -eu

role="${1:-api}"
public="${WORKSHOP_PUBLIC_DEPLOYMENT:-false}"

case "$public" in
  true)
    python docker/api/validate_public_config.py "$role"
    ;;
  false) ;;
  *)
    echo "WORKSHOP_PUBLIC_DEPLOYMENT must be true or false" >&2
    exit 1
    ;;
esac

case "$role" in
  api)
    if [ "$public" = "false" ]; then
      python scripts/generate_jwt_keys.py
      alembic upgrade head
      python -m backend.seed_locations
      if [ "${WORKSHOP_SEED:-0}" = "1" ]; then
        python -m backend.seed_demo_data
      fi
    fi
    exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  release)
    exec alembic upgrade head
    ;;
  reset-demo)
    shift
    exec python -m backend.reset_demo_data "$@"
    ;;
  worker)
    if [ "$public" = "false" ]; then
      python scripts/generate_jwt_keys.py
    fi
    exec celery -A backend.tasks.celery_app worker --loglevel=info
    ;;
  *)
    exec "$@"
    ;;
esac
