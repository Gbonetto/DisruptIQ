"""
Vendor Model
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class Vendor(Base):
    """Vendor/service provider model"""

    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)

    # Basic info
    name = Column(String, nullable=False)
    company_name = Column(String)
    email = Column(String, nullable=False, unique=True, index=True)
    phone = Column(String)

    # Business details
    category = Column(String, index=True)  # e.g., "plumber", "electrician", "painter"
    specialties = Column(JSON, default=list)  # List of specialties

    # Location
    address = Column(Text)
    city = Column(String)
    postal_code = Column(String)

    # Performance
    rating = Column(Float, default=0.0)
    total_jobs = Column(Integer, default=0)

    # Contact history
    last_contacted = Column(DateTime(timezone=True))
    notes = Column(Text)

    # Indexing status for RAG (Qdrant synchronization)
    is_indexed = Column(Boolean, default=False, nullable=False, index=True)
    last_indexed_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Vendor {self.name} - {self.category}>"
