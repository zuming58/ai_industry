"""Add immutable candidate verification and project acceptance reports."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2b7c41a9d50"
down_revision: Union[str, Sequence[str], None] = "d7a1c2e9304f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "release_candidate_verifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("release_candidate_id", sa.String(length=36), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("checks_json", sa.Text(), nullable=False),
        sa.Column("report_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["release_candidate_id"], ["release_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["report_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_candidate_id",
            "input_hash",
            name="uq_release_candidate_verification_input",
        ),
    )
    op.create_index(
        "ix_release_candidate_verifications_project_id",
        "release_candidate_verifications",
        ["project_id"],
    )
    op.create_index(
        "ix_release_candidate_verifications_release_candidate_id",
        "release_candidate_verifications",
        ["release_candidate_id"],
    )
    op.create_index(
        "ix_release_candidate_verifications_input_hash",
        "release_candidate_verifications",
        ["input_hash"],
    )
    op.create_index(
        "ix_release_candidate_verifications_status",
        "release_candidate_verifications",
        ["status"],
    )

    op.create_table(
        "project_acceptance_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("program_commit_id", sa.String(length=36), nullable=False),
        sa.Column("automated_review_id", sa.String(length=36), nullable=False),
        sa.Column("generation_audit_id", sa.String(length=36), nullable=False),
        sa.Column("simulation_run_id", sa.String(length=36), nullable=False),
        sa.Column("release_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_verification_id", sa.String(length=36), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("checks_json", sa.Text(), nullable=False),
        sa.Column("external_gates_json", sa.Text(), nullable=False),
        sa.Column("claim_boundary", sa.Text(), nullable=False),
        sa.Column("report_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"]),
        sa.ForeignKeyConstraint(["program_commit_id"], ["program_commits.id"]),
        sa.ForeignKeyConstraint(["automated_review_id"], ["automated_review_runs.id"]),
        sa.ForeignKeyConstraint(["generation_audit_id"], ["generation_audits.id"]),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"]),
        sa.ForeignKeyConstraint(["release_candidate_id"], ["release_candidates.id"]),
        sa.ForeignKeyConstraint(
            ["candidate_verification_id"], ["release_candidate_verifications.id"]
        ),
        sa.ForeignKeyConstraint(["report_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "input_hash", name="uq_project_acceptance_input"),
    )
    for column in (
        "project_id",
        "generation_run_id",
        "program_commit_id",
        "automated_review_id",
        "generation_audit_id",
        "simulation_run_id",
        "release_candidate_id",
        "candidate_verification_id",
        "input_hash",
        "status",
    ):
        op.create_index(
            f"ix_project_acceptance_runs_{column}",
            "project_acceptance_runs",
            [column],
        )


def downgrade() -> None:
    op.drop_table("project_acceptance_runs")
    op.drop_table("release_candidate_verifications")
