import asyncio

from app.core.config import settings
from app.models.route_search import ProviderRequestLog, RouteSearch, TrainRouteCache
from app.models.user import User
from app.services import route_jobs
from tests.fakes import FakeProvider, info, row, stop

DATE = "09-11-2026"


def make_search(session_factory):
    with session_factory() as db:
        user = User(email="a@example.com", hashed_password="x")
        db.add(user)
        db.commit()
        search = RouteSearch(user_id=user.id, status="queued", from_code="JP", to_code="BCT", journey_date=DATE,
                             travel_class="3A", progress={}, results={})
        db.add(search)
        db.commit()
        return search.id


def provider_factory(**_):
    return FakeProvider(
        trains={("JP", "BCT", DATE): [row("11111", "JP", "BCT", "10:00", "10:00")]},
        routes={"11111": info("11111", [stop("JP", "--", "10:00", 1, 0), stop("BCT", "20:00", "--", 1, 900)])},
        seats={("11111", "JP", "BCT", DATE, "3A"): ("WAITLIST", "WL 3")},
    )


def run(search_id, session_factory):
    asyncio.run(route_jobs.run_search(search_id, session_factory, provider_factory))
    with session_factory() as db:
        return db.get(RouteSearch, search_id)


def test_job_completes_saves_results_and_caches_route(session_factory):
    search = run(make_search(session_factory), session_factory)
    assert search.status == "completed" and search.finished_at
    assert search.results["groups"]["no_change"][0]["kind"] == "direct"
    with session_factory() as db:
        assert db.get(TrainRouteCache, "11111")


def test_cancel_marks_cancelled(session_factory):
    search_id = make_search(session_factory)
    route_jobs.request_cancel(search_id)
    assert run(search_id, session_factory).status == "cancelled"


def test_monthly_reserve_stops_search_with_reason(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "railkit_monthly_quota", 1)
    monkeypatch.setattr(settings, "railkit_monthly_reserve", 0)
    search_id = make_search(session_factory)
    with session_factory() as db:
        db.add(ProviderRequestLog(endpoint="/x", status_code=200, latency_ms=1))
        db.commit()
    search = run(search_id, session_factory)
    assert search.status == "completed" and "allowance" in search.progress["stop_reason"]


def test_recover_interrupted_fails_active_searches(session_factory):
    search_id = make_search(session_factory)
    route_jobs.recover_interrupted(session_factory)
    with session_factory() as db:
        assert db.get(RouteSearch, search_id).status == "failed"
