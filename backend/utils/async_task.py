import json
from datetime import datetime, timezone

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import AsyncTaskStatus, AsyncTaskType
from backend.core.clock import utc_now


def get_now():
    return utc_now()


def normalize_task_status(status: str):
    status_map = {
        "PENDING": AsyncTaskStatus.pending.value,
        "STARTED": AsyncTaskStatus.started.value,
        "RETRY": AsyncTaskStatus.retry.value,
        "SUCCESS": AsyncTaskStatus.success.value,
        "FAILURE": AsyncTaskStatus.failed.value,
        "REVOKED": AsyncTaskStatus.revoked.value,
    }

    return status_map.get(status, status.lower())


def dump_task_result(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def load_task_result(value: str | None):
    if not value:
        return None

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def create_async_task_record(
    task_id: str,
    task_type: AsyncTaskType,
    db: Session,
    user_id: int | None = None,
    commit: bool = True,
):
    now = get_now()
    async_task = models.AsyncTask(
        task_id=task_id,
        user_id=user_id,
        task_type=task_type.value,
        status=AsyncTaskStatus.pending.value,
        result_json=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        finished_at=None,
    )

    db.add(async_task)

    if commit:
        db.commit()
        db.refresh(async_task)

    return async_task


def update_async_task_record(
    task_id: str,
    db: Session,
    status: AsyncTaskStatus,
    result=None,
    error_message: str | None = None,
):
    async_task = (
        db.query(models.AsyncTask).filter(models.AsyncTask.task_id == task_id).first()
    )

    if not async_task:
        return None

    async_task.status = status.value
    async_task.updated_at = get_now()

    if status in (
        AsyncTaskStatus.success,
        AsyncTaskStatus.failed,
        AsyncTaskStatus.revoked,
    ):
        async_task.finished_at = async_task.updated_at

    if result is not None:
        async_task.result_json = dump_task_result(result)

    if error_message is not None:
        async_task.error_message = error_message[:500]

    db.commit()
    db.refresh(async_task)

    return async_task


def sync_async_task_record_from_celery(
    async_task: models.AsyncTask,
    celery_result: AsyncResult,
    db: Session,
):
    terminal_statuses = {
        AsyncTaskStatus.success.value,
        AsyncTaskStatus.failed.value,
        AsyncTaskStatus.revoked.value,
    }

    if async_task.status in terminal_statuses and celery_result.status == "PENDING":
        return async_task

    status = normalize_task_status(celery_result.status)
    async_task.status = status
    async_task.updated_at = get_now()

    if celery_result.ready():
        async_task.finished_at = async_task.updated_at

        if celery_result.successful():
            result = celery_result.result
            task_error = None

            if isinstance(result, dict):
                task_error = result.get("error")

                if result.get("status") == "not_found":
                    task_error = task_error or "Task target not found"

            if task_error:
                async_task.status = AsyncTaskStatus.failed.value
                async_task.error_message = str(task_error)[:500]
            else:
                async_task.result_json = dump_task_result(result)
                async_task.error_message = None
        else:
            async_task.error_message = str(celery_result.result)[:500]

    db.commit()
    db.refresh(async_task)

    return async_task


def format_async_task_response(async_task: models.AsyncTask):
    return {
        "id": async_task.id,
        "task_id": async_task.task_id,
        "user_id": async_task.user_id,
        "task_type": async_task.task_type,
        "status": async_task.status,
        "result": load_task_result(async_task.result_json),
        "error_message": async_task.error_message,
        "created_at": async_task.created_at,
        "updated_at": async_task.updated_at,
        "finished_at": async_task.finished_at,
    }
