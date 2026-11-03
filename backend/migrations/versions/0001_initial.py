"""Initial schema: supplied accounts/activity_events plus the seed-import
operational record.

Translation of review-input/starter/schema.sql:
- TIMESTAMP columns (documented UTC) become timestamptz; the UTC
  interpretation is made explicitly during import (see app/reviews/seed.py).
- PK, FK, and required-field semantics are preserved. No additional domain
  constraints: source domains are profiled first (PLAN.md section 5).
- Composite index (account_id, event_type, occurred_at) for the single
  aggregation access path.

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=60), nullable=False),
        sa.Column("timezone", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=True),
    )
    op.create_index(
        "ix_activity_events_account_type_time",
        "activity_events",
        ["account_id", "event_type", "occurred_at"],
    )
    op.create_table(
        "seed_import",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("accounts_loaded", sa.Integer(), nullable=False),
        sa.Column("events_loaded", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("seed_import")
    op.drop_index("ix_activity_events_account_type_time", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_table("accounts")
