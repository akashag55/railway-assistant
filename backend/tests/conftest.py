import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app import models  # noqa: F401  (register all tables on Base.metadata)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def override():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)  # no context manager: skips startup, which needs the real database
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    def register(email="user@example.com"):
        res = client.post("/api/v1/auth/register", json={"email": email, "password": "goodpass123"})
        assert res.status_code == 201
        return {"Authorization": f"Bearer {res.json()['access_token']}"}
    return register
