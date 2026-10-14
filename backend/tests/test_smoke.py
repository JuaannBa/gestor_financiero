def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_public(client):
    response = client.get("/api/v1/schema/")
    assert response.status_code == 200


def test_swagger_ui_renders(client):
    response = client.get("/api/v1/docs/")
    assert response.status_code == 200
