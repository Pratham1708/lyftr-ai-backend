"""
Pydantic models for request/response validation and data structures.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class WebhookPayload(BaseModel):
    """Incoming webhook payload structure with full validation."""
    
    message_id: str = Field(..., min_length=1, description="Unique message identifier")
    from_: str = Field(..., alias="from", description="Sender MSISDN in E.164 format")
    to: str = Field(..., description="Recipient MSISDN in E.164 format")
    ts: datetime = Field(..., description="Message timestamp in ISO 8601 format")
    text: Optional[str] = Field(default=None, max_length=4096, description="Message text")
    
    @field_validator('message_id')
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        """Ensure message_id is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("message_id cannot be empty or whitespace only")
        return v.strip()
    
    @field_validator('from_', 'to')
    @classmethod
    def validate_e164(cls, v: str) -> str:
        """Validate E.164 phone number format: starts with +, then digits only."""
        if not v:
            raise ValueError("Phone number cannot be empty")
        if not re.match(r'^\+\d+$', v):
            raise ValueError("Phone number must be in E.164 format (start with + followed by digits)")
        return v
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "message_id": "m1",
                "from": "+919876543210",
                "to": "+14155550100",
                "ts": "2025-01-15T10:00:00Z",
                "text": "Hello"
            }
        }


class WebhookResponse(BaseModel):
    """Response for webhook endpoint."""
    status: str = Field(..., description="Processing status")


class Message(BaseModel):
    """Message model for API responses."""
    
    message_id: str
    from_: str = Field(..., alias="from")
    to: str
    ts: datetime
    text: Optional[str] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class MessageListResponse(BaseModel):
    """Paginated message list response."""
    
    data: List[Message]
    total: int
    limit: int
    offset: int


class SenderStats(BaseModel):
    """Statistics for a single sender."""
    
    from_: str = Field(..., alias="from")
    count: int
    
    class Config:
        populate_by_name = True


class StatsResponse(BaseModel):
    """Analytics statistics response."""
    
    total_messages: int
    senders_count: int
    messages_per_sender: List[SenderStats]
    first_message_ts: Optional[datetime] = None
    last_message_ts: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    timestamp: datetime
    database: Optional[str] = None
