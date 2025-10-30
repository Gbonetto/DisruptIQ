"""
Document Model
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, BigInteger
from sqlalchemy.sql import func
from app.core.database import Base


class Document(Base):
    """Document storage and metadata model"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # File information
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String)  # Local storage path
    file_size = Column(BigInteger)  # Size in bytes
    mime_type = Column(String)

    # Document metadata
    document_type = Column(String, index=True)  # "invoice", "contract", "letter", etc.
    category = Column(String)
    tags = Column(JSON, default=list)

    # Content
    extracted_text = Column(Text)  # OCR/extracted text
    summary = Column(Text)  # LLM-generated summary

    # Vector database reference
    qdrant_id = Column(String, index=True)  # Reference to Qdrant vector

    # Related entities
    vendor_id = Column(Integer, index=True)
    property_id = Column(String, index=True)

    # Document-specific data (for invoices, contracts, etc.)
    document_metadata = Column(JSON, default=dict)  # Flexible metadata storage

    # Processing status
    processed = Column(Boolean, default=False)
    indexed = Column(Boolean, default=False)

    # Timestamps
    document_date = Column(DateTime(timezone=True))  # Date on the document
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<Document {self.filename} ({self.document_type})>"
