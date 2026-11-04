import asyncio
from datetime import datetime, timedelta

import httpx
import pytest

from app.api.v1 import railway
from app.providers import railkit
from app.providers.railkit import RailKitError, RailKitProvider
from app.services import route_jobs

FUTURE = (datetime.now() + timedelta(days=5)).strftime("%d-%m-%Y")
PAST = (datetime.now() - timedelta(days=5)).strftime("%d-%m-%Y")
BODY = {"from": "JP", "to": "BCT", "date": FUTURE, "travel_class": "3A"}


@pytest.fixture(autouse=True)
def no_background_tasks(monkeypatch):
    monkeypatch.setattr(route_jobs, "start", lambda search_id: None)


def test_register_login_and_me(client):
    creds = {"email": "New@Example.com", "password": "goodpass123"}
    assert client.post("/api/v1/auth/register", json=creds).status_code == 201
    assert client.post("/api/v1/auth/register", json=creds).status_code == 409
    token = client.post("/api/v1/auth/login", json=creds).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "new@example.com"


def test_short_password_and_wrong_login_rejected(client):
    assert client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "short"}).status_code == 422
    assert client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrongpass12"}).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/auth/me"),
    ("get", "/api/v1/railway/trains/between?from=JP&to=BCT"),
    ("get", "/api/v1/routes/search"),
    ("get", "/api/v1/routes/search/1"),
    ("post", "/api/v1/routes/search/1/cancel"),
])
def test_protected_endpoints_need_a_token(client, method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers={"Authorization": "Bearer bad"}).status_code == 401


def test_past_date_and_bad_class_rejected(client, auth):
    h = auth()
    assert client.get(f"/api/v1/railway/trains/between?from=JP&to=BCT&date={PAST}", headers=h).status_code == 422
    assert client.post("/api/v1/routes/search", json={**BODY, "date": PAST}, headers=h).status_code == 422
    assert client.post("/api/v1/routes/search", json={**BODY, "travel_class": "GEN"}, headers=h).status_code == 422


def test_provider_failure_is_an_error_not_an_empty_result(client, auth, monkeypatch):
    class Failing:
        def __init__(self, **_):
            pass

        async def search_trains(self, *_):
            raise RailKitError("RailKit rate limit reached.", status_code=429)

    monkeypatch.setattr(railway, "RailKitProvider", Failing)
    res = client.get("/api/v1/railway/trains/between?from=JP&to=BCT", headers=auth())
    assert res.status_code == 429 and "rate limit" in res.json()["detail"]


def test_route_search_lifecycle_and_one_active_per_user(client, auth):
    h = auth()
    res = client.post("/api/v1/routes/search", json=BODY, headers=h)
    assert res.status_code == 202 and res.json()["status"] == "queued"
    assert client.post("/api/v1/routes/search", json=BODY, headers=h).status_code == 409
    assert client.get(f"/api/v1/routes/search/{res.json()['id']}", headers=h).status_code == 200
    assert len(client.get("/api/v1/routes/search", headers=h).json()) == 1


def test_users_cannot_see_or_cancel_each_others_searches(client, auth):
    owner, other = auth("owner@example.com"), auth("other@example.com")
    search_id = client.post("/api/v1/routes/search", json=BODY, headers=owner).json()["id"]
    assert client.get(f"/api/v1/routes/search/{search_id}", headers=other).status_code == 404
    assert client.post(f"/api/v1/routes/search/{search_id}/cancel", headers=other).status_code == 404
    assert client.get("/api/v1/routes/search", headers=other).json() == []


def provider_with(monkeypatch, handler, **kwargs):
    real = httpx.AsyncClient
    monkeypatch.setattr(railkit.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    provider = RailKitProvider(**kwargs)
    provider.api_key = "test-key"
    return provider


@pytest.mark.parametrize("status,body,expected", [
    (403, {"success": False, "error": "upgrade your plan"}, 503),
    (400, {"success": False, "error": "Unable"}, 400),
    (500, {}, 502),
])
def test_provider_status_mapping(monkeypatch, status, body, expected):
    provider = provider_with(monkeypatch, lambda r: httpx.Response(status, json=body))
    with pytest.raises(RailKitError) as err:
        asyncio.run(provider.search_trains("JP", "BCT", None))
    assert err.value.status_code == expected


def test_provider_bad_json_is_an_error_and_logs_only_the_endpoint_template(monkeypatch):
    seen = []
    provider = provider_with(monkeypatch, lambda r: httpx.Response(200, text="<html>"),
                             on_request=lambda endpoint, status, ms: seen.append(endpoint))
    with pytest.raises(RailKitError):
        asyncio.run(provider.availability("12345", "JP", "BCT", "09-11-2026", "3A", "GN"))
    assert seen == ["/api/v1/seats/{train}/{from}/{to}/{date}/{class}/{quota}"]


def test_provider_timeout_is_a_504(monkeypatch):
    def timeout(request):
        raise httpx.ConnectTimeout("slow")

    provider = provider_with(monkeypatch, timeout)
    with pytest.raises(RailKitError) as err:
        asyncio.run(provider.train_info("12345"))
    assert err.value.status_code == 504
