"""Add local settings and settings audit tables."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e2b7c41a9d50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_app_settings_key", "app_settings", ["key"], unique=True)
    op.create_table(
        "settings_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_settings_audit_events_action", "settings_audit_events", ["action"], unique=False)
    op.create_index("ix_settings_audit_events_key", "settings_audit_events", ["key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_settings_audit_events_key", table_name="settings_audit_events")
    op.drop_index("ix_settings_audit_events_action", table_name="settings_audit_events")
    op.drop_table("settings_audit_events")
    op.drop_index("ix_app_settings_key", table_name="app_settings")
    op.drop_table("app_settings")
