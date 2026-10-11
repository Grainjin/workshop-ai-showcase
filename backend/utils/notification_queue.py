from sqlalchemy.orm import Session

from backend import config
from backend.schemas import AsyncTaskType
from backend.tasks.notification_tasks import deliver_notification_task
from backend.utils.async_task import create_async_task_record


def enqueue_notification_delivery(
    user_id: int,
    title: str,
    content: str,
    notification_type: str,
    related_type: str,
    related_id: int,
    db: Session,
):
    # The public demo persists in-app notifications but has no delivery worker.
    if config.DEMO_MODE:
        return None
    payload = {
        "user_id": user_id,
        "title": title,
        "content": content,
        "notification_type": notification_type,
        "related_type": related_type,
        "related_id": related_id,
    }

    try:
        task = deliver_notification_task.apply_async(
            args=[payload],
            retry=False,
        )
    except Exception:
        return None

    create_async_task_record(
        task.id,
        AsyncTaskType.notification_delivery,
        db,
        user_id=user_id,
        commit=False,
    )

    return task.id
