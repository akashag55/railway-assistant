from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1.railway import router as railway_router
from app.api.v1.routes import router as routes_router
from app.services.route_jobs import recover_interrupted


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The schema is managed by Alembic (`alembic upgrade head` runs before the server starts).
    recover_interrupted()
    yield


app = FastAPI(title="Railway Assistant API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth_router, prefix="/api/v1")
app.include_router(railway_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
