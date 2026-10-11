from tests.conftest import create_booking


def test_customer_can_chat_with_provider(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]

    opened = client.post(f"/customer/chats/{provider_id}", headers=customer)
    assert opened.status_code == 200, opened.text
    room = opened.json()["data"]["chat_room"]
    room_id = room["id"]

    sent = client.post(
        f"/chats/{room_id}/messages",
        json={"message": "Can you come tomorrow morning?"},
        headers=customer,
    )
    assert sent.status_code == 200, sent.text

    reply = client.post(
        f"/chats/{room_id}/messages",
        json={"message": "Yes, after 10am."},
        headers=provider,
    )
    assert reply.status_code == 200, reply.text

    history = client.get(f"/chats/{room_id}/messages", headers=customer)
    assert history.status_code == 200, history.text
    messages = history.json()["data"]["items"]
    texts = [item["message"] for item in messages]
    assert "Can you come tomorrow morning?" in texts
    assert "Yes, after 10am." in texts

    notes = client.get("/notifications", headers=provider)
    assert notes.status_code == 200
    assert notes.json()["data"]["total"] >= 1


def test_booking_creates_chat_room_and_history(client, marketplace):
    customer = marketplace["customer"]["headers"]
    booking = create_booking(
        client, customer, marketplace["provider_profile"]["id"]
    )
    room_id = booking["chat_room_id"]
    history = client.get(f"/chats/{room_id}/messages", headers=customer)
    assert history.status_code == 200
    assert history.json()["data"]["total"] >= 1


def test_websocket_requires_auth_payload(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    room_id = client.post(
        f"/customer/chats/{provider_id}", headers=customer
    ).json()["data"]["chat_room"]["id"]

    with client.websocket_connect(f"/ws/chats/{room_id}") as websocket:
        websocket.send_json({"type": "auth", "token": marketplace["customer"]["access_token"]})
        ready = websocket.receive_json()
        assert ready["type"] == "connection_ready"
        websocket.send_json({"type": "ping"})
        for _ in range(8):
            message = websocket.receive_json()
            if message.get("type") == "pong":
                break
        else:
            raise AssertionError("WebSocket did not return pong after ping")


def test_websocket_rejects_missing_auth(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    room_id = client.post(
        f"/customer/chats/{provider_id}", headers=customer
    ).json()["data"]["chat_room"]["id"]

    with client.websocket_connect(f"/ws/chats/{room_id}") as websocket:
        websocket.send_json({"hello": "nope"})
        error = websocket.receive_json()
        assert error["type"] == "error"
