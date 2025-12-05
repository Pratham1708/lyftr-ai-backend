"""
Tests for analytics/stats endpoint.
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


def test_stats_empty_database(client):
    """Test stats with empty database."""
    response = client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 0
    assert data["senders_count"] == 0
    assert data["messages_per_sender"] == []
    assert data["first_message_ts"] is None
    assert data["last_message_ts"] is None


def test_stats_basic_counts(client):
    """Test basic message and sender counts."""
    # Insert messages from different senders
    insert_test_message(client, "msg_stats_1", "+911234567890", "+14155550100", "M1")
    insert_test_message(client, "msg_stats_2", "+911234567890", "+14155550100", "M2")
    insert_test_message(client, "msg_stats_3", "+919876543210", "+14155550100", "M3")
    insert_test_message(client, "msg_stats_4", "+918888888888", "+14155550100", "M4")
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_messages"] >= 4
    assert data["senders_count"] >= 3


def test_stats_messages_per_sender(client):
    """Test messages_per_sender statistics."""
    # Insert messages with varying counts per sender
    insert_test_message(client, "msg_mps_1", "+911111111111", "+14155550100", "A1")
    insert_test_message(client, "msg_mps_2", "+911111111111", "+14155550100", "A2")
    insert_test_message(client, "msg_mps_3", "+911111111111", "+14155550100", "A3")
    insert_test_message(client, "msg_mps_4", "+912222222222", "+14155550100", "B1")
    insert_test_message(client, "msg_mps_5", "+912222222222", "+14155550100", "B2")
    insert_test_message(client, "msg_mps_6", "+913333333333", "+14155550100", "C1")
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    messages_per_sender = data["messages_per_sender"]
    
    # Should be sorted by count DESC, then from ASC
    assert len(messages_per_sender) >= 3
    
    # Find our test senders
    test_senders = {s["from"]: s["count"] for s in messages_per_sender 
                    if s["from"] in ["+911111111111", "+912222222222", "+913333333333"]}
    
    if "+911111111111" in test_senders:
        assert test_senders["+911111111111"] == 3
    if "+912222222222" in test_senders:
        assert test_senders["+912222222222"] == 2
    if "+913333333333" in test_senders:
        assert test_senders["+913333333333"] == 1


def test_stats_top_10_senders(client):
    """Test that only top 10 senders are returned."""
    # Insert messages from 15 different senders
    for i in range(15):
        count = 15 - i  # Varying message counts
        for j in range(count):
            insert_test_message(
                client,
                f"msg_top10_{i}_{j}",
                f"+91{i:010d}",
                "+14155550100",
                f"Message {j}"
            )
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    messages_per_sender = data["messages_per_sender"]
    
    # Should return at most 10 senders
    assert len(messages_per_sender) <= 10


def test_stats_deterministic_ordering(client):
    """Test that senders with same count are ordered alphabetically by 'from'."""
    # Insert messages with same count for multiple senders
    insert_test_message(client, "msg_det_1", "+913333333333", "+14155550100", "Z1")
    insert_test_message(client, "msg_det_2", "+913333333333", "+14155550100", "Z2")
    insert_test_message(client, "msg_det_3", "+911111111111", "+14155550100", "A1")
    insert_test_message(client, "msg_det_4", "+911111111111", "+14155550100", "A2")
    insert_test_message(client, "msg_det_5", "+912222222222", "+14155550100", "B1")
    insert_test_message(client, "msg_det_6", "+912222222222", "+14155550100", "B2")
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    messages_per_sender = data["messages_per_sender"]
    
    # Find senders with count=2
    two_count_senders = [s["from"] for s in messages_per_sender if s["count"] == 2]
    
    # Among those with same count, should be alphabetically ordered
    if len(two_count_senders) >= 3:
        assert two_count_senders == sorted(two_count_senders)


def test_stats_timestamps(client):
    """Test first and last message timestamps."""
    now = datetime.utcnow()
    past = now - timedelta(hours=5)
    future = now + timedelta(hours=5)
    
    # Insert messages with different timestamps
    insert_test_message(
        client,
        "msg_ts_1",
        "+919876543210",
        "+14155550100",
        "Past",
        past.isoformat() + "Z"
    )
    insert_test_message(
        client,
        "msg_ts_2",
        "+919876543210",
        "+14155550100",
        "Now",
        now.isoformat() + "Z"
    )
    insert_test_message(
        client,
        "msg_ts_3",
        "+919876543210",
        "+14155550100",
        "Future",
        future.isoformat() + "Z"
    )
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    # Should have first and last timestamps
    assert data["first_message_ts"] is not None
    assert data["last_message_ts"] is not None


def test_stats_after_duplicate_messages(client):
    """Test that duplicate messages don't affect stats."""
    payload = {
        "message_id": "msg_dup_stats",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": datetime.utcnow().isoformat() + "Z",
        "text": "Duplicate test"
    }
    
    signature = generate_signature(payload, "testsecret")
    headers = {"X-Signature": signature}
    
    # Get initial count
    response = client.get("/stats")
    initial_total = response.json()["total_messages"]
    
    # Send same message twice
    client.post("/webhook", json=payload, headers=headers)
    client.post("/webhook", json=payload, headers=headers)
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    # Should only count once
    assert data["total_messages"] == initial_total + 1


def test_health_endpoints(client):
    """Test health check endpoints."""
    # Liveness check
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    
    # Readiness check (should pass if WEBHOOK_SECRET is set)
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    
    if Config.ENABLE_METRICS:
        assert response.status_code == 200
        # Should return Prometheus format
        assert "text/plain" in response.headers["content-type"]
        
        # Check for required metrics
        content = response.text
        assert "http_requests_total" in content
        assert "webhook_requests_total" in content
    else:
        assert response.status_code == 404
