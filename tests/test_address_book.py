from tests.conftest import register_session


def address(label="Home", is_default=False, **extra):
    payload = {
        "label": label,
        "place_id": extra.get("place_id", "place-home"),
        "formatted_address": extra.get("formatted_address", "1 Demo Street"),
        "latitude": extra.get("latitude", 41.0082),
        "longitude": extra.get("longitude", 28.9784),
        "is_default": is_default,
    }
    if "service_location_id" in extra:
        payload["service_location_id"] = extra["service_location_id"]
    return payload


def test_address_book_is_private_and_first_address_default(client):
    customer = register_session(client, "address-owner@example.com")
    other = register_session(client, "address-other@example.com")

    created = client.post("/customer/addresses", json=address(), headers=customer["headers"])
    assert created.status_code == 200, created.text
    assert created.json()["data"]["is_default"] is True
    address_id = created.json()["data"]["id"]

    listed = client.get("/customer/addresses", headers=customer["headers"])
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]] == [address_id]
    assert client.get("/customer/addresses", headers=other["headers"]).json()["data"] == []


def test_address_book_requires_customer_and_hides_other_records(client):
    provider = register_session(client, "address-provider@example.com", role="provider")
    assert client.get("/customer/addresses").status_code == 401
    assert client.get("/customer/addresses", headers=provider["headers"]).status_code == 403

    customer = register_session(client, "address-private@example.com")
    created = client.post("/customer/addresses", json=address(), headers=customer["headers"])
    address_id = created.json()["data"]["id"]
    assert (
        client.delete(f"/customer/addresses/{address_id}", headers=provider["headers"]).status_code
        == 403
    )


def test_address_book_switches_default_and_deletes_with_promotion(client):
    customer = register_session(client, "address-default@example.com")
    first = client.post("/customer/addresses", json=address(), headers=customer["headers"])
    second = client.post(
        "/customer/addresses",
        json=address("Work", place_id="place-work"),
        headers=customer["headers"],
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    assert second.json()["data"]["is_default"] is False

    switched = client.patch(
        f"/customer/addresses/{second_id}",
        json={"is_default": True},
        headers=customer["headers"],
    )
    assert switched.status_code == 200
    listed = client.get("/customer/addresses", headers=customer["headers"]).json()["data"]
    assert {item["id"] for item in listed if item["is_default"]} == {second_id}
    assert (
        client.delete(f"/customer/addresses/{second_id}", headers=customer["headers"]).status_code
        == 200
    )
    remaining = client.get("/customer/addresses", headers=customer["headers"]).json()["data"]
    assert remaining[0]["id"] == first_id
    assert remaining[0]["is_default"] is True


def test_address_book_rejects_sixth_and_invalid_place_data(client):
    customer = register_session(client, "address-limit@example.com")
    for index in range(5):
        response = client.post(
            "/customer/addresses",
            json=address(f"Place {index}", place_id=f"place-{index}"),
            headers=customer["headers"],
        )
        assert response.status_code == 200, response.text
    sixth = client.post(
        "/customer/addresses",
        json=address("Sixth", place_id="place-sixth"),
        headers=customer["headers"],
    )
    assert sixth.status_code == 409

    missing_place = client.post(
        "/customer/addresses",
        json=address("Missing", place_id=""),
        headers=customer["headers"],
    )
    assert missing_place.status_code == 422


def test_address_book_rejects_hand_typed_coordinates_and_bad_service_location(client):
    customer = register_session(client, "address-validation@example.com")
    hand_typed = client.post(
        "/customer/addresses",
        json=address("Typed", place_id="typed-coordinates"),
        headers=customer["headers"],
    )
    assert hand_typed.status_code == 200

    missing_coordinates = address("No Coordinates", place_id="place-no-coordinates")
    del missing_coordinates["latitude"]
    assert (
        client.post(
            "/customer/addresses", json=missing_coordinates, headers=customer["headers"]
        ).status_code
        == 422
    )
    missing_longitude = address("No Longitude", place_id="place-no-longitude")
    del missing_longitude["longitude"]
    assert (
        client.post(
            "/customer/addresses", json=missing_longitude, headers=customer["headers"]
        ).status_code
        == 422
    )

    bad_location = client.post(
        "/customer/addresses",
        json=address("Bad Region", place_id="place-region", service_location_id=999999),
        headers=customer["headers"],
    )
    assert bad_location.status_code == 422


def test_address_book_patch_rejects_null_or_blank_label(client):
    customer = register_session(client, "address-label-validation@example.com")
    created = client.post("/customer/addresses", json=address(), headers=customer["headers"])
    address_id = created.json()["data"]["id"]
    for label in (None, "   "):
        response = client.patch(
            f"/customer/addresses/{address_id}",
            json={"label": label},
            headers=customer["headers"],
        )
        assert response.status_code == 422, response.text
