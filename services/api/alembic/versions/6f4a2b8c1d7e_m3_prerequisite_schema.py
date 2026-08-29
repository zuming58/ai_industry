"""M3 prerequisite adapter, audit and simulation schema."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f4a2b8c1d7e"
down_revision: Union[str, Sequence[str], None] = "3dd6709720e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "adapter_environments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("adapter_id", sa.String(length=80), nullable=False),
        sa.Column("adapter_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "adapter_id", "fingerprint", name="uq_adapter_environment_fingerprint"),
    )
    op.create_index("ix_adapter_environments_project_id", "adapter_environments", ["project_id"], unique=False)
    op.create_index("ix_adapter_environments_adapter_id", "adapter_environments", ["adapter_id"], unique=False)
    op.create_index("ix_adapter_environments_fingerprint", "adapter_environments", ["fingerprint"], unique=False)

    op.create_table(
        "generation_audits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("audit_version", sa.String(length=24), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("findings_json", sa.Text(), nullable=False),
        sa.Column("report_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_run_id", "audit_version", name="uq_generation_audit_version"),
    )
    op.create_index("ix_generation_audits_generation_run_id", "generation_audits", ["generation_run_id"], unique=False)
    op.create_index("ix_generation_audits_input_hash", "generation_audits", ["input_hash"], unique=False)

    op.create_table(
        "compile_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("adapter_id", sa.String(length=80), nullable=False),
        sa.Column("adapter_environment_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("diagnostics_json", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"]),
        sa.ForeignKeyConstraint(["adapter_environment_id"], ["adapter_environments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compile_runs_project_id", "compile_runs", ["project_id"], unique=False)
    op.create_index("ix_compile_runs_generation_run_id", "compile_runs", ["generation_run_id"], unique=False)
    op.create_index("ix_compile_runs_status", "compile_runs", ["status"], unique=False)

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("generation_run_id", sa.String(length=36), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=False),
        sa.Column("trace_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"]),
        sa.ForeignKeyConstraint(["trace_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulation_runs_project_id", "simulation_runs", ["project_id"], unique=False)
    op.create_index("ix_simulation_runs_generation_run_id", "simulation_runs", ["generation_run_id"], unique=False)
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"], unique=False)

    op.create_table(
        "evidence_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("compile_run_id", sa.String(length=36), nullable=True),
        sa.Column("simulation_run_id", sa.String(length=36), nullable=True),
        sa.Column("source_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_kind", sa.String(length=40), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compile_run_id"], ["compile_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_artifacts_project_id", "evidence_artifacts", ["project_id"], unique=False)
    op.create_index("ix_evidence_artifacts_compile_run_id", "evidence_artifacts", ["compile_run_id"], unique=False)
    op.create_index("ix_evidence_artifacts_simulation_run_id", "evidence_artifacts", ["simulation_run_id"], unique=False)

    op.create_table(
        "simulation_traces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("simulation_run_id", sa.String(length=36), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.String(length=160), nullable=True),
        sa.Column("inputs_json", sa.Text(), nullable=False),
        sa.Column("outputs_json", sa.Text(), nullable=False),
        sa.Column("events_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulation_traces_simulation_run_id", "simulation_traces", ["simulation_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_simulation_traces_simulation_run_id", table_name="simulation_traces")
    op.drop_table("simulation_traces")
    op.drop_index("ix_evidence_artifacts_simulation_run_id", table_name="evidence_artifacts")
    op.drop_index("ix_evidence_artifacts_compile_run_id", table_name="evidence_artifacts")
    op.drop_index("ix_evidence_artifacts_project_id", table_name="evidence_artifacts")
    op.drop_table("evidence_artifacts")
    op.drop_index("ix_simulation_runs_status", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_generation_run_id", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_project_id", table_name="simulation_runs")
    op.drop_table("simulation_runs")
    op.drop_index("ix_compile_runs_status", table_name="compile_runs")
    op.drop_index("ix_compile_runs_generation_run_id", table_name="compile_runs")
    op.drop_index("ix_compile_runs_project_id", table_name="compile_runs")
    op.drop_table("compile_runs")
    op.drop_index("ix_generation_audits_input_hash", table_name="generation_audits")
    op.drop_index("ix_generation_audits_generation_run_id", table_name="generation_audits")
    op.drop_table("generation_audits")
    op.drop_index("ix_adapter_environments_fingerprint", table_name="adapter_environments")
    op.drop_index("ix_adapter_environments_adapter_id", table_name="adapter_environments")
    op.drop_index("ix_adapter_environments_project_id", table_name="adapter_environments")
    op.drop_table("adapter_environments")
