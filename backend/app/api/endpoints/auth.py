"""
Authentication Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from datetime import timedelta

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token
)
from app.core.config import settings

router = APIRouter()


class UserCreate(BaseModel):
    """User registration schema"""
    email: EmailStr
    password: str
    full_name: str


class Token(BaseModel):
    """Token response"""
    access_token: str
    token_type: str


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate):
    """Register a new user"""
    # TODO: Check if user exists
    # TODO: Create user in database

    # For now, just return a token
    access_token = create_access_token(
        data={"sub": user_data.email, "email": user_data.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint"""
    # TODO: Verify user credentials from database
    # For now, accept any login

    access_token = create_access_token(
        data={"sub": form_data.username, "email": form_data.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me")
async def get_current_user_info():
    """Get current user information"""
    # TODO: Get from database
    return {
        "email": "user@example.com",
        "full_name": "Test User"
    }
