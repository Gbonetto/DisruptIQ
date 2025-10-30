"""
Vendor Pydantic Schemas
"""

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class VendorBase(BaseModel):
    """Base vendor schema"""
    name: str
    company_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    category: str
    specialties: List[str] = []
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None


class VendorCreate(VendorBase):
    """Schema for creating a vendor"""
    pass


class VendorUpdate(BaseModel):
    """Schema for updating a vendor"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    category: Optional[str] = None
    specialties: Optional[List[str]] = None
    notes: Optional[str] = None


class VendorResponse(VendorBase):
    """Vendor API response"""
    id: int
    rating: float
    total_jobs: int
    last_contacted: Optional[datetime]
    is_indexed: bool
    last_indexed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class VendorSearch(BaseModel):
    """Vendor search criteria"""
    category: Optional[str] = None
    city: Optional[str] = None
    min_rating: Optional[float] = None
    specialties: Optional[List[str]] = None


class VendorBulkImport(BaseModel):
    """Bulk import vendors from CSV"""
    vendors: List[VendorCreate]
