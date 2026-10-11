"""Milvus vector store wrapper.

Stores review embeddings for RAG when AI summarizes provider reviews.
Business data stays in PostgreSQL; Milvus is a semantic search layer.
"""

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from backend.config import (
    EMBEDDING_DIMENSION,
    MILVUS_HOST,
    MILVUS_PORT,
    MILVUS_REVIEW_COLLECTION,
)

MILVUS_ALIAS = "default"


def connect_milvus():
    connections.connect(
        alias=MILVUS_ALIAS,
        host=MILVUS_HOST,
        port=MILVUS_PORT,
    )


def check_milvus_connection():
    connect_milvus()
    return utility.get_server_version(using=MILVUS_ALIAS)


def create_review_collection():
    connect_milvus()

    if utility.has_collection(MILVUS_REVIEW_COLLECTION, using=MILVUS_ALIAS):
        return {
            "collection": MILVUS_REVIEW_COLLECTION,
            "created": False,
            "message": "Review collection already exists",
        }

    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
            auto_id=True,
        ),
        FieldSchema(
            name="review_id",
            dtype=DataType.INT64,
        ),
        FieldSchema(
            name="provider_id",
            dtype=DataType.INT64,
        ),
        FieldSchema(
            name="rating",
            dtype=DataType.INT64,
        ),
        FieldSchema(
            name="comment",
            dtype=DataType.VARCHAR,
            max_length=500,
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIMENSION,
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description="Provider review embeddings for Workshop AI RAG",
    )

    collection = Collection(
        name=MILVUS_REVIEW_COLLECTION,
        schema=schema,
        using=MILVUS_ALIAS,
    )

    index_params = {
        "metric_type": "COSINE",
        "index_type": "AUTOINDEX",
        "params": {},
    }

    collection.create_index(
        field_name="embedding",
        index_params=index_params,
    )

    collection.load()

    return {
        "collection": MILVUS_REVIEW_COLLECTION,
        "created": True,
        "message": "Review collection created successfully",
    }


def clear_review_collection():
    connect_milvus()
    create_review_collection()

    collection = Collection(
        name=MILVUS_REVIEW_COLLECTION,
        using=MILVUS_ALIAS,
    )

    collection.delete(expr="review_id >= 0")
    collection.flush()

    return {
        "collection": MILVUS_REVIEW_COLLECTION,
        "message": "Review collection cleared",
    }


def delete_review_embedding(review_id: int):
    connect_milvus()
    create_review_collection()

    collection = Collection(
        name=MILVUS_REVIEW_COLLECTION,
        using=MILVUS_ALIAS,
    )

    collection.delete(expr=f"review_id == {review_id}")
    collection.flush()

    return {
        "review_id": review_id,
        "message": "Review embedding deleted",
    }


def insert_review_embeddings(
    review_documents: list[dict],
    refresh: bool = False,
):
    connect_milvus()
    create_review_collection()

    if refresh:
        clear_review_collection()

    if not review_documents:
        return {
            "inserted": 0,
            "message": "No review documents to insert",
        }

    collection = Collection(
        name=MILVUS_REVIEW_COLLECTION,
        using=MILVUS_ALIAS,
    )

    data = [
        [doc["review_id"] for doc in review_documents],
        [doc["provider_id"] for doc in review_documents],
        [doc["rating"] for doc in review_documents],
        [doc["comment"] for doc in review_documents],
        [doc["embedding"] for doc in review_documents],
    ]

    collection.insert(data)
    collection.flush()

    return {
        "inserted": len(review_documents),
        "refreshed": refresh,
        "message": "Review embeddings inserted successfully",
    }


def upsert_review_embedding(review_document: dict):
    delete_review_embedding(review_document["review_id"])
    result = insert_review_embeddings([review_document])

    return {
        "review_id": review_document["review_id"],
        "message": "Review embedding upserted",
        **result,
    }


def format_review_search_hits(search_result):
    return [
        {
            "review_id": hit.entity.get("review_id"),
            "provider_id": hit.entity.get("provider_id"),
            "rating": hit.entity.get("rating"),
            "comment": hit.entity.get("comment"),
            "score": hit.score,
        }
        for hit in search_result[0]
    ]


def search_review_embeddings(
    query_embedding: list[float],
    provider_ids: list[int],
    limit_per_type: int = 5,
):
    connect_milvus()

    collection = Collection(
        name=MILVUS_REVIEW_COLLECTION,
        using=MILVUS_ALIAS,
    )
    collection.load()

    review_context = []

    for provider_id in provider_ids:
        positive_results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={
                "metric_type": "COSINE",
                "params": {},
            },
            limit=limit_per_type,
            expr=f"provider_id == {provider_id} and rating >= 4",
            output_fields=["review_id", "provider_id", "rating", "comment"],
        )

        negative_results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={
                "metric_type": "COSINE",
                "params": {},
            },
            limit=limit_per_type,
            expr=f"provider_id == {provider_id} and rating <= 2",
            output_fields=["review_id", "provider_id", "rating", "comment"],
        )

        review_context.append(
            {
                "provider_id": provider_id,
                "positive_reviews": format_review_search_hits(positive_results),
                "negative_reviews": format_review_search_hits(negative_results),
            }
        )

    return review_context
