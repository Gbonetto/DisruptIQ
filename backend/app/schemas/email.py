"""
Email Pydantic Schemas
"""

from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class EmailUrgency(str, Enum):
    """Email urgency levels"""
    URGENT = "urgent"
    IMPORTANT = "important"
    ROUTINE = "routine"


class EmailClassification(BaseModel):
    """Email classification result"""
    urgency: EmailUrgency
    category: str
    reasoning: str
    suggested_actions: List[str]


class EmailAttachment(BaseModel):
    """Email attachment info"""
    filename: str
    size: int
    mime_type: str
    url: Optional[str] = None


class EmailResponse(BaseModel):
    """Email API response"""
    id: int
    subject: str
    sender: str
    body: str
    urgency: EmailUrgency
    category: Optional[str]
    attachments: List[EmailAttachment]
    received_at: datetime
    time_ago: str

    class Config:
        from_attributes = True


class DigestEmailGroup(BaseModel):
    """Group of emails by urgency"""
    urgency: EmailUrgency
    count: int
    emails: List[EmailResponse]


class DigestResponse(BaseModel):
    """Daily digest response"""
    date: datetime
    total_emails: int
    urgent: DigestEmailGroup
    important: DigestEmailGroup
    routine: DigestEmailGroup
    generated_at: datetime


class EmailGenerateRequest(BaseModel):
    """Request to generate an email"""
    prompt: str
    context: Optional[Dict] = None


class EmailGenerateResponse(BaseModel):
    """Generated email response"""
    subject: str
    body: str
    recipients: List[EmailStr]
    draft_id: Optional[str]
    n8n_webhook_available: bool
