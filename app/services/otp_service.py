import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.otp_verification import OTPVerification

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES:        int = 5
OTP_MAX_ATTEMPTS:          int = 5
OTP_RESEND_COOLDOWN_SECS:  int = 60
OTP_MAX_DAILY_SENDS:       int = 10


# ── Exceptions ─────────────────────────────────────────────────────────────

class OTPError(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400):
        super().__init__(message)
        self.message     = message
        self.error_code  = error_code
        self.status_code = status_code

class OTPExpiredError(OTPError):
    def __init__(self):
        super().__init__("Verification code has expired. Please request a new one.", "OTP_EXPIRED")

class OTPInvalidError(OTPError):
    def __init__(self, attempts_left: int):
        super().__init__(f"Invalid code. {attempts_left} attempt(s) remaining.", "OTP_INVALID")

class OTPMaxAttemptsError(OTPError):
    def __init__(self):
        super().__init__("Too many failed attempts. Please request a new code.", "OTP_MAX_ATTEMPTS", 429)

class OTPRateLimitError(OTPError):
    def __init__(self, seconds_remaining: int):
        super().__init__(f"Please wait {seconds_remaining}s before requesting a new code.", "OTP_RATE_LIMIT", 429)

class OTPDailyLimitError(OTPError):
    def __init__(self):
        super().__init__("Daily OTP limit reached. Try again tomorrow.", "OTP_DAILY_LIMIT", 429)

class OTPNotFoundError(OTPError):
    def __init__(self):
        super().__init__("No active verification code found. Please request a new one.", "OTP_NOT_FOUND", 404)


# ── Service ────────────────────────────────────────────────────────────────

class OTPService:

    def generate_otp(self) -> str:
        return str(secrets.randbelow(900_000) + 100_000)

    def mask_email(self, email: str) -> str:
        local, domain = email.split("@", 1)
        masked = local[0] + "*" * max(1, len(local) - 1)
        return f"{masked}@{domain}"

    def _check_rate_limits(self, db: Session, email: str, purpose: str) -> None:
        now = datetime.now(timezone.utc)

        recent = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email == email,
                OTPVerification.purpose == purpose,
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

        if recent:
            created_at = recent.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            elapsed = (now - created_at).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN_SECS:
                raise OTPRateLimitError(int(OTP_RESEND_COOLDOWN_SECS - elapsed))

        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email == email,
                OTPVerification.purpose == purpose,
                OTPVerification.created_at >= day_start,
            )
            .count()
        )
        if daily >= OTP_MAX_DAILY_SENDS:
            raise OTPDailyLimitError()

    def create_otp(self, db: Session, email: str, purpose: str = "registration") -> OTPVerification:
        email = email.lower().strip()
        self._check_rate_limits(db, email, purpose)

        # Invalidate previous unused OTPs for this email+purpose
        db.query(OTPVerification).filter(
            OTPVerification.email == email,
            OTPVerification.purpose == purpose,
            OTPVerification.is_used == False,   # noqa: E712
        ).update({"is_used": True})

        now = datetime.now(timezone.utc)
        record = OTPVerification(
            email          = email,
            purpose        = purpose,
            otp_code       = self.generate_otp(),
            created_at     = now,
            expires_at     = now + timedelta(minutes=OTP_EXPIRY_MINUTES),
            verified       = False,
            is_used        = False,
            attempts_count = 0,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info("OTP created — email=%s purpose=%s id=%d", email, purpose, record.id)
        return record

    def verify_otp(self, db: Session, email: str, otp_code: str, purpose: str = "registration") -> OTPVerification:
        email = email.lower().strip()
        now   = datetime.now(timezone.utc)

        record: Optional[OTPVerification] = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email   == email,
                OTPVerification.purpose == purpose,
                OTPVerification.is_used == False,   # noqa: E712
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

        if not record:
            raise OTPNotFoundError()

        if record.attempts_count >= OTP_MAX_ATTEMPTS:
            raise OTPMaxAttemptsError()

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            record.is_used = True
            db.commit()
            raise OTPExpiredError()

        if record.otp_code != otp_code:
            record.attempts_count += 1
            db.commit()
            left = OTP_MAX_ATTEMPTS - record.attempts_count
            if record.attempts_count >= OTP_MAX_ATTEMPTS:
                raise OTPMaxAttemptsError()
            raise OTPInvalidError(attempts_left=left)

        record.verified = True
        record.is_used  = True
        db.commit()
        db.refresh(record)
        logger.info("OTP verified — email=%s purpose=%s", email, purpose)
        return record

    def is_email_verified(self, db: Session, email: str, purpose: str = "registration") -> bool:
        """Check for a verified OTP within the last 10-minute grace window."""
        email = email.lower().strip()
        now   = datetime.now(timezone.utc)
        grace = timedelta(minutes=10)

        record = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.email    == email,
                OTPVerification.purpose  == purpose,
                OTPVerification.verified == True,    # noqa: E712
                OTPVerification.is_used  == True,    # noqa: E712
                OTPVerification.expires_at >= (now - grace),
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        return record is not None

    def cleanup_expired(self, db: Session) -> int:
        from datetime import timedelta
        cutoff  = datetime.now(timezone.utc) - timedelta(hours=24)
        deleted = (
            db.query(OTPVerification)
            .filter(OTPVerification.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info("OTP cleanup: removed %d records", deleted)
        return deleted


otp_service = OTPService()
