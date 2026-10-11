"""Redis service wrapper.

Ephemeral state: online presence, notification unread cache, AI recommendation context.
Data may expire; the database remains the source of truth.
"""

import json

import redis
from redis.exceptions import RedisError

from backend.config import REDIS_HOST, REDIS_PORT, REDIS_DB

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
    retry_on_timeout=False,
)


def check_redis_connection():
    return redis_client.ping()


def get_user_online_key(user_id: int):
    return f"online:user:{user_id}"


def set_user_online(user_id: int, expire_seconds: int = 3600):
    try:
        redis_client.set(
            get_user_online_key(user_id),
            "1",
            ex=expire_seconds,
        )
        return True
    except RedisError:
        return False


def set_user_offline(user_id: int):
    try:
        redis_client.delete(get_user_online_key(user_id))
        return True
    except RedisError:
        return False


def is_user_online(user_id: int):
    try:
        return redis_client.exists(get_user_online_key(user_id)) == 1
    except RedisError:
        return False


def get_notification_unread_key(user_id: int):
    return f"notification:unread:{user_id}"


def get_cached_notification_unread_count(user_id: int):
    try:
        value = redis_client.get(get_notification_unread_key(user_id))
    except RedisError:
        return None

    if value is None:
        return None

    try:
        return max(int(value), 0)
    except ValueError:
        return None


def set_notification_unread_count(user_id: int, count: int):
    try:
        redis_client.set(
            get_notification_unread_key(user_id),
            max(count, 0),
        )
        return True
    except RedisError:
        return False


def increment_notification_unread_count(user_id: int, amount: int = 1):
    key = get_notification_unread_key(user_id)

    try:
        if redis_client.exists(key) != 1:
            return False

        redis_client.incrby(key, amount)
        return True
    except RedisError:
        return False


def decrement_notification_unread_count(user_id: int, amount: int = 1):
    key = get_notification_unread_key(user_id)

    try:
        if redis_client.exists(key) != 1:
            return False

        unread_count = redis_client.decrby(key, amount)

        if unread_count < 0:
            redis_client.set(key, 0)

        return True
    except RedisError:
        return False


def get_chat_unread_key(user_id: int, chat_room_id: int):
    return f"chat:unread:{user_id}:{chat_room_id}"


def get_cached_chat_room_unread_count(user_id: int, chat_room_id: int):
    try:
        value = redis_client.get(get_chat_unread_key(user_id, chat_room_id))
    except RedisError:
        return None

    if value is None:
        return None

    try:
        return max(int(value), 0)
    except ValueError:
        return None


def set_chat_room_unread_count(user_id: int, chat_room_id: int, count: int):
    try:
        redis_client.set(
            get_chat_unread_key(user_id, chat_room_id),
            max(count, 0),
        )
        return True
    except RedisError:
        return False


def increment_chat_room_unread_count(
    user_id: int,
    chat_room_id: int,
    amount: int = 1,
):
    key = get_chat_unread_key(user_id, chat_room_id)

    try:
        if redis_client.exists(key) != 1:
            return None

        unread_count = redis_client.incrby(key, amount)
        if unread_count < 0:
            redis_client.set(key, 0)
            return 0

        return unread_count
    except RedisError:
        return None


def clear_chat_room_unread_count(user_id: int, chat_room_id: int):
    return set_chat_room_unread_count(user_id, chat_room_id, 0)


def get_last_recommended_providers_key(user_id: int):
    return f"ai:last_recommended_providers:{user_id}"


def get_last_provider_recommendation_context_key(user_id: int):
    return f"ai:last_provider_recommendation_context:{user_id}"


def save_last_recommended_providers(
    user_id: int,
    provider_ids: list[int],
    expire_seconds: int = 1800,
):
    key = get_last_recommended_providers_key(user_id)
    try:
        redis_client.set(
            key,
            json.dumps(provider_ids),
            ex=expire_seconds,
        )
    except RedisError:
        pass


def get_last_recommended_providers(user_id: int):
    key = get_last_recommended_providers_key(user_id)
    try:
        value = redis_client.get(key)
    except RedisError:
        return []

    if not value:
        return []

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


def save_last_provider_recommendation_context(
    user_id: int,
    recommendation_context: list[dict],
    expire_seconds: int = 1800,
):
    key = get_last_provider_recommendation_context_key(user_id)
    try:
        redis_client.set(
            key,
            json.dumps(recommendation_context, ensure_ascii=False),
            ex=expire_seconds,
        )
    except RedisError:
        pass


def get_last_provider_recommendation_context(user_id: int):
    key = get_last_provider_recommendation_context_key(user_id)
    try:
        value = redis_client.get(key)
    except RedisError:
        return []

    if not value:
        return []

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


def filter_recent_provider_ids(user_id: int, provider_ids: list[int]):
    recent_provider_ids = get_last_recommended_providers(user_id)

    if not provider_ids:
        return recent_provider_ids

    return [
        provider_id
        for provider_id in provider_ids
        if provider_id in recent_provider_ids
    ]
