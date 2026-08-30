from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    customer_code: Mapped[str | None] = mapped_column(String(80))
    plc_brand: Mapped[str] = mapped_column(String(80), default="三菱电机")
    plc_series: Mapped[str] = mapped_column(String(80), default="MELSEC iQ-F")
    plc_model: Mapped[str] = mapped_column(String(120), default="FX5U-64MT/ES")
    status: Mapped[str] = mapped_column(String(40), default="资料准备")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_import_id: Mapped[str | None] = mapped_column(String(36))
    current_spec_revision_id: Mapped[str | None] = mapped_column(String(36))

    imports: Mapped[list[ImportVersion]] = relationship(back_populates="project", cascade="all, delete-orphan")


class TemplateVersion(Base, TimestampMixin):
    __tablename__ = "template_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version: Mapped[str] = mapped_column(String(24), unique=True)
    schema_version: Mapped[str] = mapped_column(String(24))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    definition_json: Mapped[str] = mapped_column(Text)


class AppSetting(Base, TimestampMixin):
    """Non-secret local application settings.

    Secrets are intentionally not represented by this model. Values are
    stored as a small JSON document so the API can evolve without exposing
    credentials in SQLite, logs, exports, or the timeline.
    """

    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value_json: Mapped[str] = mapped_column(Text, default="{}")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SettingsAuditEvent(Base):
    """Audit trail for global local-settings changes."""

    __tablename__ = "settings_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    action: Mapped[str] = mapped_column(String(80), index=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SourceArtifact(Base, TimestampMixin):
    __tablename__ = "source_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(120))
    original_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(512))


class ImportVersion(Base, TimestampMixin):
    __tablename__ = "import_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_project_import_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    source_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    current_revision_id: Mapped[str | None] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    project: Mapped[Project] = relationship(back_populates="imports")
    source_artifact: Mapped[SourceArtifact] = relationship()
    spec_revisions: Mapped[list[MachineSpecRevision]] = relationship(back_populates="import_version", cascade="all, delete-orphan")


class MachineSpecRevision(Base, TimestampMixin):
    __tablename__ = "machine_spec_revisions"
    __table_args__ = (UniqueConstraint("import_id", "sequence", name="uq_import_spec_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("import_versions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(24), default="1.0")
    data_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    import_version: Mapped[ImportVersion] = relationship(back_populates="spec_revisions")
    issues: Mapped[list[ValidationIssue]] = relationship(back_populates="spec_revision", cascade="all, delete-orphan")
    confirmations: Mapped[list[ReviewConfirmation]] = relationship(back_populates="spec_revision", cascade="all, delete-orphan")


class ValidationIssue(Base, TimestampMixin):
    __tablename__ = "validation_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    spec_revision_id: Mapped[str] = mapped_column(ForeignKey("machine_spec_revisions.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    sheet: Mapped[str | None] = mapped_column(String(80))
    row_number: Mapped[int | None] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(120))
    entity_id: Mapped[str | None] = mapped_column(String(160))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted_reason: Mapped[str | None] = mapped_column(Text)

    spec_revision: Mapped[MachineSpecRevision] = relationship(back_populates="issues")


