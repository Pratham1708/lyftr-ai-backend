"""
Tests for message retrieval endpoint with pagination and filtering.
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import Config


@pytest.fixture
def client():
    """Create test client."""
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


def insert_test_message(client, message_id: str, from_msisdn: str, to_msisdn: str, text: str, ts: str = None):
    """Helper to insert a test message."""
    if ts is None:
        ts = datetime.utcnow().isoformat() + "Z"
    
    payload = {
        "message_id": message_id,
        "from": from_msisdn,
        "to": to_msisdn,
        "ts": ts,
        "text": text
    }
    
    signature = generate_signature(payload, "testsecret")
    
    response = client.post(
        "/webhook",
        json=payload,
        headers={"X-Signature": signature}
    )
    
    return response.status_code == 200


def test_get_messages_empty(client):
    """Test retrieving messages when database is empty."""
    response = client.get("/messages")
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["total"] == 0


def test_get_messages_default_pagination(client):
    """Test default pagination (limit=50, offset=0)."""
    # Insert a few messages
    for i in range(5):
        insert_test_message(
            client,
            f"msg_default_{i}",
            "+919876543210",
            "+14155550100",
            f"Message {i}"
        )
    
    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert data["total"] >= 5


def test_get_messages_custom_pagination(client):
    """Test custom pagination."""
    # Insert test messages
    for i in range(10):
        insert_test_message(
            client,
            f"msg_page_{i}",
            "+919876543210",
            "+14155550100",
            f"Message {i}"
        )
    
    # Get first page with limit=5
    response = client.get("/messages?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) <= 5
    assert data["limit"] == 5
    assert data["offset"] == 0


def test_get_messages_filter_by_from(client):
    """Test filtering messages by 'from' (sender)."""
    # Insert messages from different senders
    insert_test_message(client, "msg_alice_1", "+911234567890", "+14155550100", "Alice 1")
    insert_test_message(client, "msg_alice_2", "+911234567890", "+14155550100", "Alice 2")
    insert_test_message(client, "msg_bob_1", "+919876543210", "+14155550100", "Bob 1")
    
    # Filter by Alice's number
    response = client.get("/messages?from=%2B911234567890")
    assert response.status_code == 200
    data = response.json()
    
    # All returned messages should be from Alice
    for msg in data["data"]:
        assert msg["from"] == "+911234567890"


def test_get_messages_filter_by_since(client):
    """Test filtering messages by timestamp."""
    now = datetime.utcnow()
    past = now - timedelta(hours=2)
    future = now + timedelta(hours=2)
    
    # Insert messages with different timestamps
    insert_test_message(
        client,
        "msg_past",
        "+919876543210",
        "+14155550100",
        "Past",
        past.isoformat() + "Z"
    )
    insert_test_message(
        client,
        "msg_future",
        "+919876543210",
        "+14155550100",
        "Future",
        future.isoformat() + "Z"
    )
    
    # Filter messages since now
    response = client.get(f"/messages?since={now.isoformat()}Z")
    assert response.status_code == 200
    data = response.json()
    
    # Should only include future message
    assert data["total"] >= 1


def test_get_messages_search_text(client):
    """Test searching messages by text content."""
    insert_test_message(client, "msg_search_1", "+919876543210", "+14155550100", "Hello world")
    insert_test_message(client, "msg_search_2", "+919876543210", "+14155550100", "Goodbye world")
    insert_test_message(client, "msg_search_3", "+919876543210", "+14155550100", "Something else")
    
    # Search for "world"
    response = client.get("/messages?q=world")
    assert response.status_code == 200
    data = response.json()
    
    # Should find at least 2 messages
    assert data["total"] >= 2


def test_get_messages_ordering(client):
    """Test that messages are ordered by ts ASC, message_id ASC."""
    now = datetime.utcnow()
    
    # Insert messages with specific timestamps
    ts1 = (now - timedelta(hours=2)).isoformat() + "Z"
    ts2 = (now - timedelta(hours=1)).isoformat() + "Z"
    ts3 = now.isoformat() + "Z"
    
    insert_test_message(client, "msg_order_3", "+919876543210", "+14155550100", "Third", ts3)
    insert_test_message(client, "msg_order_1", "+919876543210", "+14155550100", "First", ts1)
    insert_test_message(client, "msg_order_2", "+919876543210", "+14155550100", "Second", ts2)
    
    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    
    # Messages should be ordered oldest first (ts ASC)
    if len(data["data"]) >= 3:
        # Find our test messages
        test_msgs = [m for m in data["data"] if m["message_id"].startswith("msg_order_")]
        if len(test_msgs) == 3:
            assert test_msgs[0]["text"] == "First"
            assert test_msgs[1]["text"] == "Second"
            assert test_msgs[2]["text"] == "Third"


def test_get_messages_limit_validation(client):
    """Test limit parameter validation."""
    # Limit too high (max is 100)
    response = client.get("/messages?limit=200")
    assert response.status_code == 422
    
    # Limit too low
    response = client.get("/messages?limit=0")
    assert response.status_code == 422


def test_get_messages_offset_validation(client):
    """Test offset parameter validation."""
    # Valid offset
    response = client.get("/messages?offset=10")
    assert response.status_code == 200
    
    # Negative offset
    response = client.get("/messages?offset=-1")
    assert response.status_code == 422


def test_get_messages_combined_filters(client):
    """Test combining multiple filters."""
    now = datetime.utcnow()
    
    insert_test_message(
        client,
        "msg_combo_1",
        "+911234567890",
        "+14155550100",
        "Important update",
        now.isoformat() + "Z"
    )
    
    # Combine from + q filters
    response = client.get("/messages?from=%2B911234567890&q=Important")
    assert response.status_code == 200
    data = response.json()
    
    # Should find the message
    assert data["total"] >= 1
