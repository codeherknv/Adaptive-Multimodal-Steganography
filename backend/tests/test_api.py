"""Automated tests for health, status, and cryptographic API endpoints."""

import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.core.crypto_utils import generate_key, bytes_to_base64, bytes_to_hex


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


def test_system_status_endpoint_phase_2(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] == 2
    assert "modules" in data
    
    # Phase 1 & 2 modules are implemented
    assert data["modules"]["infrastructure"]["status"] == "implemented"
    assert data["modules"]["cryptography"]["status"] == "implemented"
    assert len(data["modules"]["cryptography"]["capabilities"]) > 0
    assert data["modules"]["payload_codec"]["status"] == "implemented"
    assert len(data["modules"]["payload_codec"]["capabilities"]) > 0

    # Future phases remain truthfully pending
    assert data["modules"]["image_stego"]["status"] == "pending"
    assert data["modules"]["audio_stego"]["status"] == "pending"
    assert data["modules"]["video_stego"]["status"] == "pending"
    assert data["modules"]["steganalysis"]["status"] == "pending"


class TestCryptoAPIEndpoints:
    def test_encrypt_and_decrypt_auto_key_roundtrip(self, client):
        msg = "Secret academic payload across carriers 🚀"
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": msg, "encoding": "base64"}
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert "key" in enc_data
        assert "envelope" in enc_data
        assert enc_data["envelope_version"] == 1
        assert enc_data["plaintext_bytes_length"] == len(msg.encode("utf-8"))
        assert "Educational Key Workflow" in enc_data["warning"]

        # Now decrypt using the returned key
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "key": enc_data["key"],
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        dec_data = dec_res.json()
        assert dec_data["plaintext"] == msg
        assert dec_data["authenticated"] is True
        assert dec_data["envelope_version"] == 1

    def test_encrypt_and_decrypt_user_key(self, client):
        raw_key = generate_key()
        b64_key = bytes_to_base64(raw_key)
        msg = "Target carrier allocation: Image=33%, Audio=33%, Video=34%"

        enc_res = client.post(
            "/api/crypto/encrypt",
            json={
                "plaintext": msg,
                "key": b64_key,
                "encoding": "base64"
            }
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert enc_data["key"] == b64_key

        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "key": b64_key,
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == msg

    def test_encrypt_and_decrypt_hex_encoding(self, client):
        msg = "Hex-encoded payload round-trip check"
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": msg, "encoding": "hex"}
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert enc_data["key_encoding"] == "hex"

        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "key": enc_data["key"],
                "encoding": "hex"
            }
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == msg

    def test_encrypt_and_decrypt_password_derivation(self, client):
        password = "MasterPassword2026!#"
        msg = "Key derived via PBKDF2-HMAC-SHA256"

        enc_res = client.post(
            "/api/crypto/encrypt",
            json={
                "plaintext": msg,
                "password": password,
                "encoding": "base64"
            }
        )
        assert enc_res.status_code == 200
        enc_data = enc_res.json()
        assert enc_data["salt"] is not None

        # Decrypt using password and returned salt
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={
                "envelope": enc_data["envelope"],
                "password": password,
                "salt": enc_data["salt"],
                "encoding": "base64"
            }
        )
        assert dec_res.status_code == 200
        assert dec_res.json()["plaintext"] == msg

    def test_decrypt_with_wrong_key_rejected(self, client):
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": "Confidential message"}
        )
        envelope = enc_res.json()["envelope"]

        wrong_key = bytes_to_base64(generate_key())
        dec_res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": envelope, "key": wrong_key}
        )
        assert dec_res.status_code == 400
        assert "Authentication tag verification failed" in dec_res.json()["detail"]

    def test_decrypt_tampered_envelope_rejected(self, client):
        enc_res = client.post(
            "/api/crypto/encrypt",
            json={"plaintext": "Data integrity test"}
        )
        enc_data = enc_res.json()
        key = enc_data["key"]

        # Tamper base64 envelope by flipping characters
        tampered_envelope = enc_data["envelope"][:-4] + "AAAA"

        dec_res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": tampered_envelope, "key": key}
        )
        assert dec_res.status_code == 400

    def test_validation_rejects_key_and_password_simultaneously(self, client):
        res = client.post(
            "/api/crypto/encrypt",
            json={
                "plaintext": "Test",
                "key": bytes_to_base64(generate_key()),
                "password": "Password123"
            }
        )
        assert res.status_code == 422  # Pydantic validation error

    def test_validation_rejects_empty_decrypt_credentials(self, client):
        res = client.post(
            "/api/crypto/decrypt",
            json={"envelope": "dGVzdA=="}
        )
        assert res.status_code == 422  # Neither key nor password provided
