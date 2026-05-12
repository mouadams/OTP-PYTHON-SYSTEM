import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)


class AuthService:

    # ── Passwords ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_72_bytes(password: str) -> str:
        """Encode to UTF-8 and hard-clip at 72 bytes before bcrypt sees it."""
        raw = password.encode("utf-8")[:72]
        # decode ignoring any split multi-byte char at the boundary
        return raw.decode("utf-8", errors="ignore")

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(AuthService._to_72_bytes(password))

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(AuthService._to_72_bytes(plain), hashed)

    # ── JWT ─────────────────────────────────────────────────────────────────

    @staticmethod
    def create_access_token(data: dict) -> str:
        payload = data.copy()
        expire  = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload.update({"exp": expire})
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            return None

    # ── User CRUD ───────────────────────────────────────────────────────────

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email.lower().strip()).first()

    @staticmethod
    def create_user(db: Session, full_name: str, email: str, password: str) -> User:
        email = email.lower().strip()
        if AuthService.get_user_by_email(db, email):
            raise ValueError("Email already registered")

        user = User(
            full_name       = full_name.strip(),
            email           = email,
            hashed_password = AuthService.hash_password(password),
            is_active       = True,
            is_verified     = True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("User created — id=%d email=%s", user.id, email)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        user = AuthService.get_user_by_email(db, email)
        if not user:
            return None
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        return user


auth_service = AuthService()