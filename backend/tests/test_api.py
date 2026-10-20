"""Automated tests for health and status endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture
def client():
    return TestClient(app)

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert "health_url" in data

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == settings.VERSION
    assert "timestamp" in data
    # Ensure no internal filesystem paths or secrets are leaked
    assert "C:" not in str(data)
    assert "secret" not in str(data).lower()

def test_system_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] == 1
    assert "modules" in data
    assert "infrastructure" in data["modules"]
    assert data["modules"]["infrastructure"]["status"] == "implemented"
    # Ensure future phases are truthfully reported as pending
    assert data["modules"]["cryptography"]["status"] == "pending"
    assert data["modules"]["image_stego"]["status"] == "pending"
    assert data["modules"]["steganalysis"]["status"] == "pending"
