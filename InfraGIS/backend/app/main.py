import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.bootstrap import ensure_bootstrap_admin
from app.config import settings
from app.database import SessionLocal, engine
from app.routers import admin, auth, layers, media360


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Ensure local storage roots exist before serving requests.
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.media_upload_path.mkdir(parents=True, exist_ok=True)
    settings.media_processed_path.mkdir(parents=True, exist_ok=True)
    if os.environ.get("TESTING") != "1":
        # Bootstrap default admin only outside test mode.
        db: Session = SessionLocal()
        try:
            ensure_bootstrap_admin(db)
        finally:
            db.close()
    yield


app = FastAPI(title="InfraGIS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API modules are mounted as independent routers for clean domain boundaries.
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(layers.router)
app.include_router(media360.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
