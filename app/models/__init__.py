# Import all models here so Base.metadata.create_all() picks them up
from app.models.user import User
from app.models.otp_verification import OTPVerification

__all__ = ["User", "OTPVerification"]
