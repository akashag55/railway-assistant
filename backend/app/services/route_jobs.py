"""Runs RouteFinder as a background task and persists progress, results and usage.

Tasks live in this process, so a server restart interrupts them; recover_interrupted()
marks those searches failed at startup. Move this to a dedicated worker before running
more than one backend instance (see project guide section 10).
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.route_search import ProviderRequestLog, RouteSearch, TrainRouteCache
from app.providers.railkit import RailKitError, RailKitProvider
from app.services.route_finder import RouteFinder, StopSearch

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")
ROUTE_CACHE_DAYS = 7
SAVE_INTERVAL_SECONDS = 2.0
CANCELLED_REASON = "Cancelled by you."

_tasks: dict[int, asyncio.Task] = {}
_cancel_requested: set[int] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def log_provider_request(
    endpoint: str, status: int | None, latency_ms: int,
    route_search_id: int | None = None, session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    with session_factory() as db:
        db.add(ProviderRequestLog(
            endpoint=endpoint, status_code=status, latency_ms=latency_ms, route_search_id=route_search_id,
        ))
        db.commit()


def monthly_usage(db: Session) -> int:
    month_start = _utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(
        select(func.count()).select_from(ProviderRequestLog).where(ProviderRequestLog.created_at >= month_start)
    ) or 0


def active_search(db: Session, user_id: int) -> RouteSearch | None:
    return db.scalar(
        select(RouteSearch).where(RouteSearch.user_id == user_id, RouteSearch.status.in_(ACTIVE_STATUSES))
    )


def recover_interrupted(session_factory: Callable[[], Session] = SessionLocal) -> None:
    with session_factory() as db:
        db.execute(
            update(RouteSearch).where(RouteSearch.status.in_(ACTIVE_STATUSES)).values(
                status="failed", error="Interrupted by a server restart. Start the search again.", finished_at=_utcnow(),
            )
        )
        db.commit()


def start(search_id: int) -> None:
    task = asyncio.create_task(run_search(search_id))
    _tasks[search_id] = task
    task.add_done_callback(lambda _: _tasks.pop(search_id, None))


def request_cancel(search_id: int) -> None:
    _cancel_requested.add(search_id)


async def run_search(
    search_id: int,
    session_factory: Callable[[], Session] = SessionLocal,
    provider_factory: Callable[..., object] = RailKitProvider,
) -> None:
    with session_factory() as db:
        search = db.get(RouteSearch, search_id)
        if search is None:
            return
        search.status = "running"
        db.commit()

        last_save = 0.0

        def report(progress: dict, results: dict) -> None:
            nonlocal last_save
            if time.monotonic() - last_save < SAVE_INTERVAL_SECONDS:
                return
            last_save = time.monotonic()
            search.progress, search.results = progress, results
            db.commit()

        def should_stop() -> str | None:
            if search_id in _cancel_requested:
                return CANCELLED_REASON
            if monthly_usage(db) >= settings.railkit_monthly_quota - settings.railkit_monthly_reserve:
                return (
                    f"Stopped to keep the last {settings.railkit_monthly_reserve} RailKit requests "
                    "of this month's allowance free. These are the best routes found so far."
                )
            return None

        def load_route(train_no: str) -> dict | None:
            cached = db.get(TrainRouteCache, train_no)
            if cached is None:
                return None
            fetched_at = cached.fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            return cached.data if _utcnow() - fetched_at < timedelta(days=ROUTE_CACHE_DAYS) else None

        def save_route(train_no: str, payload: dict) -> None:
            db.merge(TrainRouteCache(train_no=train_no, data=payload, fetched_at=_utcnow()))
            db.commit()

        def on_request(endpoint: str, status: int | None, latency_ms: int) -> None:
            log_provider_request(endpoint, status, latency_ms, search_id, session_factory)

        finder = RouteFinder(
            provider_factory(on_request=on_request), search.from_code, search.to_code,
            search.journey_date, search.travel_class,
            load_route=load_route, save_route=save_route, report=report, should_stop=should_stop,
        )

        status, error, stop_reason = "completed", None, None
        try:
            await finder.run()
        except StopSearch as exc:
            stop_reason = str(exc)
            if stop_reason == CANCELLED_REASON:
                status = "cancelled"
        except RailKitError as exc:
            status, error = "failed", str(exc)
        except asyncio.CancelledError:
            search.status, search.error, search.finished_at = "failed", "Interrupted by a server restart.", _utcnow()
            db.commit()
            raise
        except Exception:
            logger.exception("Route search %s failed", search_id)
            status, error = "failed", "The route search failed unexpectedly."
        finally:
            _cancel_requested.discard(search_id)

        search.status, search.error, search.finished_at = status, error, _utcnow()
        search.progress = {**finder.progress(), "phase": "Done" if status == "completed" else status.capitalize(),
                           "stop_reason": stop_reason}
        search.results = finder.snapshot()
        db.commit()
