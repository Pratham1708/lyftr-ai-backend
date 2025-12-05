"""
Tests for webhook endpoint including signature verification and idempotency.
"""
import hashlib
import hmac
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import Config


@pytest.fixture
def client():
    """Create test client."""
    # Ensure WEBHOOK_SECRET is set for tests
    Config.WEBHOOK_SECRET = "testsecret"
    return TestClient(app)


def generate_signature(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    signature = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return signature


def test_webhook_valid_signature(client):
    """Test webhook with valid signature."""
    payload = {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello"
    }
    
    signature = generate_signature(payload, "testsecret")
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_webhook_invalid_signature(client):
    """Test webhook with invalid signature."""
    payload = {
        "message_id": "m2",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Test"
    }
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": "invalid_signature"}
    )
    
    assert response.status_code == 401
    assert "invalid signature" in response.json()["detail"]


def test_webhook_missing_signature(client):
    """Test webhook without signature header."""
    payload = {
        "message_id": "m3",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Test"
    }
    
    response = client.post("/webhook", json=payload)
    
    assert response.status_code == 422  # Missing required header


def test_webhook_invalid_e164_format(client):
    """Test webhook with invalid E.164 phone number."""
    payload = {
        "message_id": "m4",
        "from": "919876543210",  # Missing +
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Test"
    }
    
    signature = generate_signature(payload, "testsecret")
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 422  # Validation error


def test_webhook_idempotency(client):
    """Test that duplicate messages are handled idempotently."""
    payload = {
        "message_id": "m_idempotent",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Idempotency test"
    }
    
    signature = generate_signature(payload, "testsecret")
    headers = {"X-Signature": signature}
    
    # First request
    response1 = client.post("/webhook", json=payload, headers=headers)
    assert response1.status_code == 200
    assert response1.json()["status"] == "ok"
    
    # Second request with same message_id
    response2 = client.post("/webhook", json=payload, headers=headers)
    assert response2.status_code == 200
    assert response2.json()["status"] == "ok"


def test_webhook_missing_required_fields(client):
    """Test webhook with missing required fields."""
    payload = {
        "message_id": "m5",
        "from": "+919876543210",
        # Missing 'to' and 'ts'
    }
    
    signature = generate_signature(payload, "testsecret")
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 422


def test_webhook_optional_text_field(client):
    """Test webhook with optional text field."""
    payload = {
        "message_id": "m6",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z"
        # text is optional
    }
    
    signature = generate_signature(payload, "testsecret")
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_text_max_length(client):
    """Test webhook with text exceeding max length."""
    payload = {
        "message_id": "m7",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "x" * 5000  # Exceeds 4096 limit
    }
    
    signature = generate_signature(payload, "testsecret")
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 422
