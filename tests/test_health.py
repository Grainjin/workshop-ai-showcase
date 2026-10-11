def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["success"] is True
