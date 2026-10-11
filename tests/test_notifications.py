from backend.services.redis_service import set_notification_unread_count
from backend.utils.notification import get_notification_unread_count


def test_unread_count_follows_database_not_stale_cache(
    client, marketplace, db_session
):
    user_id = marketplace["customer"]["user"]["id"]
    set_notification_unread_count(user_id, 24)

    assert get_notification_unread_count(user_id, db_session) == 0

    summary = client.get(
        "/notifications/summary",
        headers=marketplace["customer"]["headers"],
    )
    listing = client.get(
        "/notifications",
        headers=marketplace["customer"]["headers"],
    )
    assert summary.status_code == 200, summary.text
    assert listing.status_code == 200, listing.text
    assert summary.json()["data"]["unread_count"] == 0
    assert summary.json()["data"]["latest_notification"] is None
    assert listing.json()["data"]["total"] == 0
    assert listing.json()["data"]["items"] == []


def test_chat_notification_keeps_summary_and_list_in_sync(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]

    room_id = client.post(
        f"/customer/chats/{provider_id}",
        headers=customer,
    ).json()["data"]["chat_room"]["id"]
    sent = client.post(
        f"/chats/{room_id}/messages",
        json={"message": "Can you come tomorrow morning?"},
        headers=customer,
    )
    assert sent.status_code == 200, sent.text

    summary = client.get("/notifications/summary", headers=provider)
    listing = client.get("/notifications", headers=provider)
    assert summary.status_code == 200, summary.text
    assert listing.status_code == 200, listing.text

    items = listing.json()["data"]["items"]
    unread = sum(1 for item in items if item["read_at"] is None)
    assert listing.json()["data"]["total"] >= 1
    assert summary.json()["data"]["unread_count"] == unread
    assert summary.json()["data"]["latest_notification"] is not None
