import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth / User ────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    full_name: str  = Field(..., min_length=2, max_length=100)
    email:     EmailStr
    password:  str  = Field(..., min_length=8, max_length=128)
    otp_code:  str  = Field(..., min_length=6, max_length=6)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("otp_code")
    @classmethod
    def otp_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must be digits only")
        return v

    model_config = {"str_strip_whitespace": True}


class UserLoginRequest(BaseModel):
    email:    EmailStr
    password: str

    model_config = {"str_strip_whitespace": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    email:        str
    full_name:    str


class UserResponse(BaseModel):
    id:          int
    full_name:   str
    email:       str
    is_verified: bool

    model_config = {"from_attributes": True}


# ── OTP ────────────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    email:   EmailStr
    purpose: str = Field(
        default="registration",
        pattern="^(registration|password_reset|email_change|2fa)$",
    )
    model_config = {"str_strip_whitespace": True}


class VerifyOTPRequest(BaseModel):
    email:    EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)
    purpose:  str = Field(
        default="registration",
        pattern="^(registration|password_reset|email_change|2fa)$",
    )

    @field_validator("otp_code")
    @classmethod
    def otp_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must be digits only")
        return v

    model_config = {"str_strip_whitespace": True}


class SendOTPResponse(BaseModel):
    success:           bool
    message:           str
    masked_email:      str
    expires_in_seconds: int = 300


class VerifyOTPResponse(BaseModel):
    success:  bool
    message:  str
    verified: bool


class RegisterResponse(BaseModel):
    success:      bool
    message:      str
    access_token: Optional[str] = None
    token_type:   str           = "bearer"
    user_id:      Optional[int] = None
    email:        Optional[str] = None
    full_name:    Optional[str] = None
