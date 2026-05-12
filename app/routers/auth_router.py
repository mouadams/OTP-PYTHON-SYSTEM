import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import (
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    UserRegisterRequest, RegisterResponse,
    UserLoginRequest, TokenResponse,
)
from app.services.otp_service   import otp_service, OTPError, OTP_EXPIRY_MINUTES
from app.services.email_service  import email_service
from app.services.auth_service   import auth_service

logger = logging.getLogger(__name__)
router = APIRouter()

DB = Annotated[Session, Depends(get_db)]


# ── POST /auth/send-otp ────────────────────────────────────────────────────

@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(payload: SendOTPRequest, bg: BackgroundTasks, db: DB):
    """Step 1 — generate OTP and email it."""
    try:
        record = otp_service.create_otp(db, payload.email, payload.purpose)
    except OTPError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    bg.add_task(
        email_service.send_otp_email,
        recipient_email=str(payload.email),
        otp_code=record.otp_code,
        purpose=payload.purpose,
        expiry_minutes=OTP_EXPIRY_MINUTES,
    )

    masked = otp_service.mask_email(str(payload.email))
    return SendOTPResponse(
        success=True,
        message=f"Verification code sent to {masked}",
        masked_email=masked,
        expires_in_seconds=OTP_EXPIRY_MINUTES * 60,
    )


# ── POST /auth/verify-otp ──────────────────────────────────────────────────

@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(payload: VerifyOTPRequest, db: DB):
    """Step 2 — validate the OTP code."""
    try:
        otp_service.verify_otp(db, str(payload.email), payload.otp_code, payload.purpose)
    except OTPError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return VerifyOTPResponse(
        success=True,
        message="Email verified. You may now complete registration.",
        verified=True,
    )


# ── POST /auth/register ────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: UserRegisterRequest, db: DB):
    """Step 3 — create account (requires prior OTP verification)."""

    # Gate: confirm OTP was verified within grace window
    if not otp_service.is_email_verified(db, str(payload.email), "registration"):
        raise HTTPException(
            status_code=400,
            detail="Email not verified. Please complete OTP verification first.",
        )

    try:
        user = auth_service.create_user(
            db,
            full_name=payload.full_name,
            email=str(payload.email),
            password=payload.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = auth_service.create_access_token({"sub": str(user.id), "email": user.email})

    return RegisterResponse(
        success=True,
        message="Account created and email verified successfully!",
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


# ── POST /auth/login ───────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLoginRequest, db: DB):
    """Standard JWT login — unchanged from existing logic."""
    user = auth_service.authenticate_user(db, str(payload.email), payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = auth_service.create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )
