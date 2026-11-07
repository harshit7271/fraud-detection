import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_healthz_endpoint(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.unit
def test_readyz_endpoint(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "models_loaded" in data
    assert "yunet_available" in data
    assert "sface_available" in data
