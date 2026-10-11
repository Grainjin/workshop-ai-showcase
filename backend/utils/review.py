from sqlalchemy.orm import Session

from backend import models
from backend.utils.formatters import format_review_response, format_user_response


def format_review_detail_response(review: models.Review, db: Session):
    result = format_review_response(review)

    customer = (
        db.query(models.User).filter(models.User.id == review.customer_id).first()
    )

    result["customer"] = format_user_response(customer) if customer else None

    return result


def get_provider_rating_summary(provider_id: int, db: Session):
    reviews = (
        db.query(models.Review)
        .filter(
            models.Review.provider_profile_id == provider_id,
            models.Review.is_visible == 1,
        )
        .all()
    )

    review_count = len(reviews)

    if review_count == 0:
        average_rating = None
    else:
        total_rating = 0

        for review in reviews:
            total_rating += review.rating

        average_rating = round(total_rating / review_count, 2)

    return {
        "average_rating": average_rating,
        "review_count": review_count,
    }
