#!/usr/bin/env python3
"""
Script to query messages and stats from the API.
"""
import requests
import json
from datetime import datetime, timedelta


def get_messages(base_url: str, **params):
    """Retrieve messages with optional filters."""
    response = requests.get(f"{base_url}/messages", params=params)
    return response


def get_stats(base_url: str):
    """Get analytics statistics."""
    response = requests.get(f"{base_url}/stats")
    return response


def get_health(base_url: str):
    """Check service health."""
    live = requests.get(f"{base_url}/health/live")
    ready = requests.get(f"{base_url}/health/ready")
    return live, ready


if __name__ == "__main__":
    BASE_URL = "http://localhost:8000"
    
    print("=" * 60)
    print("Lyftr AI Webhook Service - Query Examples")
    print("=" * 60)
    
    # Health check
    print("\n1. Health Check")
    print("-" * 60)
    try:
        live, ready = get_health(BASE_URL)
        print(f"Liveness: {live.status_code} - {live.json()}")
        print(f"Readiness: {ready.status_code} - {ready.json()}")
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
    
    # Get all messages
    print("\n2. Get All Messages (first 10)")
    print("-" * 60)
    response = get_messages(BASE_URL, limit=10)
    if response.status_code == 200:
        data = response.json()
        print(f"Total messages: {data['total']}")
        print(f"Returned: {len(data['data'])}")
        for msg in data['data'][:3]:  # Show first 3
            print(f"  - {msg['message_id']}: {msg['from']} → {msg['to']}")
            print(f"    {msg['text'][:50] if msg['text'] else '(no text)'}")
    else:
        print(f"❌ Error: {response.status_code}")
    
    # Filter by sender
    print("\n3. Filter by Sender")
    print("-" * 60)
    response = get_messages(BASE_URL, **{"from": "+919876543210"})
    if response.status_code == 200:
        data = response.json()
        print(f"Messages from +919876543210: {data['total']}")
    
    # Search content
    print("\n4. Search Content")
    print("-" * 60)
    response = get_messages(BASE_URL, q="hello")
    if response.status_code == 200:
        data = response.json()
        print(f"Messages containing 'hello': {data['total']}")
    
    # Filter by timestamp
    print("\n5. Recent Messages (last hour)")
    print("-" * 60)
    since = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
    response = get_messages(BASE_URL, since=since)
    if response.status_code == 200:
        data = response.json()
        print(f"Messages in last hour: {data['total']}")
    
    # Get statistics
    print("\n6. Analytics Statistics")
    print("-" * 60)
    response = get_stats(BASE_URL)
    if response.status_code == 200:
        stats = response.json()
        print(f"Total messages: {stats['total_messages']}")
        print(f"Unique senders: {stats['senders_count']}")
        print(f"\nTop senders:")
        for sender_stat in stats['messages_per_sender'][:5]:
            print(f"  - {sender_stat['from']}: {sender_stat['count']} messages")
        if stats['first_message_ts']:
            print(f"\nFirst message: {stats['first_message_ts']}")
        if stats['last_message_ts']:
            print(f"Last message: {stats['last_message_ts']}")
    else:
        print(f"❌ Error: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("Query examples completed!")
    print("=" * 60)
