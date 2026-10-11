from backend import models
from backend.database import SessionLocal
from backend.schemas import AIChatRequest
from backend.tasks.celery_app import celery_app
from backend.schemas import AsyncTaskStatus
from backend.utils.async_task import update_async_task_record
from backend.utils.ai_chat_handler import handle_ai_chat_request


@celery_app.task(name="ai.chat", bind=True)
def ai_chat_task(self, user_id: int, request_data: dict):
    db = SessionLocal()

    try:
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.started,
        )

        user = db.query(models.User).filter(models.User.id == user_id).first()

        if not user:
            result = {
                "error": "User not found",
            }
            update_async_task_record(
                self.request.id,
                db,
                AsyncTaskStatus.failed,
                result=result,
                error_message=result["error"],
            )
            return result

        if user.role != "customer":
            result = {
                "error": "Only customers can use AI chat",
            }
            update_async_task_record(
                self.request.id,
                db,
                AsyncTaskStatus.failed,
                result=result,
                error_message=result["error"],
            )
            return result

        request = AIChatRequest(**request_data)
        result = handle_ai_chat_request(request, user, db)
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
