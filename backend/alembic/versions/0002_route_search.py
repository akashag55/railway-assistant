"""route searches, train route cache, provider request log

Revision ID: 0002_route_search
Revises: 0001_users
Create Date: 2026-11-04

Tables that already exist are skipped: a dev database may have them from the old
create_all at startup, with the same structure.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_route_search"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "route_searches" not in existing:
        _create_route_searches()
    if "train_route_cache" not in existing:
        _create_train_route_cache()
    if "provider_request_logs" not in existing:
        _create_provider_request_logs()


def _create_route_searches() -> None:
    op.create_table(
        "route_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("from_code", sa.String(8), nullable=False),
        sa.Column("to_code", sa.String(8), nullable=False),
        sa.Column("journey_date", sa.String(10), nullable=False),
        sa.Column("travel_class", sa.String(4), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_route_searches_user_id", "route_searches", ["user_id"])
    op.create_index("ix_route_searches_status", "route_searches", ["status"])


def _create_train_route_cache() -> None:
    op.create_table(
        "train_route_cache",
        sa.Column("train_no", sa.String(8), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_provider_request_logs() -> None:
    op.create_table(
        "provider_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("route_search_id", sa.Integer(), sa.ForeignKey("route_searches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_request_logs_route_search_id", "provider_request_logs", ["route_search_id"])
    op.create_index("ix_provider_request_logs_created_at", "provider_request_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("provider_request_logs")
    op.drop_table("train_route_cache")
    op.drop_table("route_searches")
