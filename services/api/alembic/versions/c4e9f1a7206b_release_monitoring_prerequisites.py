"""Add release candidate and read-only monitoring prerequisite models."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e9f1a7206b"
down_revision: Union[str, Sequence[str], None] = "b3d8e7f2401a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "release_candidates",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("generation_run_id", sa.String(36), nullable=False),
        sa.Column("program_commit_id", sa.String(36), nullable=False),
        sa.Column("automated_review_id", sa.String(36), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("verification_level", sa.String(40), nullable=False),
        sa.Column("package_artifact_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"]),
        sa.ForeignKeyConstraint(["program_commit_id"], ["program_commits.id"]),
        sa.ForeignKeyConstraint(["automated_review_id"], ["automated_review_runs.id"]),
        sa.ForeignKeyConstraint(["package_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "input_hash", name="uq_release_candidate_input"),
        sa.UniqueConstraint("project_id", "version", name="uq_release_candidate_version"),
    )
    for name, columns in (
        ("ix_release_candidates_project_id", ["project_id"]),
        ("ix_release_candidates_generation_run_id", ["generation_run_id"]),
        ("ix_release_candidates_program_commit_id", ["program_commit_id"]),
        ("ix_release_candidates_automated_review_id", ["automated_review_id"]),
        ("ix_release_candidates_input_hash", ["input_hash"]),
        ("ix_release_candidates_manifest_hash", ["manifest_hash"]),
        ("ix_release_candidates_status", ["status"]),
    ):
        op.create_index(name, "release_candidates", columns, unique=False)

    op.create_table(
        "monitoring_plans",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("release_candidate_id", sa.String(36), nullable=False),
        sa.Column("target_fingerprint", sa.String(64), nullable=False),
        sa.Column("variable_map_hash", sa.String(64), nullable=False),
        sa.Column("variable_map_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(48), nullable=False),
        sa.Column("verification_level", sa.String(40), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_candidate_id"], ["release_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_candidate_id", name="uq_monitoring_plan_candidate"),
    )
    for name, columns in (
        ("ix_monitoring_plans_project_id", ["project_id"]),
        ("ix_monitoring_plans_release_candidate_id", ["release_candidate_id"]),
        ("ix_monitoring_plans_target_fingerprint", ["target_fingerprint"]),
        ("ix_monitoring_plans_variable_map_hash", ["variable_map_hash"]),
        ("ix_monitoring_plans_status", ["status"]),
    ):
        op.create_index(name, "monitoring_plans", columns, unique=False)

    op.create_table(
        "monitoring_evidence",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("monitoring_plan_id", sa.String(36), nullable=False),
        sa.Column("source_artifact_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("verification_level", sa.String(40), nullable=False),
        sa.Column("analysis_json", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitoring_plan_id"], ["monitoring_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_monitoring_evidence_project_id", ["project_id"]),
        ("ix_monitoring_evidence_monitoring_plan_id", ["monitoring_plan_id"]),
        ("ix_monitoring_evidence_status", ["status"]),
    ):
        op.create_index(name, "monitoring_evidence", columns, unique=False)

    op.create_table(
        "commissioning_tasks",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("monitoring_evidence_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("generation_run_id", sa.String(36), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitoring_evidence_id"], ["monitoring_evidence.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["program_branches.id"]),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("monitoring_evidence_id", name="uq_commissioning_task_evidence"),
    )
    for name, columns in (
        ("ix_commissioning_tasks_project_id", ["project_id"]),
        ("ix_commissioning_tasks_monitoring_evidence_id", ["monitoring_evidence_id"]),
        ("ix_commissioning_tasks_branch_id", ["branch_id"]),
        ("ix_commissioning_tasks_generation_run_id", ["generation_run_id"]),
        ("ix_commissioning_tasks_status", ["status"]),
    ):
        op.create_index(name, "commissioning_tasks", columns, unique=False)


def downgrade() -> None:
    for table, indexes in (
        ("commissioning_tasks", ["ix_commissioning_tasks_status", "ix_commissioning_tasks_generation_run_id", "ix_commissioning_tasks_branch_id", "ix_commissioning_tasks_monitoring_evidence_id", "ix_commissioning_tasks_project_id"]),
        ("monitoring_evidence", ["ix_monitoring_evidence_status", "ix_monitoring_evidence_monitoring_plan_id", "ix_monitoring_evidence_project_id"]),
        ("monitoring_plans", ["ix_monitoring_plans_status", "ix_monitoring_plans_variable_map_hash", "ix_monitoring_plans_target_fingerprint", "ix_monitoring_plans_release_candidate_id", "ix_monitoring_plans_project_id"]),
        ("release_candidates", ["ix_release_candidates_status", "ix_release_candidates_manifest_hash", "ix_release_candidates_input_hash", "ix_release_candidates_automated_review_id", "ix_release_candidates_program_commit_id", "ix_release_candidates_generation_run_id", "ix_release_candidates_project_id"]),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
