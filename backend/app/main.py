import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bins import router as bins_router
from app.api.v1.classifications import router as classifications_router
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.recovery import router as recovery_router
from app.api.v1.recyclers import router as recyclers_router
from app.api.v1.routes import router as routes_router
from app.api.v1.users import router as locations_router
from app.api.v1.voice import router as voice_router
from app.core.config import get_settings
from app.db.session import engine
from app.services.classifier import classifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("recyclink.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    classifier.load()
    yield

app = FastAPI(title="RecycLink API", version="0.1.0", description="RecycLink development API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(locations_router, prefix="/api/v1")
app.include_router(recyclers_router, prefix="/api/v1")
app.include_router(classifications_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
app.include_router(recovery_router, prefix="/api/v1")
app.include_router(bins_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")

# In a deployed container, serve the built SPA from the same origin as the API.
# Same-origin delivery keeps the HttpOnly session cookie and CSRF flow simple.
frontend_dist = Path(__file__).resolve().parents[1] / "static"
if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


@app.get("/api/v1/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "recyclink-api"}


@app.get("/api/v1/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ready", "database": "connected"}
