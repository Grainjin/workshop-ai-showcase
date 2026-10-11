from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models
from backend.services.milvus_service import (
    delete_review_embedding,
    upsert_review_embedding,
)
from backend.services.ai_service import generate_embedding
from backend.core.clock import utc_now


def build_review_document(review: models.Review):
    if not review.comment or not review.comment.strip():
        return None

    return {
        "review_id": review.id,
        "provider_id": review.provider_profile_id,
        "rating": review.rating,
        "comment": review.comment,
        "embedding": generate_embedding(review.comment),
    }


def mark_review_embedding_synced(review: models.Review, db: Session):
    review.embedding_status = "synced"
    review.embedding_error = None
    review.embedding_synced_at = utc_now()
    db.commit()


def mark_review_embedding_deleted(review: models.Review, db: Session):
    review.embedding_status = "deleted"
    review.embedding_error = None
    review.embedding_synced_at = utc_now()
    db.commit()


def mark_review_embedding_failed(review: models.Review, error: Exception, db: Session):
    review.embedding_status = "failed"
    review.embedding_error = str(error)[:500]
    db.commit()


def mark_reviews_embedding_synced(review_ids: list[int], db: Session):
    if not review_ids:
        return

    now = utc_now()

    db.query(models.Review).filter(models.Review.id.in_(review_ids)).update(
        {
            models.Review.embedding_status: "synced",
            models.Review.embedding_error: None,
            models.Review.embedding_synced_at: now,
        },
        synchronize_session=False,
    )
    db.commit()


def mark_reviews_embedding_deleted(review_ids: list[int], db: Session):
    if not review_ids:
        return

    now = utc_now()

    db.query(models.Review).filter(models.Review.id.in_(review_ids)).update(
        {
            models.Review.embedding_status: "deleted",
            models.Review.embedding_error: None,
            models.Review.embedding_synced_at: now,
        },
        synchronize_session=False,
    )
    db.commit()


def sync_review_embedding(review: models.Review, db: Session):
    if review.is_visible != 1:
        delete_review_embedding(review.id)
        mark_review_embedding_deleted(review, db)
        return

    review_document = build_review_document(review)

    if not review_document:
        delete_review_embedding(review.id)
        mark_review_embedding_deleted(review, db)
        return

    upsert_review_embedding(review_document)
    mark_review_embedding_synced(review, db)


def try_sync_review_embedding(review: models.Review, db: Session):
    review.embedding_status = "pending"
    review.embedding_error = None
    db.commit()

    try:
        sync_review_embedding(review, db)
    except Exception as error:
        mark_review_embedding_failed(review, error, db)


def try_delete_review_embedding(review: models.Review, db: Session):
    try:
        delete_review_embedding(review.id)
        mark_review_embedding_deleted(review, db)
    except Exception as error:
        mark_review_embedding_failed(review, error, db)
