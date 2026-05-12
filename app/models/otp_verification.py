from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    email          = Column(String(255), nullable=False, index=True)
    purpose        = Column(String(50), nullable=False, default="registration")
    otp_code       = Column(String(6), nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at     = Column(DateTime(timezone=True), nullable=False)
    verified       = Column(Boolean, default=False, nullable=False)
    is_used        = Column(Boolean, default=False, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_otp_email_purpose_used", "email", "purpose", "is_used"),
    )

    def __repr__(self):
        return f"<OTPVerification id={self.id} email={self.email} purpose={self.purpose}>"
