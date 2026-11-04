from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RouteSearch(Base):
    """A background best-route search owned by one user."""

    __tablename__ = "route_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # queued | running | completed | cancelled | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    from_code: Mapped[str] = mapped_column(String(8), nullable=False)
    to_code: Mapped[str] = mapped_column(String(8), nullable=False)
    journey_date: Mapped[str] = mapped_column(String(10), nullable=False)  # DD-MM-YYYY
    travel_class: Mapped[str] = mapped_column(String(4), nullable=False)
    progress: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TrainRouteCache(Base):
    """Cached RailKit train info + stop list. Schedules change rarely."""

    __tablename__ = "train_route_cache"

    train_no: Mapped[str] = mapped_column(String(8), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ProviderRequestLog(Base):
    """One row per provider HTTP request: usage, latency and errors. No secrets or query values."""

    __tablename__ = "provider_request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="railkit")
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    route_search_id: Mapped[int | None] = mapped_column(
        ForeignKey("route_searches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
