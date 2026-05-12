import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.config   import settings

# ── Import ALL models so Base.metadata knows about every table ─────────────
import app.models   # noqa: F401  (triggers __init__.py → registers User + OTPVerification)

from app.routers.auth_router import router as auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates all missing tables on startup — safe, non-destructive
    logger.info("Creating DB tables if they don't exist…")
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready  ✓")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="FastAPI backend with OTP email verification",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
