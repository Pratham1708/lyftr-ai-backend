"""
FastAPI application with webhook ingestion, message retrieval, and analytics.
"""
import hashlib
import hmac
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Header, Query, Response
from fastapi.responses import PlainTextResponse

from app.config import Config
from app.models import (
    WebhookPayload,
    WebhookResponse,
    MessageListResponse,
    StatsResponse,
    HealthResponse,
    Message
)
from app.storage import MessageStorage
from app.logging_utils import setup_logging, log_request, log_webhook, get_logger, request_id_var
from app.metrics import MetricsCollector, get_metrics


# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Lyftr AI Webhook Service",
    description="Webhook ingestion service with message storage and analytics",
    version="1.0.0"
)

# Initialize storage
storage = MessageStorage()


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature.
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Signature header
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not Config.WEBHOOK_SECRET:
        return False
    
    expected_signature = hmac.new(
        Config.WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Middleware for request logging and metrics."""
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # Log request (non-webhook endpoints)
    if request.url.path != "/webhook":
        log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=duration_ms,
            extra={"request_id": request_id}
        )
    
    # Record metrics
    MetricsCollector.record_http_request(
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms
    )
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    return response


@app.post("/webhook", response_model=WebhookResponse, status_code=200)
async def webhook_endpoint(
    request: Request,
    payload: WebhookPayload,
    x_signature: str = Header(..., alias="X-Signature")
):
    """
    Webhook endpoint with HMAC-SHA256 signature verification.
    
    Implements idempotent message ingestion using message_id as primary key.
    """
    start_time = time.time()
    message_id = payload.message_id
    dup = False
    result = "created"
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify signature
        if not verify_signature(body, x_signature):
            result = "invalid_signature"
            duration_ms = (time.time() - start_time) * 1000
            log_webhook(message_id, False, result, "POST", "/webhook", 401, duration_ms)
            MetricsCollector.record_webhook_request(result)
            raise HTTPException(status_code=401, detail="invalid signature")
        
        # Insert message (idempotent operation)
        was_inserted = storage.insert_message(
            message_id=payload.message_id,
            from_msisdn=payload.from_,
            to_msisdn=payload.to,
            ts=payload.ts,
            text=payload.text
        )
        
        # Determine result
        if was_inserted:
            result = "created"
            dup = False
        else:
            result = "duplicate"
            dup = True
        
        # Record metrics
        MetricsCollector.record_webhook_request(result)
        
        # Log webhook request
        duration_ms = (time.time() - start_time) * 1000
        log_webhook(message_id, dup, result, "POST", "/webhook", 200, duration_ms)
        
        logger.info(
            f"Webhook processed: message_id={payload.message_id}, "
            f"from={payload.from_}, inserted={was_inserted}"
        )
        
        return WebhookResponse(status="ok")
    
    except HTTPException:
        raise
    except Exception as e:
        result = "validation_error"
        duration_ms = (time.time() - start_time) * 1000
        log_webhook(message_id, False, result, "POST", "/webhook", 500, duration_ms)
        MetricsCollector.record_webhook_request(result)
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/messages", response_model=MessageListResponse)
async def get_messages(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    from_: Optional[str] = Query(default=None, alias="from", description="Filter by sender MSISDN"),
    since: Optional[datetime] = Query(default=None, description="Filter messages since timestamp"),
    q: Optional[str] = Query(default=None, description="Search query for message text")
):
    """
    Retrieve messages with pagination and filtering.
    
    Supports:
    - Pagination: limit (1-100, default 50), offset (0+, default 0)
    - Filtering: from (sender), since (timestamp), q (text search)
    - Deterministic ordering: ts ASC, message_id ASC (oldest first)
    """
    try:
        messages, total = storage.get_messages(
            limit=limit,
            offset=offset,
            from_msisdn=from_,
            since=since,
            search_query=q
        )
        
        logger.info(
            f"Retrieved {len(messages)} messages "
            f"(limit={limit}, offset={offset}, total={total})"
        )
        
        return MessageListResponse(
            data=messages,
            total=total,
            limit=limit,
            offset=offset
        )
    
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get analytics statistics.
    
    Returns:
    - total_messages: Total number of messages
    - senders_count: Number of unique senders
    - messages_per_sender: Top 10 senders by message count (sorted by count DESC, from ASC)
    - first_message_ts: Timestamp of first message
    - last_message_ts: Timestamp of last message
    """
    try:
        stats = storage.get_stats()
        
        logger.info(
            f"Stats retrieved: total={stats['total_messages']}, "
            f"senders={stats['senders_count']}"
        )
        
        return StatsResponse(**stats)
    
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health/live", response_model=HealthResponse)
async def liveness_check():
    """
    Liveness probe - checks if application is running.
    Always returns 200 when server is up.
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow()
    )


@app.get("/health/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness probe - checks if application is ready to serve traffic.
    Returns 200 only if:
    - Database is reachable
    - WEBHOOK_SECRET is set
    Otherwise returns 503.
    """
    # Check if WEBHOOK_SECRET is set
    if not Config.is_ready():
        raise HTTPException(status_code=503, detail="WEBHOOK_SECRET not set")
    
    # Check database connectivity
    db_healthy = storage.health_check()
    
    if not db_healthy:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow(),
        database="connected"
    )


@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    
    Exposes:
    - http_requests_total: Counter of HTTP requests by path and status
    - webhook_requests_total: Counter of webhook requests by result
    - request_latency_ms: Histogram of request latency in milliseconds
    """
    if not Config.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Lyftr AI Webhook Service",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "POST /webhook",
            "messages": "GET /messages",
            "stats": "GET /stats",
            "health": {
                "liveness": "GET /health/live",
                "readiness": "GET /health/ready"
            },
            "metrics": "GET /metrics"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {Config.HOST}:{Config.PORT}")
    uvicorn.run(
        "app.main:app",
        host=Config.HOST,
        port=Config.PORT,
        log_config=None  # Use our custom logging
    )
