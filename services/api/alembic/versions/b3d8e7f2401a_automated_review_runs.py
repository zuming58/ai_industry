"""Add immutable project-level automated review runs."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d8e7f2401a"
down_revision: Union[str, Sequence[str], None] = "98c7e5a31b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automated_review_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("program_commit_id", sa.String(length=36), nullable=False),
        sa.Column("review_version", sa.String(length=24), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False),
        sa.Column("checks_json", sa.Text(), nullable=False),
        sa.Column("external_gates_json", sa.Text(), nullable=False),
        sa.Column("claim_boundary", sa.Text(), nullable=False),
        sa.Column("report_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generation_run_id"], ["generation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["program_commit_id"], ["program_commits.id"]),
        sa.ForeignKeyConstraint(["report_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generation_run_id",
            "review_version",
            "input_hash",
            name="uq_automated_review_input",
        ),
    )
    op.create_index(
        "ix_automated_review_runs_project_id",
        "automated_review_runs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_automated_review_runs_generation_run_id",
        "automated_review_runs",
        ["generation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_automated_review_runs_program_commit_id",
        "automated_review_runs",
        ["program_commit_id"],
        unique=False,
    )
    op.create_index(
        "ix_automated_review_runs_input_hash",
        "automated_review_runs",
        ["input_hash"],
        unique=False,
    )
    op.create_index(
        "ix_automated_review_runs_status",
        "automated_review_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_automated_review_runs_status", table_name="automated_review_runs")
    op.drop_index("ix_automated_review_runs_input_hash", table_name="automated_review_runs")
    op.drop_index("ix_automated_review_runs_program_commit_id", table_name="automated_review_runs")
    op.drop_index("ix_automated_review_runs_generation_run_id", table_name="automated_review_runs")
    op.drop_index("ix_automated_review_runs_project_id", table_name="automated_review_runs")
    op.drop_table("automated_review_runs")