class ReviewConfirmation(Base):
    __tablename__ = "review_confirmations"
    __table_args__ = (UniqueConstraint("spec_revision_id", "view", name="uq_spec_confirmation_view"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    spec_revision_id: Mapped[str] = mapped_column(ForeignKey("machine_spec_revisions.id", ondelete="CASCADE"), index=True)
    view: Mapped[str] = mapped_column(String(64))
    confirmed_by: Mapped[str] = mapped_column(String(120), default="本机工程师")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    spec_revision: Mapped[MachineSpecRevision] = relationship(back_populates="confirmations")


class LockedMachineSpec(Base):
    __tablename__ = "locked_machine_specs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    spec_revision_id: Mapped[str] = mapped_column(ForeignKey("machine_spec_revisions.id"), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))
    locked_by: Mapped[str] = mapped_column(String(120), default="本机工程师")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    snapshot_artifact: Mapped[SourceArtifact] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36))
    actor: Mapped[str] = mapped_column(String(120), default="本机工程师")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProgramWorkspace(Base, TimestampMixin):
    __tablename__ = "program_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True)
    repository_path: Mapped[str] = mapped_column(String(512))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ProgramBranch(Base, TimestampMixin):
    __tablename__ = "program_branches"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_workspace_branch_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("program_workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    git_ref: Mapped[str] = mapped_column(String(180))
    base_commit: Mapped[str | None] = mapped_column(String(64))
    head_commit: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="clean")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ControlIRRevision(Base, TimestampMixin):
    __tablename__ = "control_ir_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    spec_revision_id: Mapped[str] = mapped_column(ForeignKey("machine_spec_revisions.id"), index=True)
    generator_version: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    spec_revision_id: Mapped[str] = mapped_column(ForeignKey("machine_spec_revisions.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("program_branches.id"), index=True)
    control_ir_revision_id: Mapped[str | None] = mapped_column(ForeignKey("control_ir_revisions.id"))
    generator_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ProgramArtifact(Base, TimestampMixin):
    __tablename__ = "program_artifacts"
    __table_args__ = (UniqueConstraint("generation_run_id", "path", name="uq_generation_artifact_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))


class TestSpecRevision(Base, TimestampMixin):
    __tablename__ = "test_spec_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id", ondelete="CASCADE"), unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class TraceLink(Base):
    __tablename__ = "trace_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True)
    output_path: Mapped[str] = mapped_column(String(512))
    output_symbol: Mapped[str | None] = mapped_column(String(160))
    output_line: Mapped[int | None] = mapped_column(Integer)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(160))
    source_sheet: Mapped[str | None] = mapped_column(String(80))
    source_row: Mapped[int | None] = mapped_column(Integer)


class ProgramCommit(Base):
    __tablename__ = "program_commits"
    __table_args__ = (
        Index(
            "uq_program_commit_branch_sha",
            "branch_id",
            "git_sha",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(ForeignKey("program_branches.id", ondelete="CASCADE"), index=True)
    git_sha: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(240))
    author: Mapped[str] = mapped_column(String(120), default="本机工程师")
    machine_spec_revision_id: Mapped[str | None] = mapped_column(ForeignKey("machine_spec_revisions.id"))
    control_ir_revision_id: Mapped[str | None] = mapped_column(ForeignKey("control_ir_revisions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AdapterEnvironment(Base, TimestampMixin):
    __tablename__ = "adapter_environments"
    __table_args__ = (UniqueConstraint("project_id", "adapter_id", "fingerprint", name="uq_adapter_environment_fingerprint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    adapter_id: Mapped[str] = mapped_column(String(80), index=True)
    adapter_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="unavailable")
    verification_level: Mapped[str] = mapped_column(String(40), default="unverified")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class GenerationAudit(Base, TimestampMixin):
    __tablename__ = "generation_audits"
    __table_args__ = (UniqueConstraint("generation_run_id", "audit_version", name="uq_generation_audit_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True)
    program_commit_id: Mapped[str | None] = mapped_column(ForeignKey("program_commits.id"), index=True)
    audit_version: Mapped[str] = mapped_column(String(24), default="1")
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="review_ready")
    findings_json: Mapped[str] = mapped_column(Text, default="[]")
    report_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("source_artifacts.id"))


class AutomatedReviewRun(Base, TimestampMixin):
    __tablename__ = "automated_review_runs"
    __table_args__ = (
        UniqueConstraint(
            "generation_run_id",
            "review_version",
            "input_hash",
            name="uq_automated_review_input",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    generation_run_id: Mapped[str] = mapped_column(
        ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True
    )
    program_commit_id: Mapped[str] = mapped_column(
        ForeignKey("program_commits.id"), index=True
    )
    review_version: Mapped[str] = mapped_column(String(24))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="automatic")
    repeat_count: Mapped[int] = mapped_column(Integer, default=20)
    checks_json: Mapped[str] = mapped_column(Text, default="[]")
    external_gates_json: Mapped[str] = mapped_column(Text, default="[]")
    claim_boundary: Mapped[str] = mapped_column(Text)
    report_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))


class CompileRun(Base, TimestampMixin):
    __tablename__ = "compile_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id"), index=True)
    program_commit_id: Mapped[str | None] = mapped_column(ForeignKey("program_commits.id"), index=True)
    adapter_id: Mapped[str] = mapped_column(String(80), default="gxworks3")
    adapter_environment_id: Mapped[str | None] = mapped_column(ForeignKey("adapter_environments.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="unverified")
    diagnostics_json: Mapped[str] = mapped_column(Text, default="[]")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class EvidenceArtifact(Base, TimestampMixin):
    __tablename__ = "evidence_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    compile_run_id: Mapped[str | None] = mapped_column(ForeignKey("compile_runs.id", ondelete="CASCADE"), index=True)
    simulation_run_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    source_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))
    evidence_kind: Mapped[str] = mapped_column(String(40))
    verification_level: Mapped[str] = mapped_column(String(40), default="manual_unverified")


class SimulationRun(Base, TimestampMixin):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id"), index=True)
    program_commit_id: Mapped[str | None] = mapped_column(ForeignKey("program_commits.id"), index=True)
    test_spec_revision_id: Mapped[str | None] = mapped_column(ForeignKey("test_spec_revisions.id"), index=True)
    engine_version: Mapped[str] = mapped_column(String(32), default="kongpu-reference-v1")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="automatic_reference")
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    trace_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("source_artifacts.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SimulationTrace(Base):
    __tablename__ = "simulation_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    simulation_run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    step_id: Mapped[str | None] = mapped_column(String(160))
    inputs_json: Mapped[str] = mapped_column(Text, default="{}")
    outputs_json: Mapped[str] = mapped_column(Text, default="{}")
    events_json: Mapped[str] = mapped_column(Text, default="[]")


class ReleaseCandidate(Base, TimestampMixin):
    __tablename__ = "release_candidates"
    __table_args__ = (
        UniqueConstraint("project_id", "input_hash", name="uq_release_candidate_input"),
        UniqueConstraint("project_id", "version", name="uq_release_candidate_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id"), index=True)
    program_commit_id: Mapped[str] = mapped_column(ForeignKey("program_commits.id"), index=True)
    automated_review_id: Mapped[str] = mapped_column(ForeignKey("automated_review_runs.id"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    manifest_hash: Mapped[str] = mapped_column(String(64), index=True)
    manifest_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="external_validation_required", index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="automatic_package")
    package_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ReleaseCandidateVerification(Base, TimestampMixin):
    __tablename__ = "release_candidate_verifications"
    __table_args__ = (
        UniqueConstraint(
            "release_candidate_id",
            "input_hash",
            name="uq_release_candidate_verification_input",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    release_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("release_candidates.id", ondelete="CASCADE"), index=True
    )
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    verification_level: Mapped[str] = mapped_column(
        String(40), default="automatic_integrity"
    )
    checks_json: Mapped[str] = mapped_column(Text, default="[]")
    report_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("source_artifacts.id")
    )


class ProjectAcceptanceRun(Base, TimestampMixin):
    __tablename__ = "project_acceptance_runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "input_hash", name="uq_project_acceptance_input"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    generation_run_id: Mapped[str] = mapped_column(
        ForeignKey("generation_runs.id"), index=True
    )
    program_commit_id: Mapped[str] = mapped_column(
        ForeignKey("program_commits.id"), index=True
    )
    automated_review_id: Mapped[str] = mapped_column(
        ForeignKey("automated_review_runs.id"), index=True
    )
    generation_audit_id: Mapped[str] = mapped_column(
        ForeignKey("generation_audits.id"), index=True
    )
    simulation_run_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.id"), index=True
    )
    release_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("release_candidates.id"), index=True
    )
    candidate_verification_id: Mapped[str | None] = mapped_column(
        ForeignKey("release_candidate_verifications.id"), index=True
    )
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(48), index=True)
    verification_level: Mapped[str] = mapped_column(
        String(40), default="automatic"
    )
    checks_json: Mapped[str] = mapped_column(Text, default="[]")
    external_gates_json: Mapped[str] = mapped_column(Text, default="[]")
    claim_boundary: Mapped[str] = mapped_column(Text)
    report_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("source_artifacts.id")
    )


class MonitoringPlan(Base, TimestampMixin):
    __tablename__ = "monitoring_plans"
    __table_args__ = (UniqueConstraint("release_candidate_id", name="uq_monitoring_plan_candidate"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    release_candidate_id: Mapped[str] = mapped_column(ForeignKey("release_candidates.id"), index=True)
    target_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    variable_map_hash: Mapped[str] = mapped_column(String(64), index=True)
    variable_map_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), default="awaiting_external_read_only_connection", index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="unverified")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class MonitoringEvidence(Base, TimestampMixin):
    __tablename__ = "monitoring_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    monitoring_plan_id: Mapped[str] = mapped_column(ForeignKey("monitoring_plans.id", ondelete="CASCADE"), index=True)
    source_artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"))
    status: Mapped[str] = mapped_column(String(40), default="recorded_unverified", index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="manual_unverified")
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    note: Mapped[str | None] = mapped_column(Text)


class CommissioningTask(Base, TimestampMixin):
    __tablename__ = "commissioning_tasks"
    __table_args__ = (UniqueConstraint("monitoring_evidence_id", name="uq_commissioning_task_evidence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    monitoring_evidence_id: Mapped[str] = mapped_column(ForeignKey("monitoring_evidence.id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("program_branches.id"), index=True)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
