import math

from backend.utils.response import success_response

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def normalize_pagination(page: int, page_size: int):
    page = max(page, 1)
    page_size = max(page_size, 1)
    page_size = min(page_size, MAX_PAGE_SIZE)

    return page, page_size


def build_paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
):
    page, page_size = normalize_pagination(page, page_size)
    total_pages = math.ceil(total / page_size) if total else 0

    return success_response(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1 and total_pages > 0,
        }
    )


def paginate_query(query, page: int, page_size: int):
    page, page_size = normalize_pagination(page, page_size)
    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return records, total, page, page_size


def paginate_list(items: list, page: int, page_size: int):
    page, page_size = normalize_pagination(page, page_size)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return items[start:end], total, page, page_size
