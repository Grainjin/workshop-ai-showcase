from sqlalchemy.orm import Session

from backend import config, models
from backend.schemas import AsyncTaskType
from backend.tasks.review_tasks import (
    delete_review_embedding_task,
    sync_all_review_embeddings_task,
    sync_review_embedding_task,
)
from backend.utils.async_task import create_async_task_record


def mark_review_embedding_pending(review: models.Review, db: Session):
    review.embedding_status = "pending"
    review.embedding_error = None
    db.commit()
    db.refresh(review)


def mark_review_embedding_enqueue_failed(
    review: models.Review,
    error: Exception,
    db: Session,
):
    review.embedding_status = "failed"
    review.embedding_error = f"Failed to enqueue Celery task: {str(error)[:450]}"
    db.commit()
    db.refresh(review)


def enqueue_review_embedding_sync(
    review: models.Review,
    db: Session,
    user_id: int | None = None,
):
    if config.DEMO_MODE:
        return None
    mark_review_embedding_pending(review, db)

    try:
        task = sync_review_embedding_task.delay(review.id)
    except Exception as error:
        mark_review_embedding_enqueue_failed(review, error, db)
        return None

    create_async_task_record(
        task.id,
        AsyncTaskType.review_embedding_sync,
        db,
        user_id=user_id,
    )

    return task.id


def enqueue_review_embedding_delete(
    review: models.Review,
    db: Session,
    user_id: int | None = None,
):
    if config.DEMO_MODE:
        return None
    mark_review_embedding_pending(review, db)

    try:
        task = delete_review_embedding_task.delay(review.id)
    except Exception as error:
        mark_review_embedding_enqueue_failed(review, error, db)
        return None

    create_async_task_record(
        task.id,
        AsyncTaskType.review_embedding_delete,
        db,
        user_id=user_id,
    )

    return task.id


def enqueue_all_review_embeddings_sync(
    db: Session,
    user_id: int | None = None,
):
    db.query(models.Review).update(
        {
            models.Review.embedding_status: "pending",
            models.Review.embedding_error: None,
        },
        synchronize_session=False,
    )
    db.commit()

    try:
        task = sync_all_review_embeddings_task.delay()
    except Exception as error:
        db.query(models.Review).filter(
            models.Review.embedding_status == "pending"
        ).update(
            {
                models.Review.embedding_status: "failed",
                models.Review.embedding_error: (
                    f"Failed to enqueue Celery task: {str(error)[:450]}"
                ),
            },
            synchronize_session=False,
        )
        db.commit()
        return None

    create_async_task_record(
        task.id,
        AsyncTaskType.review_embedding_full_sync,
        db,
        user_id=user_id,
    )

    return task.id
