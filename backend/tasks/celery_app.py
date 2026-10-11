"""Celery background task config.

Redis broker/backend for long-running AI chat, notifications, review embeddings.
"""

from celery import Celery

from backend.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "workshop_ai",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.ai_tasks",
        "backend.tasks.notification_tasks",
        "backend.tasks.review_tasks",
        "backend.tasks.marketplace_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_publish_retry=False,
    broker_connection_timeout=1,
    broker_transport_options={
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
        "retry_on_timeout": False,
    },
    result_backend_transport_options={
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
        "retry_on_timeout": False,
    },
)

app = celery_app
