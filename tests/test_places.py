from backend.services import places_service


def test_places_autocomplete_returns_normalized_suggestions(client, monkeypatch):
    monkeypatch.setattr(places_service, "GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        places_service,
        "_request_google_json",
        lambda *args, **kwargs: {
            "suggestions": [
                {
                    "placePrediction": {
                        "placeId": "ChIJistanbul",
                        "text": {"text": "Sultanahmet, Istanbul, Türkiye"},
                    }
                },
                {"queryPrediction": {"text": {"text": "Istanbul"}}},
            ]
        },
    )

    response = client.get("/places/autocomplete", params={"q": "Sultanahmet"})

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Success",
        "data": {
            "suggestions": [
                {
                    "place_id": "ChIJistanbul",
                    "description": "Sultanahmet, Istanbul, Türkiye",
                }
            ]
        },
    }


def test_places_details_returns_normalized_location(client, monkeypatch):
    monkeypatch.setattr(places_service, "GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        places_service,
        "_request_google_json",
        lambda *args, **kwargs: {
            "id": "ChIJistanbul",
            "formattedAddress": "Sultanahmet, Fatih, Istanbul, Türkiye",
            "location": {"latitude": 41.0082, "longitude": 28.9784},
        },
    )

    response = client.get(
        "/places/details",
        params={"place_id": "ChIJistanbul"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "place_id": "ChIJistanbul",
        "formatted_address": "Sultanahmet, Fatih, Istanbul, Türkiye",
        "latitude": 41.0082,
        "longitude": 28.9784,
    }


def test_places_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(places_service, "GOOGLE_MAPS_API_KEY", "")

    response = client.get("/places/autocomplete", params={"q": "Istanbul"})

    assert response.status_code == 503
    assert response.json()["error"]["detail"] == "Places service is not configured"


def test_places_rejects_blank_query(client, monkeypatch):
    monkeypatch.setattr(places_service, "GOOGLE_MAPS_API_KEY", "test-key")

    response = client.get("/places/autocomplete", params={"q": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["detail"] == "Query cannot be empty"
