def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness(client):
    response = client.get("/api/v1/health/liveness")
    assert response.status_code == 200


def test_readiness(client):
    response = client.get("/api/v1/health/readiness")
    assert response.status_code == 200
