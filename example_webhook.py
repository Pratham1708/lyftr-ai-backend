#!/usr/bin/env python3
"""
Example script to test webhook endpoint with proper signature.
"""
import hashlib
import hmac
import json
import requests
from datetime import datetime


def generate_signature(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    signature = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return signature


def send_webhook(base_url: str, secret: str, message_data: dict):
    """Send a webhook request with proper signature."""
    # Generate signature
    signature = generate_signature(message_data, secret)
    
    # Send request
    response = requests.post(
        f"{base_url}/webhook",
        json=message_data,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    
    return response


if __name__ == "__main__":
    # Configuration
    BASE_URL = "http://localhost:8000"
    WEBHOOK_SECRET = "testsecret"  # Change this to match your .env
    
    # Sample message (matching PDF spec)
    message = {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": datetime.utcnow().isoformat() + "Z",
        "text": "Hello from the example script!"
    }
    
    print("Sending webhook...")
    print(f"Message: {json.dumps(message, indent=2)}")
    
    try:
        response = send_webhook(BASE_URL, WEBHOOK_SECRET, message)
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Webhook sent successfully!")
        else:
            print(f"\n❌ Error: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server. Is it running?")
        print(f"   Try: make up")
    except Exception as e:
        print(f"\n❌ Error: {e}")
