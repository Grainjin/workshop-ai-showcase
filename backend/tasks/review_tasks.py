from backend import models
from backend.database import SessionLocal
from backend.schemas import AsyncTaskStatus
from backend.services.ai_service import generate_embedding
from backend.services.milvus_service import insert_review_embeddings
from backend.tasks.celery_app import celery_app
from backend.utils.ai import get_review_documents
from backend.utils.async_task import update_async_task_record
from backend.utils.review_embedding import (
    mark_reviews_embedding_deleted,
    mark_reviews_embedding_synced,
    try_delete_review_embedding,
    try_sync_review_embedding,
)


@celery_app.task(name="reviews.sync_embedding", bind=True)
def sync_review_embedding_task(self, review_id: int):
    db = SessionLocal()

    try:
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.started,
        )

        review = db.query(models.Review).filter(models.Review.id == review_id).first()

        if not review:
            result = {
                "review_id": review_id,
                "status": "not_found",
            }
            update_async_task_record(
                self.request.id,
                db,
                AsyncTaskStatus.failed,
                result=result,
                error_message="Review not found",
            )
            return result

        try_sync_review_embedding(review, db)
        db.refresh(review)

        result = {
            "review_id": review.id,
            "status": review.embedding_status,
            "error": review.embedding_error,
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


@celery_app.task(name="reviews.delete_embedding", bind=True)
def delete_review_embedding_task(self, review_id: int):
    db = SessionLocal()

    try:
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.started,
        )

        review = db.query(models.Review).filter(models.Review.id == review_id).first()

        if not review:
            result = {
                "review_id": review_id,
                "status": "not_found",
            }
            update_async_task_record(
                self.request.id,
                db,
                AsyncTaskStatus.failed,
                result=result,
                error_message="Review not found",
            )
            return result

        try_delete_review_embedding(review, db)
        db.refresh(review)

        result = {
            "review_id": review.id,
            "status": review.embedding_status,
            "error": review.embedding_error,
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


@celery_app.task(name="reviews.sync_all_embeddings", bind=True)
def sync_all_review_embeddings_task(self):
    db = SessionLocal()

    try:
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.started,
        )

        review_documents = get_review_documents(db)

        for document in review_documents:
            document["embedding"] = generate_embedding(document["comment"])

        result = insert_review_embeddings(
            review_documents,
            refresh=True,
        )
        synced_review_ids = [document["review_id"] for document in review_documents]
        mark_reviews_embedding_synced(
            synced_review_ids,
            db,
        )
        all_review_ids = [review.id for review in db.query(models.Review.id).all()]
        deleted_review_ids = [
            review_id
            for review_id in all_review_ids
            if review_id not in synced_review_ids
        ]
        mark_reviews_embedding_deleted(
            deleted_review_ids,
            db,
        )

        result_payload = {
            "review_count": len(review_documents),
            "synced_review_count": len(synced_review_ids),
            "deleted_embedding_count": len(deleted_review_ids),
            **result,
        }
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.success,
            result=result_payload,
        )
        return result_payload
    except Exception as error:
        db.query(models.Review).filter(
            models.Review.embedding_status == "pending"
        ).update(
            {
                models.Review.embedding_status: "failed",
                models.Review.embedding_error: str(error)[:500],
            },
            synchronize_session=False,
        )
        db.commit()
        update_async_task_record(
            self.request.id,
            db,
            AsyncTaskStatus.failed,
            error_message=str(error),
        )
        raise
    finally:
        db.close()
