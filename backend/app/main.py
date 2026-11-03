from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.session import Base, engine
from app.models import User  # noqa: F401
from app.api.v1.auth import router as auth_router
from app.api.v1.railway import router as railway_router

app = FastAPI(title="Railway Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    # Starter convenience only. Replace with Alembic migrations before production.
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth_router, prefix="/api/v1")
app.include_router(railway_router, prefix="/api/v1")
