from backend.main import app


def test_booking_attachments_are_advertised_as_binary_files():
    schema = app.openapi()["components"]["schemas"]["Body_create_booking_bookings_post"]
    attachments = schema["properties"]["attachments"]

    array_schema = next(item for item in attachments["anyOf"] if item.get("type") == "array")
    assert array_schema["items"] == {"type": "string", "format": "binary"}


def test_provider_quote_endpoints_advertise_json_and_multipart_files():
    paths = app.openapi()["paths"]
    for path in (
        "/provider/bookings/{booking_id}/quote",
        "/provider/bookings/{booking_id}/final-quote",
    ):
        content = paths[path]["put"]["requestBody"]["content"]
        assert "application/json" in content
        files = content["multipart/form-data"]["schema"]["properties"]["quote_files"]
        assert files["items"] == {"type": "string", "format": "binary"}
