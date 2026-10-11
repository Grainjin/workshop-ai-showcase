from backend.database import SessionLocal
from backend.schemas import AsyncTaskStatus
from backend.tasks.celery_app import celery_app
from backend.utils.async_task import update_async_task_record


@celery_app.task(name="notifications.deliver", bind=True)
def deliver_notification_task(self, notification_payload: dict):
    db = SessionLocal()

    try:
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.started,
        )
        result = {
            "delivered": True,
            "channel": "in_app_placeholder",
            "notification": notification_payload,
        }
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.success,
            result=result,
        )
        return result
    except Exception as error:
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.failed,
            error_message=str(error),
        )
        raise
    finally:
        db.close()
