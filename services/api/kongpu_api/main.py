from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .artifacts import artifact_path, store_bytes
from .adapters import descriptor, descriptors, detect as detect_adapter
from .audit import audit_bundle
from .automated_review import (
    AUTOMATED_REVIEW_VERSION, EXTERNAL_VALIDATION_GATES, run_automated_review,
)
from .config import Settings, get_settings
from .database import DatabaseRuntime
from .delivery import (
    DeliveryInputError, build_delivery_candidate, entry_index, sha256_bytes,
    stable_json_bytes, verify_delivery_candidate,
)
from .generator import GeneratedBundle, GENERATOR_VERSION, content_hash, generate_bundle, stable_json
from .machine_spec import (
    MachineSpec, WorkbookInputError, generate_workbook, parse_workbook, patch_cells,
    required_review_views, sheet_payload, spec_hash, validate_spec,
)
from .simulation import SimulationInputError, run_test_spec
from .monitoring import (
    MonitoringInputError, analyze_snapshot, build_variable_map,
    target_fingerprint, variable_map_hash,
)
from .models import (
    AdapterEnvironment, AuditEvent, AutomatedReviewRun, CompileRun,
    CommissioningTask, ControlIRRevision, EvidenceArtifact,
    GenerationAudit, GenerationRun, ImportVersion, LockedMachineSpec,
    MachineSpecRevision, MonitoringEvidence, MonitoringPlan,
    ProgramArtifact, ProgramBranch, ProgramCommit,
    ProgramWorkspace, Project, ReviewConfirmation, SourceArtifact,
    ReleaseCandidate, SimulationRun, SimulationTrace,
    TemplateVersion, TestSpecRevision, TraceLink,
    ValidationIssue, new_id,
)
from .repository import (
    RepositoryError, checkout_branch, commit_all, commit_diff, ensure_repository,
    is_working_tree_clean, list_files, list_files_at_commit, parent_of, read_file,
    read_file_at_commit, repository_path, validate_branch_name, write_files,
)
from .schemas import (
    AdapterDetectRequest, AutomatedReviewRequest, BranchCreateRequest,
    CellPatchRequest, CompileRunRequest,
    CommissioningTaskRequest, ConfirmationRequest, GenerationRequest,
    MonitoringPlanRequest, MonitoringSnapshotRequest, ReleaseCandidateRequest,
    SimulationRunRequest,
    ProgramCommitRequest, ProgramFilePatch, ProjectCreate, ProjectPatch,
    WarningAcceptRequest,
)


router = APIRouter()


def app_settings(request: Request) -> Settings:
    return request.app.state.settings


def app_session(request: Request):
    yield from request.app.state.database.sessions()


def create_app(
    settings_override: Settings | None = None,
    database_override: DatabaseRuntime | None = None,
) -> FastAPI:
    runtime_settings = settings_override or get_settings()
    database = database_override or DatabaseRuntime(runtime_settings)

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        if database_override is None:
            database.upgrade_schema()
        else:
            database.create_schema()
        with database.session_factory() as session:
            seed_template_version(session)
        yield
        if database_override is not None:
            database.dispose()

    application = FastAPI(title="控谱本地 API", version="0.2.0", lifespan=lifespan)
    application.state.settings = runtime_settings
    application.state.database = database
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": detail.get("code", "HTTP_ERROR"),
                "message": detail.get("message", "请求失败"),
                "location": detail.get("location"),
                "action": detail.get("action"),
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "REQUEST_VALIDATION_FAILED",
                "message": "请求参数不符合接口约束",
                "location": exc.errors(),
                "action": "检查输入后重试",
            },
        )

    application.include_router(router)
    return application


def api_error(code: str, message: str, status_code: int = 400, *, action: str | None = None) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, "action": action})


def seed_template_version(session: Session) -> None:
    current = session.scalar(select(TemplateVersion).where(TemplateVersion.version == "1.0"))
    if current is None:
        definition = {"required_sheets": ["Instructions", "Project", "Components", "Signals", "Sequence"], "optional_sheets": ["Interlocks", "Exceptions"]}
        session.add(TemplateVersion(version="1.0", schema_version="1.0", definition_json=json.dumps(definition, ensure_ascii=False)))
        session.commit()


def project_dict(project: Project) -> dict[str, Any]:
    return {
        "id": project.id, "code": project.code, "name": project.name,
        "customer_code": project.customer_code, "plc_brand": project.plc_brand,
        "plc_series": project.plc_series, "plc_model": project.plc_model,
        "status": project.status, "archived": project.archived,
        "is_demo": project.is_demo, "revision": project.revision,
        "current_import_id": project.current_import_id,
        "current_spec_revision_id": project.current_spec_revision_id,
        "created_at": project.created_at.isoformat(), "updated_at": project.updated_at.isoformat(),
    }


def require_project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise api_error("PROJECT_NOT_FOUND", "项目不存在", 404, action="返回项目列表")
    return project


def require_spec(session: Session, revision_id: str) -> MachineSpecRevision:
    revision = session.get(MachineSpecRevision, revision_id)
    if revision is None:
        raise api_error("SPEC_REVISION_NOT_FOUND", "MachineSpec 版本不存在", 404)
    return revision


def require_workspace(session: Session, workspace_id: str) -> ProgramWorkspace:
    workspace = session.get(ProgramWorkspace, workspace_id)
    if workspace is None:
        raise api_error("WORKSPACE_NOT_FOUND", "程序工作区不存在", 404)
    return workspace


def require_branch(session: Session, branch_id: str) -> ProgramBranch:
    branch = session.get(ProgramBranch, branch_id)
    if branch is None:
        raise api_error("BRANCH_NOT_FOUND", "程序分支不存在", 404)
    return branch


def workspace_for_project(
    session: Session,
    settings: Settings,
    project_id: str,
) -> tuple[ProgramWorkspace, Any]:
    workspace = session.scalar(
        select(ProgramWorkspace).where(ProgramWorkspace.project_id == project_id)
    )
    repo = ensure_repository(settings, project_id)
    if workspace is None:
        workspace = ProgramWorkspace(
            project_id=project_id,
            repository_path=str(repository_path(settings, project_id)),
        )
        session.add(workspace)
        session.flush()
    return workspace, repo


def branch_dict(branch: ProgramBranch) -> dict[str, Any]:
    return {
        "id": branch.id,
        "workspace_id": branch.workspace_id,
        "name": branch.name,
        "git_ref": branch.git_ref,
        "base_commit": branch.base_commit,
        "head_commit": branch.head_commit,
        "status": branch.status,
        "revision": branch.revision,
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
    }


def commit_dict(commit: ProgramCommit) -> dict[str, Any]:
    return {
        "id": commit.id,
        "branch_id": commit.branch_id,
        "git_sha": commit.git_sha,
        "message": commit.message,
        "author": commit.author,
        "machine_spec_revision_id": commit.machine_spec_revision_id,
        "control_ir_revision_id": commit.control_ir_revision_id,
        "created_at": commit.created_at.isoformat(),
    }


def generation_dict(session: Session, run: GenerationRun) -> dict[str, Any]:
    artifacts = session.scalars(
        select(ProgramArtifact)
        .where(ProgramArtifact.generation_run_id == run.id)
        .order_by(ProgramArtifact.path)
    ).all()
    traces = session.scalars(
        select(TraceLink)
        .where(TraceLink.generation_run_id == run.id)
        .order_by(TraceLink.output_path, TraceLink.output_line)
    ).all()
    return {
        "id": run.id,
        "project_id": run.project_id,
        "spec_revision_id": run.spec_revision_id,
        "branch_id": run.branch_id,
        "control_ir_revision_id": run.control_ir_revision_id,
        "generator_version": run.generator_version,
        "status": run.status,
        "warnings": json.loads(run.warnings_json),
        "failure_reason": run.failure_reason,
        "revision": run.revision,
        "artifacts": [
            {
                "id": item.id,
                "path": item.path,
                "kind": item.kind,
                "content_hash": item.content_hash,
                "source_artifact_id": item.source_artifact_id,
            }
            for item in artifacts
        ],
        "trace_links": [
            {
                "output_path": item.output_path,
                "output_symbol": item.output_symbol,
                "output_line": item.output_line,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "source_sheet": item.source_sheet,
                "source_row": item.source_row,
            }
            for item in traces
        ],
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def adapter_environment_dict(item: AdapterEnvironment) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "adapter_id": item.adapter_id,
        "adapter_version": item.adapter_version,
        "status": item.status,
        "verification_level": item.verification_level,
        "fingerprint": item.fingerprint,
        "details": json.loads(item.details_json),
        "revision": item.revision,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def audit_dict(item: GenerationAudit) -> dict[str, Any]:
    findings = json.loads(item.findings_json)
    return {
        "id": item.id,
        "generation_run_id": item.generation_run_id,
        "program_commit_id": item.program_commit_id,
        "baseline_scope": "current_program_commit",
        "audit_version": item.audit_version,
        "input_hash": item.input_hash,
        "status": item.status,
        "findings": findings,
        "summary": {
            "total": len(findings),
            "blocker": sum(value.get("severity") == "blocker" for value in findings),
            "warning": sum(value.get("severity") == "warning" for value in findings),
        },
        "report_artifact_id": item.report_artifact_id,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def automated_review_dict(session: Session, item: AutomatedReviewRun) -> dict[str, Any]:
    checks = json.loads(item.checks_json)
    gates = json.loads(item.external_gates_json)
    report_artifact = session.get(SourceArtifact, item.report_artifact_id)
    return {
        "id": item.id,
        "project_id": item.project_id,
        "generation_run_id": item.generation_run_id,
        "program_commit_id": item.program_commit_id,
        "review_version": item.review_version,
        "input_hash": item.input_hash,
        "status": item.status,
        "verification_level": item.verification_level,
        "repeat_count": item.repeat_count,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": sum(value.get("status") == "passed" for value in checks),
            "failed": sum(value.get("status") == "failed" for value in checks),
            "external_pending": len(gates),
        },
        "external_validation_gates": gates,
        "claim_boundary": item.claim_boundary,
        "report_artifact_id": item.report_artifact_id,
        "report_sha256": report_artifact.sha256 if report_artifact else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def compile_dict(session: Session, item: CompileRun) -> dict[str, Any]:
    evidence_count = session.scalar(
        select(func.count()).select_from(EvidenceArtifact).where(EvidenceArtifact.compile_run_id == item.id)
    ) or 0
    return {
        "id": item.id,
        "project_id": item.project_id,
        "generation_run_id": item.generation_run_id,
        "program_commit_id": item.program_commit_id,
        "adapter_id": item.adapter_id,
        "adapter_environment_id": item.adapter_environment_id,
        "status": item.status,
        "verification_level": item.verification_level,
        "diagnostics": json.loads(item.diagnostics_json),
        "failure_reason": item.failure_reason,
        "revision": item.revision,
        "evidence_count": evidence_count,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def simulation_dict(session: Session, item: SimulationRun) -> dict[str, Any]:
    traces = session.scalars(select(SimulationTrace).where(SimulationTrace.simulation_run_id == item.id).order_by(SimulationTrace.cycle)).all()
    result = json.loads(item.results_json)
    return {
        "id": item.id,
        "project_id": item.project_id,
        "generation_run_id": item.generation_run_id,
        "program_commit_id": item.program_commit_id,
        "test_spec_revision_id": item.test_spec_revision_id,
        "engine_version": item.engine_version,
        "status": item.status,
        "verification_level": item.verification_level,
        "results": result,
        "trace_artifact_id": item.trace_artifact_id,
        "revision": item.revision,
        "trace_count": len(traces),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def release_candidate_dict(session: Session, item: ReleaseCandidate) -> dict[str, Any]:
    package = session.get(SourceArtifact, item.package_artifact_id)
    return {
        "id": item.id,
        "project_id": item.project_id,
        "generation_run_id": item.generation_run_id,
        "program_commit_id": item.program_commit_id,
        "automated_review_id": item.automated_review_id,
        "version": item.version,
        "input_hash": item.input_hash,
        "manifest_hash": item.manifest_hash,
        "manifest": json.loads(item.manifest_json),
        "status": item.status,
        "verification_level": item.verification_level,
        "package_artifact_id": item.package_artifact_id,
        "package_sha256": package.sha256 if package else None,
        "package_size_bytes": package.size_bytes if package else None,
        "revision": item.revision,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def monitoring_plan_dict(session: Session, item: MonitoringPlan) -> dict[str, Any]:
    evidence_count = session.scalar(
        select(func.count()).select_from(MonitoringEvidence).where(
            MonitoringEvidence.monitoring_plan_id == item.id
        )
    ) or 0
    return {
        "id": item.id,
        "project_id": item.project_id,
        "release_candidate_id": item.release_candidate_id,
        "target_fingerprint": item.target_fingerprint,
        "variable_map_hash": item.variable_map_hash,
        "variable_map": json.loads(item.variable_map_json),
        "status": item.status,
        "verification_level": item.verification_level,
        "access": "read_only",
        "evidence_count": evidence_count,
        "revision": item.revision,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def monitoring_evidence_dict(session: Session, item: MonitoringEvidence) -> dict[str, Any]:
    artifact = session.get(SourceArtifact, item.source_artifact_id)
    task = session.scalar(
        select(CommissioningTask).where(
            CommissioningTask.monitoring_evidence_id == item.id
        )
    )
    return {
        "id": item.id,
        "project_id": item.project_id,
        "monitoring_plan_id": item.monitoring_plan_id,
        "source_artifact_id": item.source_artifact_id,
        "artifact_sha256": artifact.sha256 if artifact else None,
        "status": item.status,
        "verification_level": item.verification_level,
        "analysis": json.loads(item.analysis_json),
        "note": item.note,
        "commissioning_task_id": task.id if task else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def commissioning_task_dict(item: CommissioningTask) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "monitoring_evidence_id": item.monitoring_evidence_id,
        "branch_id": item.branch_id,
        "generation_run_id": item.generation_run_id,
        "description": item.description,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def check_expected_revision(current: int, expected: int | None, etag: str | None = None) -> None:
    requested = expected
    if etag:
        token = etag.strip('\"')
        if token.isdigit():
            requested = int(token)
    if requested is not None and requested != current:
        raise api_error("REVISION_CONFLICT", f"数据已更新，当前版本为 {current}", 409, action="刷新后重新操作")


def read_artifact_bytes(
    session: Session, settings: Settings, artifact_id: str
) -> tuple[SourceArtifact, bytes]:
    record = session.get(SourceArtifact, artifact_id)
    if record is None:
        raise api_error("ARTIFACT_NOT_FOUND", "文件工件不存在", 404)
    try:
        path = artifact_path(settings, record)
    except ValueError:
        raise api_error("ARTIFACT_PATH_INVALID", "文件工件路径无效", 500)
    if not path.is_file():
        raise api_error("ARTIFACT_MISSING", "文件工件已丢失", 410)
    content = path.read_bytes()
    if sha256_bytes(content) != record.sha256:
        raise api_error(
            "ARTIFACT_HASH_MISMATCH",
            "文件工件哈希不匹配",
            409,
            action="停止使用该工件并检查本机数据目录",
        )
    return record, content


def generation_baseline(
    session: Session,
    settings: Settings,
    run: GenerationRun,
) -> tuple[dict[str, Any], GeneratedBundle, ProgramCommit, TestSpecRevision]:
    if not run.control_ir_revision_id or not run.branch_id:
        raise api_error("GENERATION_BASELINE_INCOMPLETE", "生成任务缺少不可变 Control IR 或分支基线", 409)
    control_ir = session.get(ControlIRRevision, run.control_ir_revision_id)
    test_spec = session.scalar(select(TestSpecRevision).where(TestSpecRevision.generation_run_id == run.id))
    branch = session.get(ProgramBranch, run.branch_id)
    if branch is None or not branch.head_commit:
        raise api_error("GENERATION_BASELINE_INCOMPLETE", "生成分支缺少当前 Commit", 409)
    commit = session.scalar(
        select(ProgramCommit).where(
            ProgramCommit.branch_id == branch.id,
            ProgramCommit.git_sha == branch.head_commit,
        )
    )
    if control_ir is None or test_spec is None or commit is None:
        raise api_error("GENERATION_BASELINE_INCOMPLETE", "生成任务缺少不可变工件、TestSpec 或 Commit", 409)
    if content_hash(control_ir.data_json) != control_ir.content_hash or content_hash(test_spec.data_json) != test_spec.content_hash:
        raise api_error("GENERATION_BASELINE_HASH_MISMATCH", "Control IR 或 TestSpec 基线哈希不匹配", 409, action="停止使用该基线并检查本机数据库")
    if (
        commit.machine_spec_revision_id != run.spec_revision_id
        or commit.control_ir_revision_id != run.control_ir_revision_id
    ):
        raise api_error(
            "PROGRAM_COMMIT_BASELINE_MISMATCH",
            "当前 Commit 未绑定到该生成任务的锁定规格和 Control IR",
            409,
            action="从当前生成分支创建带完整基线的新 Commit",
        )
    immutable_files: dict[str, str] = {}
    artifacts = session.scalars(
        select(ProgramArtifact).where(ProgramArtifact.generation_run_id == run.id).order_by(ProgramArtifact.path)
    ).all()
    for item in artifacts:
        source = session.get(SourceArtifact, item.source_artifact_id)
        if source is None:
            raise api_error("GENERATION_ARTIFACT_MISSING", f"生成工件 {item.path} 的元数据不存在", 410)
        path = artifact_path(settings, source)
        if not path.is_file():
            raise api_error("GENERATION_ARTIFACT_MISSING", f"生成工件 {item.path} 已丢失", 410)
        try:
            text_value = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise api_error("GENERATION_ARTIFACT_INVALID", f"生成工件 {item.path} 不是 UTF-8 文本", 422)
        if content_hash(text_value) != item.content_hash:
            raise api_error("GENERATION_ARTIFACT_HASH_MISMATCH", f"生成工件 {item.path} 哈希不匹配", 409, action="停止使用该基线并检查本机工件库")
        immutable_files[item.path] = text_value
    spec_revision = require_spec(session, run.spec_revision_id)
    locked = session.scalar(select(LockedMachineSpec).where(LockedMachineSpec.spec_revision_id == spec_revision.id))
    if locked is None or locked.content_hash != spec_revision.content_hash:
        raise api_error("LOCKED_SPEC_HASH_MISMATCH", "锁定 MachineSpec 基线不完整或哈希不匹配", 409)
    try:
        if stable_json(json.loads(immutable_files["generated/ControlIR.json"])) != control_ir.data_json:
            raise api_error("CONTROL_IR_ARTIFACT_MISMATCH", "Control IR 工件与数据库基线不一致", 409)
        if stable_json(json.loads(immutable_files["tests/TestSpec.json"])) != test_spec.data_json:
            raise api_error("TEST_SPEC_ARTIFACT_MISMATCH", "TestSpec 工件与数据库基线不一致", 409)
    except KeyError:
        raise api_error("GENERATION_BASELINE_INCOMPLETE", "生成任务缺少 Control IR 或 TestSpec 工件", 409)
    except json.JSONDecodeError:
        raise api_error("GENERATION_ARTIFACT_INVALID", "Control IR 或 TestSpec 工件不是有效 JSON", 422)
    try:
        repo = ensure_repository(settings, run.project_id)
        files = {
            path: read_file_at_commit(repo, commit.git_sha, path)
            for path in list_files_at_commit(repo, commit.git_sha)
        }
    except (RepositoryError, UnicodeDecodeError) as exc:
        raise api_error(
            "PROGRAM_COMMIT_READ_FAILED",
            f"无法读取当前 Commit 的源码树: {exc}",
            409,
            action="检查本地 Git 仓库完整性",
        )
    try:
        if stable_json(json.loads(files["generated/ControlIR.json"])) != control_ir.data_json:
            raise api_error("CONTROL_IR_COMMIT_MISMATCH", "当前 Commit 修改了不可变 Control IR", 409)
        if stable_json(json.loads(files["tests/TestSpec.json"])) != test_spec.data_json:
            raise api_error("TEST_SPEC_COMMIT_MISMATCH", "当前 Commit 修改了不可变 TestSpec", 409)
    except KeyError:
        raise api_error("PROGRAM_COMMIT_BASELINE_INCOMPLETE", "当前 Commit 缺少 Control IR 或 TestSpec", 409)
    except json.JSONDecodeError:
        raise api_error("PROGRAM_COMMIT_BASELINE_INVALID", "当前 Commit 的 Control IR 或 TestSpec 不是有效 JSON", 422)
    traces = session.scalars(select(TraceLink).where(TraceLink.generation_run_id == run.id)).all()
    bundle = GeneratedBundle(
        control_ir=json.loads(control_ir.data_json),
        files=files,
        test_spec=json.loads(test_spec.data_json),
        trace_links=[{
            "output_path": item.output_path, "output_symbol": item.output_symbol,
            "output_line": item.output_line, "entity_type": item.entity_type,
            "entity_id": item.entity_id, "source_sheet": item.source_sheet,
            "source_row": item.source_row,
        } for item in traces],
        warnings=json.loads(run.warnings_json),
    )
    return json.loads(spec_revision.data_json), bundle, commit, test_spec


def require_current_automated_review(
    session: Session, run: GenerationRun, commit: ProgramCommit
) -> AutomatedReviewRun:
    review = session.scalar(
        select(AutomatedReviewRun)
        .where(
            AutomatedReviewRun.generation_run_id == run.id,
            AutomatedReviewRun.program_commit_id == commit.id,
        )
        .order_by(AutomatedReviewRun.created_at.desc())
    )
    if review is None:
        raise api_error(
            "AUTOMATED_REVIEW_REQUIRED",
            "当前 Commit 尚未完成项目自动审核",
            409,
            action="基于当前 Commit 重新运行项目自动审核",
        )
    if review.status != "passed":
        raise api_error(
            "AUTOMATED_REVIEW_BLOCKED",
            "当前 Commit 的项目自动审核存在 blocker",
            409,
            action="保留当前 Commit 和报告，修复后创建新 Commit",
        )
    return review


def persist_generation_audit(
    session: Session, settings: Settings, run: GenerationRun
) -> tuple[GenerationAudit, bool]:
    spec_data, bundle, commit, _test_spec = generation_baseline(
        session, settings, run
    )
    report = audit_bundle(spec_data, bundle)
    report["baseline"] = {
        "program_commit_id": commit.id,
        "git_sha": commit.git_sha,
    }
    audit_version = f"{report['audit_version']}:{commit.git_sha[:12]}"
    report["audit_version"] = audit_version
    existing = session.scalar(
        select(GenerationAudit).where(
            GenerationAudit.generation_run_id == run.id,
            GenerationAudit.audit_version == audit_version,
        )
    )
    if existing is not None:
        if (
            existing.input_hash == report["input_hash"]
            and existing.program_commit_id == commit.id
        ):
            return existing, True
        raise api_error(
            "AUDIT_BASELINE_CONFLICT",
            "同一不可变 Commit 的审计输入发生冲突",
            409,
            action="检查工件库和审计记录",
        )
    report_bytes = json.dumps(
        report, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    artifact = store_bytes(
        session,
        settings,
        report_bytes,
        f"generation-audit-{run.id}-{commit.git_sha[:12]}.json",
        "application/json",
    )
    item = GenerationAudit(
        generation_run_id=run.id,
        audit_version=audit_version,
        input_hash=report["input_hash"],
        status=report["status"],
        findings_json=json.dumps(
            report["findings"], ensure_ascii=False, sort_keys=True
        ),
        report_artifact_id=artifact.record.id,
        program_commit_id=commit.id,
    )
    session.add(item)
    session.flush()
    audit(
        session,
        run.project_id,
        "program.audit_completed",
        "GenerationAudit",
        item.id,
        {"status": report["status"], "input_hash": report["input_hash"]},
    )
    return item, False


def persist_automated_review(
    session: Session,
    settings: Settings,
    run: GenerationRun,
    *,
    repeat_count: int,
) -> tuple[AutomatedReviewRun, bool]:
    spec_data, bundle, baseline_commit, _test_spec = generation_baseline(
        session, settings, run
    )
    try:
        report = run_automated_review(
            spec_data,
            bundle,
            run_generator_version=run.generator_version,
            program_commit_id=baseline_commit.id,
            program_git_sha=baseline_commit.git_sha,
            repeat_count=repeat_count,
        )
    except (SimulationInputError, ValueError) as exc:
        failure_input_hash = content_hash(
            stable_json(
                {
                    "review_version": AUTOMATED_REVIEW_VERSION,
                    "repeat_count": repeat_count,
                    "generation_run_id": run.id,
                    "program_commit_id": baseline_commit.id,
                    "git_sha": baseline_commit.git_sha,
                    "generator_version": run.generator_version,
                    "failure": str(exc),
                }
            )
        )
        report = {
            "review_version": AUTOMATED_REVIEW_VERSION,
            "input_hash": failure_input_hash,
            "status": "blocked",
            "verification_level": "automatic",
            "checks": [
                {
                    "id": "automated_review_execution",
                    "title": "自动审核执行完整性",
                    "status": "failed",
                    "severity": "blocker",
                    "detail": str(exc),
                    "evidence": {"generation_run_id": run.id},
                    "action": "保留当前生成基线，修复生成器或 TestSpec 后创建新基线",
                }
            ],
            "external_validation_gates": list(EXTERNAL_VALIDATION_GATES),
            "claim_boundary": "自动审核执行被阻断；该结果不代表厂商工具、真实 PLC 或电气工程师确认。",
        }

    existing = session.scalar(
        select(AutomatedReviewRun).where(
            AutomatedReviewRun.generation_run_id == run.id,
            AutomatedReviewRun.review_version == report["review_version"],
            AutomatedReviewRun.input_hash == report["input_hash"],
        )
    )
    if existing is not None:
        return existing, True

    report_bytes = json.dumps(
        report, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    stored = store_bytes(
        session,
        settings,
        report_bytes,
        f"automated-review-{run.id}-{report['input_hash'][:12]}.json",
        "application/json",
    )
    item = AutomatedReviewRun(
        project_id=run.project_id,
        generation_run_id=run.id,
        program_commit_id=baseline_commit.id,
        review_version=report["review_version"],
        input_hash=report["input_hash"],
        status=report["status"],
        verification_level=report["verification_level"],
        repeat_count=repeat_count,
        checks_json=json.dumps(report["checks"], ensure_ascii=False, sort_keys=True),
        external_gates_json=json.dumps(
            report["external_validation_gates"], ensure_ascii=False, sort_keys=True
        ),
        claim_boundary=report["claim_boundary"],
        report_artifact_id=stored.record.id,
    )
    session.add(item)
    session.flush()
    audit(
        session,
        run.project_id,
        "program.automated_review_completed",
        "AutomatedReviewRun",
        item.id,
        {
            "status": item.status,
            "input_hash": item.input_hash,
            "repeat_count": item.repeat_count,
            "verification_level": item.verification_level,
        },
    )
    return item, False


def audit(session: Session, project_id: str, action: str, entity_type: str, entity_id: str, payload: dict[str, Any] | None = None) -> None:
    session.add(AuditEvent(project_id=project_id, action=action, entity_type=entity_type, entity_id=entity_id, payload_json=json.dumps(payload or {}, ensure_ascii=False)))


def add_issues(session: Session, revision: MachineSpecRevision, issues: list[Any]) -> None:
    for issue in issues:
        session.add(ValidationIssue(spec_revision_id=revision.id, **issue.to_dict()))


def issue_dict(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "id": issue.id, "code": issue.code, "severity": issue.severity,
        "title": issue.title, "detail": issue.detail, "sheet": issue.sheet,
        "row_number": issue.row_number, "column_name": issue.column_name,
        "entity_id": issue.entity_id, "resolved": issue.resolved,
        "accepted_reason": issue.accepted_reason,
    }


def revision_dict(session: Session, revision: MachineSpecRevision) -> dict[str, Any]:
    issues = session.scalars(select(ValidationIssue).where(ValidationIssue.spec_revision_id == revision.id).order_by(ValidationIssue.created_at)).all()
    confirmations = session.scalars(select(ReviewConfirmation).where(ReviewConfirmation.spec_revision_id == revision.id)).all()
    data = json.loads(revision.data_json)
    return {
        "id": revision.id, "project_id": revision.project_id, "import_id": revision.import_id,
        "sequence": revision.sequence, "schema_version": revision.schema_version,
        "content_hash": revision.content_hash, "status": revision.status,
        "revision": revision.revision, "data": data,
        "issues": [issue_dict(item) for item in issues],
        "confirmations": [{"view": item.view, "confirmed_by": item.confirmed_by, "created_at": item.created_at.isoformat()} for item in confirmations],
        "required_views": required_review_views(data),
        "created_at": revision.created_at.isoformat(), "updated_at": revision.updated_at.isoformat(),
    }


def create_revision(session: Session, project: Project, import_version: ImportVersion, data: dict[str, Any], sequence: int, issues: list[Any]) -> MachineSpecRevision:
    blockers = any(issue.severity == "blocker" for issue in issues)
    revision = MachineSpecRevision(
        project_id=project.id, import_id=import_version.id, sequence=sequence,
        schema_version=str(data.get("schema_version", "1.0")),
        data_json=json.dumps(data, ensure_ascii=False, sort_keys=True),
        content_hash=spec_hash(data), status="blocked" if blockers else "review_ready",
    )
    session.add(revision)
    session.flush()
    add_issues(session, revision, issues)
    import_version.current_revision_id = revision.id
    import_version.status = revision.status
    project.current_import_id = import_version.id
    project.current_spec_revision_id = revision.id
    project.status = "资料校验" if blockers else "规格审阅"
    project.revision += 1
    return revision


@router.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kongpu-api", "mode": "local"}


@router.get("/api/v1/adapters")
def list_adapters() -> list[dict[str, Any]]:
    return [item.as_dict() for item in descriptors()]


@router.post("/api/v1/adapters/detect")
def detect_adapter_environment(
    payload: AdapterDetectRequest,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    try:
        item = descriptor(payload.adapter_id)
    except KeyError:
        raise api_error("ADAPTER_NOT_FOUND", "Adapter 不存在", 404, action="从能力列表选择 Adapter")
    project = require_project(session, payload.project_id) if payload.project_id else None
    target = {"plc_model": project.plc_model} if project else {}
    detected = detect_adapter(item.adapter_id, target)
    if project:
        existing = session.scalar(
            select(AdapterEnvironment).where(
                AdapterEnvironment.project_id == project.id,
                AdapterEnvironment.adapter_id == item.adapter_id,
                AdapterEnvironment.fingerprint == detected["fingerprint"],
            )
        )
        if existing is None:
            existing = AdapterEnvironment(
                project_id=project.id,
                adapter_id=item.adapter_id,
                adapter_version=item.version,
                status=detected["status"],
                verification_level=detected["verification_level"],
                fingerprint=detected["fingerprint"],
                details_json=json.dumps(detected["details"], ensure_ascii=False),
            )
            session.add(existing)
            session.flush()
        else:
            existing.status = detected["status"]
            existing.verification_level = detected["verification_level"]
            existing.details_json = json.dumps(detected["details"], ensure_ascii=False)
            existing.revision += 1
        audit(session, project.id, "adapter.environment_detected", "AdapterEnvironment", existing.id, {"adapter_id": item.adapter_id, "status": detected["status"]})
        session.commit()
        detected["environment"] = adapter_environment_dict(existing)
    return detected


@router.get("/api/v1/projects/{project_id}/adapter-environments")
def list_adapter_environments(
    project_id: str,
    session: Session = Depends(app_session),
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    items = session.scalars(
        select(AdapterEnvironment)
        .where(AdapterEnvironment.project_id == project_id)
        .order_by(AdapterEnvironment.updated_at.desc())
    ).all()
    return [adapter_environment_dict(item) for item in items]


@router.post("/api/v1/generation-runs/{run_id}/audit")
def run_generation_audit(
    run_id: str,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise api_error("GENERATION_RUN_NOT_FOUND", "生成任务不存在", 404)
    existing, reused = persist_generation_audit(session, runtime_settings, run)
    session.commit()
    result = audit_dict(existing)
    result["reused"] = reused
    return result


@router.get("/api/v1/generation-runs/{run_id}/audit")
def get_generation_audit(run_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise api_error("GENERATION_RUN_NOT_FOUND", "生成任务不存在", 404)
    branch = session.get(ProgramBranch, run.branch_id) if run.branch_id else None
    commit = (
        session.scalar(
            select(ProgramCommit).where(
                ProgramCommit.branch_id == branch.id,
                ProgramCommit.git_sha == branch.head_commit
            )
        )
        if branch and branch.head_commit
        else None
    )
    item = (
        session.scalar(
            select(GenerationAudit)
            .where(
                GenerationAudit.generation_run_id == run.id,
                GenerationAudit.program_commit_id == commit.id,
            )
            .order_by(GenerationAudit.created_at.desc())
        )
        if commit
        else None
    )
    if item is None:
        raise api_error(
            "AUDIT_NOT_FOUND",
            "当前 Commit 尚未运行生成物自审计",
            404,
            action="对当前 Commit 运行自审计",
        )
    return audit_dict(item)


@router.post("/api/v1/projects/{project_id}/automated-reviews", status_code=201)
def create_automated_review(
    project_id: str,
    payload: AutomatedReviewRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    run = session.get(GenerationRun, payload.generation_run_id)
    if run is None or run.project_id != project.id:
        raise api_error(
            "GENERATION_RUN_NOT_FOUND",
            "生成任务不存在或不属于当前项目",
            404,
        )
    check_expected_revision(
        run.revision, payload.expected_generation_revision, if_match
    )
    if run.status != "review_ready":
        raise api_error(
            "GENERATION_NOT_READY",
            "生成任务尚未形成不可变审核基线",
            409,
            action="等待生成完成或创建新的生成任务",
        )
    item, reused = persist_automated_review(
        session, runtime_settings, run, repeat_count=payload.repeat_count
    )
    session.commit()
    result = automated_review_dict(session, item)
    result["reused"] = reused
    return result


@router.get("/api/v1/automated-reviews/{review_id}")
def get_automated_review(
    review_id: str, session: Session = Depends(app_session)
) -> dict[str, Any]:
    item = session.get(AutomatedReviewRun, review_id)
    if item is None:
        raise api_error("AUTOMATED_REVIEW_NOT_FOUND", "自动审核报告不存在", 404)
    return automated_review_dict(session, item)


@router.get("/api/v1/projects/{project_id}/automated-reviews")
def list_automated_reviews(
    project_id: str, session: Session = Depends(app_session)
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    items = session.scalars(
        select(AutomatedReviewRun)
        .where(AutomatedReviewRun.project_id == project_id)
        .order_by(AutomatedReviewRun.created_at.desc())
    ).all()
    return [automated_review_dict(session, item) for item in items]


@router.post("/api/v1/projects/{project_id}/compile-runs", status_code=201)
def create_compile_run(
    project_id: str,
    payload: CompileRunRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    generation = session.get(GenerationRun, payload.generation_run_id)
    if generation is None or generation.project_id != project.id:
        raise api_error("GENERATION_RUN_NOT_FOUND", "生成任务不存在或不属于当前项目", 404)
    check_expected_revision(generation.revision, payload.expected_generation_revision, if_match)
    if generation.status != "review_ready" or not generation.control_ir_revision_id:
        raise api_error("GENERATION_NOT_READY", "生成物尚未完成确定性生成与审计，不能创建编译准备任务", 409, action="先在 P07 运行生成物自审计并处理 blocker")
    _spec_data, _bundle, baseline_commit, _test_spec = generation_baseline(session, runtime_settings, generation)
    require_current_automated_review(session, generation, baseline_commit)
    try:
        adapter = descriptor(payload.adapter_id)
    except KeyError:
        raise api_error("ADAPTER_NOT_FOUND", "Adapter 不存在", 404)
    if payload.adapter_id == "reference":
        raise api_error("COMPILE_ADAPTER_UNSUPPORTED", "参考逻辑引擎不能执行厂商编译", 422, action="选择 GX Works3 或 AutoShop 并在厂商工具中人工编译")
    environment = session.scalar(select(AdapterEnvironment).where(AdapterEnvironment.project_id == project.id, AdapterEnvironment.adapter_id == adapter.adapter_id).order_by(AdapterEnvironment.updated_at.desc()))
    diagnostics = [{"code": "VENDOR_TOOL_UNAVAILABLE", "severity": "info", "message": "未执行厂商编译；当前 Adapter 仅提供人工降级路径。", "verification_level": "unverified", "action": "在隔离工程副本中使用对应厂商工具编译后导入证据"}]
    item = CompileRun(project_id=project.id, generation_run_id=generation.id, program_commit_id=baseline_commit.id, adapter_id=adapter.adapter_id, adapter_environment_id=environment.id if environment else None, status="manual_required", verification_level="unverified", diagnostics_json=json.dumps(diagnostics, ensure_ascii=False))
    session.add(item)
    session.flush()
    audit(session, project.id, "compile.manual_required", "CompileRun", item.id, {"adapter_id": adapter.adapter_id})
    session.commit()
    return compile_dict(session, item)


@router.get("/api/v1/compile-runs/{run_id}")
def get_compile_run(run_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    item = session.get(CompileRun, run_id)
    if item is None:
        raise api_error("COMPILE_RUN_NOT_FOUND", "编译任务不存在", 404)
    return compile_dict(session, item)


@router.post("/api/v1/compile-runs/{run_id}/evidence", status_code=201)
def upload_compile_evidence(
    run_id: str,
    file: UploadFile = File(...),
    evidence_kind: str = Form(default="vendor_report"),
    expected_revision: int = Form(...),
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    item = session.get(CompileRun, run_id)
    if item is None:
        raise api_error("COMPILE_RUN_NOT_FOUND", "编译任务不存在", 404)
    check_expected_revision(item.revision, expected_revision, if_match)
    content = file.file.read(runtime_settings.max_upload_bytes + 1)
    if len(content) > runtime_settings.max_upload_bytes:
        raise api_error("FILE_TOO_LARGE", "证据文件超过 20 MB 限制", 413, action="压缩证据或拆分后重新上传")
    stored = store_bytes(session, runtime_settings, content, file.filename or "compile-evidence.bin", file.content_type or "application/octet-stream")
    evidence = EvidenceArtifact(project_id=item.project_id, compile_run_id=item.id, source_artifact_id=stored.record.id, evidence_kind=evidence_kind, verification_level="manual_unverified")
    session.add(evidence)
    session.flush()
    item.revision += 1
    audit(session, item.project_id, "compile.evidence_uploaded", "EvidenceArtifact", evidence.id, {"kind": evidence_kind, "sha256": stored.record.sha256, "verification_level": "manual_unverified"})
    session.commit()
    return {"id": evidence.id, "source_artifact_id": stored.record.id, "sha256": stored.record.sha256, "evidence_kind": evidence.evidence_kind, "verification_level": evidence.verification_level, "compile_run": compile_dict(session, item)}


@router.get("/api/v1/projects/{project_id}/compile-runs")
def list_compile_runs(project_id: str, session: Session = Depends(app_session)) -> list[dict[str, Any]]:
    require_project(session, project_id)
    items = session.scalars(select(CompileRun).where(CompileRun.project_id == project_id).order_by(CompileRun.created_at.desc())).all()
    return [compile_dict(session, item) for item in items]


@router.post("/api/v1/projects/{project_id}/simulation-runs", status_code=201)
def create_simulation_run(
    project_id: str,
    payload: SimulationRunRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    generation = session.get(GenerationRun, payload.generation_run_id)
    if generation is None or generation.project_id != project.id:
        raise api_error("GENERATION_RUN_NOT_FOUND", "生成任务不存在或不属于当前项目", 404)
    if not generation.control_ir_revision_id:
        raise api_error("CONTROL_IR_NOT_FOUND", "生成任务缺少 Control IR", 409)
    _spec_data, baseline_bundle, baseline_commit, test_spec = generation_baseline(
        session,
        runtime_settings,
        generation,
    )
    check_expected_revision(generation.revision, payload.expected_generation_revision, if_match)
    require_current_automated_review(session, generation, baseline_commit)
    try:
        result = run_test_spec(baseline_bundle.control_ir, baseline_bundle.test_spec, payload.input_overrides, payload.max_cycles)
    except SimulationInputError as exc:
        raise api_error("SIMULATION_INPUT_INVALID", str(exc), 422, action="检查输入变量和最大周期")
    test_spec_row = test_spec
    item = SimulationRun(project_id=project.id, generation_run_id=generation.id, program_commit_id=baseline_commit.id, test_spec_revision_id=test_spec_row.id, engine_version=result["engine_version"], status="review_ready" if result["status"] == "passed" else "failed", verification_level="automatic_reference", results_json=json.dumps(result, ensure_ascii=False, sort_keys=True))
    session.add(item)
    session.flush()
    for trace in result["traces"]:
        session.add(SimulationTrace(simulation_run_id=item.id, cycle=trace["cycle"], step_id=trace.get("step_id"), inputs_json=json.dumps(trace["inputs"], ensure_ascii=False, sort_keys=True), outputs_json=json.dumps(trace["outputs"], ensure_ascii=False, sort_keys=True), events_json=json.dumps(trace["events"], ensure_ascii=False)))
    trace_bytes = json.dumps({"simulation_run_id": item.id, "generation_run_id": generation.id, "engine_version": result["engine_version"], "verification_level": "automatic_reference", "result": result}, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    trace_artifact = store_bytes(session, runtime_settings, trace_bytes, f"simulation-trace-{item.id}.json", "application/json")
    item.trace_artifact_id = trace_artifact.record.id
    audit(session, project.id, "simulation.reference_completed", "SimulationRun", item.id, {"status": item.status, "engine_version": item.engine_version, "verification_level": item.verification_level})
    session.commit()
    return simulation_dict(session, item)


@router.get("/api/v1/simulation-runs/{run_id}")
def get_simulation_run(run_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    item = session.get(SimulationRun, run_id)
    if item is None:
        raise api_error("SIMULATION_RUN_NOT_FOUND", "模拟任务不存在", 404)
    return simulation_dict(session, item)


@router.get("/api/v1/simulation-runs/{run_id}/trace")
def get_simulation_trace(run_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    item = session.get(SimulationRun, run_id)
    if item is None:
        raise api_error("SIMULATION_RUN_NOT_FOUND", "模拟任务不存在", 404)
    traces = session.scalars(select(SimulationTrace).where(SimulationTrace.simulation_run_id == item.id).order_by(SimulationTrace.cycle)).all()
    return {"simulation_run_id": item.id, "engine_version": item.engine_version, "verification_level": item.verification_level, "traces": [{"cycle": trace.cycle, "step_id": trace.step_id, "inputs": json.loads(trace.inputs_json), "outputs": json.loads(trace.outputs_json), "events": json.loads(trace.events_json)} for trace in traces]}


@router.get("/api/v1/projects/{project_id}/simulation-runs")
def list_simulation_runs(project_id: str, session: Session = Depends(app_session)) -> list[dict[str, Any]]:
    require_project(session, project_id)
    items = session.scalars(select(SimulationRun).where(SimulationRun.project_id == project_id).order_by(SimulationRun.created_at.desc())).all()
    return [simulation_dict(session, item) for item in items]


@router.post("/api/v1/projects/{project_id}/release-candidates", status_code=201)
def create_release_candidate(
    project_id: str,
    payload: ReleaseCandidateRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    run = session.get(GenerationRun, payload.generation_run_id)
    if run is None or run.project_id != project.id:
        raise api_error("GENERATION_RUN_NOT_FOUND", "生成任务不存在或不属于当前项目", 404)
    check_expected_revision(run.revision, payload.expected_generation_revision, if_match)
    spec, bundle, commit, test_spec = generation_baseline(session, runtime_settings, run)
    branch = require_branch(session, run.branch_id or "")
    try:
        repo = ensure_repository(runtime_settings, project.id)
        if branch.status != "clean" or not is_working_tree_clean(repo):
            raise api_error(
                "PROGRAM_BRANCH_DIRTY",
                "当前程序分支存在未提交修改，不能生成交付候选包",
                409,
                action="提交修改并完成当前 Commit 自动审核",
            )
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422)

    review = require_current_automated_review(session, run, commit)
    static_audit, _audit_reused = persist_generation_audit(
        session, runtime_settings, run
    )
    if static_audit.status == "blocked":
        raise api_error(
            "GENERATION_AUDIT_BLOCKED",
            "当前 Commit 的确定性静态审计存在 blocker",
            409,
            action="保留报告，修复后创建新 Commit",
        )
    simulation = session.scalar(
        select(SimulationRun)
        .where(
            SimulationRun.generation_run_id == run.id,
            SimulationRun.program_commit_id == commit.id,
            SimulationRun.status == "review_ready",
        )
        .order_by(SimulationRun.created_at.desc())
    )
    if simulation is None or not simulation.trace_artifact_id:
        raise api_error(
            "REFERENCE_SIMULATION_REQUIRED",
            "当前 Commit 尚无通过的控谱参考逻辑模拟",
            409,
            action="在 P08 对当前 Commit 运行参考逻辑模拟",
        )

    revision = require_spec(session, run.spec_revision_id)
    locked = session.scalar(
        select(LockedMachineSpec).where(
            LockedMachineSpec.spec_revision_id == revision.id
        )
    )
    import_version = session.get(ImportVersion, revision.import_id)
    if locked is None or import_version is None:
        raise api_error("LOCKED_SPEC_REQUIRED", "锁定规格或原始导入记录不完整", 409)

    entries: dict[str, bytes] = {}
    artifact_inputs: list[dict[str, Any]] = []

    def add_artifact_entry(path: str, artifact_id: str) -> None:
        record, content = read_artifact_bytes(
            session, runtime_settings, artifact_id
        )
        entries[path] = content
        artifact_inputs.append(
            {"path": path, "artifact_id": record.id, "sha256": record.sha256}
        )

    add_artifact_entry("spec/MachineSpec.locked.json", locked.snapshot_artifact_id)
    add_artifact_entry("source/original.xlsx", import_version.source_artifact_id)
    add_artifact_entry("evidence/automated-review.json", review.report_artifact_id)
    if not static_audit.report_artifact_id:
        raise api_error("GENERATION_AUDIT_INCOMPLETE", "静态审计报告工件缺失", 409)
    add_artifact_entry("evidence/static-audit.json", static_audit.report_artifact_id)
    add_artifact_entry("evidence/reference-simulation.json", simulation.trace_artifact_id)
    for path, content in sorted(bundle.files.items()):
        entries[f"program/{path}"] = content.encode("utf-8")

    manual_evidence = session.execute(
        select(EvidenceArtifact, SourceArtifact)
        .join(CompileRun, EvidenceArtifact.compile_run_id == CompileRun.id)
        .join(SourceArtifact, EvidenceArtifact.source_artifact_id == SourceArtifact.id)
        .where(
            CompileRun.project_id == project.id,
            CompileRun.program_commit_id == commit.id,
        )
        .order_by(EvidenceArtifact.created_at, EvidenceArtifact.id)
    ).all()
    for index, (evidence, artifact) in enumerate(manual_evidence, start=1):
        add_artifact_entry(
            f"evidence/manual/{index:03d}-{evidence.evidence_kind}-{artifact.original_name}",
            artifact.id,
        )

    input_record = {
        "project_id": project.id,
        "generation_run_id": run.id,
        "program_commit_id": commit.id,
        "git_sha": commit.git_sha,
        "machine_spec_hash": revision.content_hash,
        "control_ir_hash": content_hash(stable_json(bundle.control_ir)),
        "test_spec_hash": test_spec.content_hash,
        "automated_review_hash": review.input_hash,
        "static_audit_hash": static_audit.input_hash,
        "simulation_trace_artifact_id": simulation.trace_artifact_id,
        "generator_version": run.generator_version,
        "artifact_inputs": sorted(artifact_inputs, key=lambda item: item["path"]),
        "entry_index": entry_index(entries),
    }
    input_hash = sha256_bytes(stable_json_bytes(input_record))
    existing = session.scalar(
        select(ReleaseCandidate).where(
            ReleaseCandidate.project_id == project.id,
            ReleaseCandidate.input_hash == input_hash,
        )
    )
    if existing is not None:
        session.rollback()
        result = release_candidate_dict(session, existing)
        result["reused"] = True
        return result

    next_number = (
        session.scalar(
            select(func.count()).select_from(ReleaseCandidate).where(
                ReleaseCandidate.project_id == project.id
            )
        )
        or 0
    ) + 1
    version = f"RC-{next_number:04d}"
    manifest_seed = {
        "candidate_version": version,
        "status": "external_validation_required",
        "verification_level": "automatic_package",
        "project": {
            "id": project.id,
            "code": project.code,
            "name": project.name,
            "plc_target": {
                "brand": project.plc_brand,
                "series": project.plc_series,
                "model": project.plc_model,
            },
        },
        "baseline": input_record,
        "external_validation_gates": json.loads(review.external_gates_json),
        "claim_boundary": "该 ZIP 是自动验证后的交付候选包，不代表 GX Works3 编译、真实 PLC 硬件或电气工程师确认，禁止直接用于生产。",
    }
    try:
        package, manifest = build_delivery_candidate(manifest_seed, entries)
        verified_manifest = verify_delivery_candidate(package)
    except DeliveryInputError as exc:
        raise api_error("DELIVERY_PACKAGE_INVALID", str(exc), 422)
    if verified_manifest != manifest:
        raise api_error("DELIVERY_PACKAGE_INVALID", "候选包自校验结果不一致", 409)
    package_artifact = store_bytes(
        session,
        runtime_settings,
        package,
        f"Kongpu-{project.code}-{version}.zip",
        "application/zip",
    )
    manifest_hash = sha256_bytes(stable_json_bytes(manifest))
    candidate = ReleaseCandidate(
        project_id=project.id,
        generation_run_id=run.id,
        program_commit_id=commit.id,
        automated_review_id=review.id,
        version=version,
        input_hash=input_hash,
        manifest_hash=manifest_hash,
        manifest_json=json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        status="external_validation_required",
        verification_level="automatic_package",
        package_artifact_id=package_artifact.record.id,
    )
    session.add(candidate)
    session.flush()
    audit(
        session,
        project.id,
        "release.candidate_created",
        "ReleaseCandidate",
        candidate.id,
        {
            "version": version,
            "program_commit_id": commit.id,
            "manifest_hash": manifest_hash,
            "verification_level": "automatic_package",
        },
    )
    session.commit()
    result = release_candidate_dict(session, candidate)
    result["reused"] = False
    return result


@router.get("/api/v1/projects/{project_id}/release-candidates")
def list_release_candidates(
    project_id: str, session: Session = Depends(app_session)
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    items = session.scalars(
        select(ReleaseCandidate)
        .where(ReleaseCandidate.project_id == project_id)
        .order_by(ReleaseCandidate.created_at.desc())
    ).all()
    return [release_candidate_dict(session, item) for item in items]


@router.get("/api/v1/release-candidates/{candidate_id}")
def get_release_candidate(
    candidate_id: str, session: Session = Depends(app_session)
) -> dict[str, Any]:
    item = session.get(ReleaseCandidate, candidate_id)
    if item is None:
        raise api_error("RELEASE_CANDIDATE_NOT_FOUND", "交付候选包不存在", 404)
    return release_candidate_dict(session, item)


@router.post("/api/v1/projects/{project_id}/monitoring-plans", status_code=201)
def create_monitoring_plan(
    project_id: str,
    payload: MonitoringPlanRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    candidate = session.get(ReleaseCandidate, payload.release_candidate_id)
    if candidate is None or candidate.project_id != project.id:
        raise api_error("RELEASE_CANDIDATE_NOT_FOUND", "交付候选包不存在或不属于当前项目", 404)
    check_expected_revision(candidate.revision, payload.expected_candidate_revision, if_match)
    existing = session.scalar(
        select(MonitoringPlan).where(
            MonitoringPlan.release_candidate_id == candidate.id
        )
    )
    if existing is not None:
        result = monitoring_plan_dict(session, existing)
        result["reused"] = True
        return result
    run = session.get(GenerationRun, candidate.generation_run_id)
    if run is None or not run.control_ir_revision_id:
        raise api_error("CONTROL_IR_NOT_FOUND", "候选包缺少 Control IR 基线", 409)
    control_ir = session.get(ControlIRRevision, run.control_ir_revision_id)
    if control_ir is None or content_hash(control_ir.data_json) != control_ir.content_hash:
        raise api_error("CONTROL_IR_HASH_MISMATCH", "Control IR 基线哈希不匹配", 409)
    variables = build_variable_map(json.loads(control_ir.data_json))
    fingerprint = target_fingerprint(
        project_id=project.id,
        plc_brand=project.plc_brand,
        plc_series=project.plc_series,
        plc_model=project.plc_model,
        candidate_manifest_hash=candidate.manifest_hash,
        variables=variables,
    )
    item = MonitoringPlan(
        project_id=project.id,
        release_candidate_id=candidate.id,
        target_fingerprint=fingerprint,
        variable_map_hash=variable_map_hash(variables),
        variable_map_json=json.dumps(variables, ensure_ascii=False, sort_keys=True),
        status="awaiting_external_read_only_connection",
        verification_level="unverified",
    )
    session.add(item)
    session.flush()
    audit(
        session, project.id, "monitoring.plan_created", "MonitoringPlan", item.id,
        {"release_candidate_id": candidate.id, "access": "read_only"},
    )
    session.commit()
    result = monitoring_plan_dict(session, item)
    result["reused"] = False
    return result


@router.get("/api/v1/projects/{project_id}/monitoring-plans")
def list_monitoring_plans(
    project_id: str, session: Session = Depends(app_session)
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    items = session.scalars(
        select(MonitoringPlan)
        .where(MonitoringPlan.project_id == project_id)
        .order_by(MonitoringPlan.created_at.desc())
    ).all()
    return [monitoring_plan_dict(session, item) for item in items]


@router.get("/api/v1/monitoring-plans/{plan_id}")
def get_monitoring_plan(
    plan_id: str, session: Session = Depends(app_session)
) -> dict[str, Any]:
    item = session.get(MonitoringPlan, plan_id)
    if item is None:
        raise api_error("MONITORING_PLAN_NOT_FOUND", "只读监控计划不存在", 404)
    return monitoring_plan_dict(session, item)


@router.post("/api/v1/monitoring-plans/{plan_id}/snapshots", status_code=201)
def create_monitoring_snapshot(
    plan_id: str,
    payload: MonitoringSnapshotRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    plan = session.get(MonitoringPlan, plan_id)
    if plan is None:
        raise api_error("MONITORING_PLAN_NOT_FOUND", "只读监控计划不存在", 404)
    check_expected_revision(plan.revision, payload.expected_plan_revision, if_match)
    if payload.observed_target_fingerprint != plan.target_fingerprint:
        raise api_error(
            "MONITORING_TARGET_MISMATCH",
            "离线快照的目标指纹与候选包不一致",
            409,
            action="停止分析并核对项目、PLC 目标、候选 Manifest 和变量映射",
        )
    candidate = session.get(ReleaseCandidate, plan.release_candidate_id)
    run = session.get(GenerationRun, candidate.generation_run_id) if candidate else None
    control_ir = (
        session.get(ControlIRRevision, run.control_ir_revision_id)
        if run and run.control_ir_revision_id
        else None
    )
    if control_ir is None or content_hash(control_ir.data_json) != control_ir.content_hash:
        raise api_error("CONTROL_IR_HASH_MISMATCH", "Control IR 基线不可用", 409)
    variables = json.loads(plan.variable_map_json)
    if variable_map_hash(variables) != plan.variable_map_hash:
        raise api_error("VARIABLE_MAP_HASH_MISMATCH", "只读变量映射哈希不匹配", 409)
    try:
        analysis = analyze_snapshot(
            json.loads(control_ir.data_json),
            variables,
            payload.values,
            payload.current_step_id,
        )
    except MonitoringInputError as exc:
        raise api_error("MONITORING_SNAPSHOT_INVALID", str(exc), 422)
    original = {
        "schema": "kongpu-offline-monitoring-snapshot/v1",
        "monitoring_plan_id": plan.id,
        "release_candidate_id": plan.release_candidate_id,
        "observed_target_fingerprint": payload.observed_target_fingerprint,
        "values": payload.values,
        "current_step_id": payload.current_step_id,
        "note": payload.note,
        "analysis": analysis,
    }
    stored = store_bytes(
        session,
        runtime_settings,
        stable_json_bytes(original),
        f"monitoring-snapshot-{plan.id}-{new_id()[:8]}.json",
        "application/json",
    )
    evidence = MonitoringEvidence(
        project_id=plan.project_id,
        monitoring_plan_id=plan.id,
        source_artifact_id=stored.record.id,
        status=analysis["status"],
        verification_level="manual_unverified",
        analysis_json=json.dumps(analysis, ensure_ascii=False, sort_keys=True),
        note=payload.note,
    )
    session.add(evidence)
    session.flush()
    plan.revision += 1
    audit(
        session, plan.project_id, "monitoring.snapshot_recorded",
        "MonitoringEvidence", evidence.id,
        {"sha256": stored.record.sha256, "status": evidence.status},
    )
    session.commit()
    return monitoring_evidence_dict(session, evidence)


@router.get("/api/v1/monitoring-plans/{plan_id}/evidence")
def list_monitoring_evidence(
    plan_id: str, session: Session = Depends(app_session)
) -> list[dict[str, Any]]:
    plan = session.get(MonitoringPlan, plan_id)
    if plan is None:
        raise api_error("MONITORING_PLAN_NOT_FOUND", "只读监控计划不存在", 404)
    items = session.scalars(
        select(MonitoringEvidence)
        .where(MonitoringEvidence.monitoring_plan_id == plan.id)
        .order_by(MonitoringEvidence.created_at.desc())
    ).all()
    return [monitoring_evidence_dict(session, item) for item in items]


@router.post("/api/v1/monitoring-evidence/{evidence_id}/commissioning-tasks", status_code=201)
def create_commissioning_task(
    evidence_id: str,
    payload: CommissioningTaskRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    evidence = session.get(MonitoringEvidence, evidence_id)
    if evidence is None:
        raise api_error("MONITORING_EVIDENCE_NOT_FOUND", "离线监控证据不存在", 404)
    plan = session.get(MonitoringPlan, evidence.monitoring_plan_id)
    if plan is None:
        raise api_error("MONITORING_PLAN_NOT_FOUND", "只读监控计划不存在", 404)
    check_expected_revision(plan.revision, payload.expected_plan_revision, if_match)
    existing = session.scalar(
        select(CommissioningTask).where(
            CommissioningTask.monitoring_evidence_id == evidence.id
        )
    )
    if existing is not None:
        return commissioning_task_dict(existing)
    candidate = session.get(ReleaseCandidate, plan.release_candidate_id)
    source_run = (
        session.get(GenerationRun, candidate.generation_run_id)
        if candidate
        else None
    )
    source_commit = (
        session.get(ProgramCommit, candidate.program_commit_id)
        if candidate
        else None
    )
    if (
        candidate is None
        or source_run is None
        or source_commit is None
        or not source_run.control_ir_revision_id
    ):
        raise api_error("RELEASE_BASELINE_INCOMPLETE", "候选包程序基线不完整", 409)
    workspace, repo = workspace_for_project(
        session, runtime_settings, evidence.project_id
    )
    branch_name = f"engineer/commissioning-{evidence.id[:8]}"
    duplicate = session.scalar(
        select(ProgramBranch).where(
            ProgramBranch.workspace_id == workspace.id,
            ProgramBranch.name == branch_name,
        )
    )
    if duplicate is not None:
        raise api_error("COMMISSIONING_BRANCH_CONFLICT", "调试分支已存在但任务记录缺失", 409)
    try:
        if not is_working_tree_clean(repo):
            raise api_error("PROGRAM_BRANCH_DIRTY", "程序仓库存在未提交修改", 409)
        checkout_branch(repo, branch_name, source_commit.git_sha)
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422)
    branch = ProgramBranch(
        workspace_id=workspace.id,
        name=branch_name,
        git_ref=f"refs/heads/{branch_name}",
        base_commit=source_commit.git_sha,
        head_commit=source_commit.git_sha,
        status="clean",
    )
    session.add(branch)
    session.flush()
    derived_run = GenerationRun(
        project_id=evidence.project_id,
        spec_revision_id=source_run.spec_revision_id,
        branch_id=branch.id,
        control_ir_revision_id=source_run.control_ir_revision_id,
        generator_version=source_run.generator_version,
        status="review_ready",
        warnings_json=source_run.warnings_json,
    )
    session.add(derived_run)
    session.flush()
    source_test_spec = session.scalar(
        select(TestSpecRevision).where(
            TestSpecRevision.generation_run_id == source_run.id
        )
    )
    if source_test_spec is None:
        raise api_error("TEST_SPEC_NOT_FOUND", "候选包 TestSpec 基线缺失", 409)
    session.add(
        TestSpecRevision(
            generation_run_id=derived_run.id,
            content_hash=source_test_spec.content_hash,
            data_json=source_test_spec.data_json,
        )
    )
    for item in session.scalars(
        select(ProgramArtifact).where(
            ProgramArtifact.generation_run_id == source_run.id
        )
    ).all():
        session.add(
            ProgramArtifact(
                generation_run_id=derived_run.id,
                path=item.path, kind=item.kind,
                content_hash=item.content_hash,
                source_artifact_id=item.source_artifact_id,
            )
        )
    for item in session.scalars(
        select(TraceLink).where(TraceLink.generation_run_id == source_run.id)
    ).all():
        session.add(
            TraceLink(
                generation_run_id=derived_run.id,
                output_path=item.output_path, output_symbol=item.output_symbol,
                output_line=item.output_line, entity_type=item.entity_type,
                entity_id=item.entity_id, source_sheet=item.source_sheet,
                source_row=item.source_row,
            )
        )
    task = CommissioningTask(
        project_id=evidence.project_id,
        monitoring_evidence_id=evidence.id,
        branch_id=branch.id,
        generation_run_id=derived_run.id,
        description=payload.description,
        status="open",
    )
    session.add(task)
    session.flush()
    plan.revision += 1
    workspace.revision += 1
    audit(
        session, evidence.project_id, "commissioning.task_created",
        "CommissioningTask", task.id,
        {
            "release_candidate_id": candidate.id,
            "base_commit": source_commit.git_sha,
            "branch": branch_name,
            "access": "offline_branch_only",
        },
    )
    session.commit()
    return commissioning_task_dict(task)


@router.get("/api/v1/schemas/machine-spec/v1")
def machine_spec_schema() -> dict[str, Any]:
    return MachineSpec.model_json_schema()


@router.get("/api/v1/projects")
def list_projects(
    include_archived: bool = False,
    session: Session = Depends(app_session),
) -> list[dict[str, Any]]:
    query = select(Project).order_by(Project.updated_at.desc())
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    return [project_dict(project) for project in session.scalars(query).all()]


@router.post("/api/v1/projects", status_code=201)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    count = session.scalar(select(func.count()).select_from(Project)) or 0
    project = Project(
        code=f"KP-{datetime.now(timezone.utc):%y%m}-{count + 1:03d}",
        name=payload.name.strip(),
        customer_code=payload.customer_code.strip() if payload.customer_code else None,
        plc_brand=payload.plc_brand,
        plc_series=payload.plc_series,
        plc_model=payload.plc_model,
        status="资料准备",
    )
    session.add(project)
    session.flush()
    audit(session, project.id, "project.created", "Project", project.id, {"plc_model": project.plc_model})
    session.commit()
    return project_dict(project)


@router.get("/api/v1/projects/{project_id}")
def get_project(project_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    return project_dict(require_project(session, project_id))


@router.patch("/api/v1/projects/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectPatch,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    check_expected_revision(project.revision, payload.expected_revision, if_match)
    before_target = (project.plc_brand, project.plc_series, project.plc_model)
    changes = payload.model_dump(exclude_none=True, exclude={"expected_revision"})
    for key, value in changes.items():
        setattr(project, key, value.strip() if isinstance(value, str) else value)
    target_changed = before_target != (project.plc_brand, project.plc_series, project.plc_model)
    if target_changed:
        imports = session.scalars(
            select(ImportVersion).where(ImportVersion.project_id == project.id)
        ).all()
        for import_version in imports:
            import_version.status = "stale"
            import_version.revision += 1
            for spec_revision in import_version.spec_revisions:
                if spec_revision.status != "locked":
                    spec_revision.status = "stale"
                for confirmation in list(spec_revision.confirmations):
                    session.delete(confirmation)
        if project.current_spec_revision_id:
            project.status = "目标已变更，资料过期"
    project.revision += 1
    audit(session, project.id, "project.updated", "Project", project.id, {"changes": changes, "target_changed": target_changed})
    session.commit()
    return project_dict(project)


def set_archived(project_id: str, archived: bool, session: Session) -> dict[str, Any]:
    project = require_project(session, project_id)
    project.archived = archived
    project.revision += 1
    audit(session, project.id, "project.archived" if archived else "project.restored", "Project", project.id)
    session.commit()
    return project_dict(project)


@router.post("/api/v1/projects/{project_id}/archive")
def archive_project(project_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    return set_archived(project_id, True, session)


@router.post("/api/v1/projects/{project_id}/restore")
def restore_project(project_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    return set_archived(project_id, False, session)


@router.get("/api/v1/template-versions/current")
def current_template(session: Session = Depends(app_session)) -> dict[str, Any]:
    seed_template_version(session)
    item = session.scalar(
        select(TemplateVersion)
        .where(TemplateVersion.active.is_(True))
        .order_by(TemplateVersion.version.desc())
    )
    if item is None:
        raise api_error("TEMPLATE_NOT_FOUND", "当前模板不存在", 500)
    return {
        "id": item.id,
        "version": item.version,
        "schema_version": item.schema_version,
        "definition": json.loads(item.definition_json),
    }


@router.post("/api/v1/projects/{project_id}/templates")
def download_template(
    project_id: str,
    kind: str = Query(default="blank", pattern="^(blank|example)$"),
    session: Session = Depends(app_session),
) -> Response:
    project = require_project(session, project_id)
    content = generate_workbook(
        {
            "id": project.id,
            "code": project.code,
            "name": project.name,
            "customer_code": project.customer_code or "",
            "plc_brand": project.plc_brand,
            "plc_series": project.plc_series,
            "plc_model": project.plc_model,
        },
        kind=kind,
    )
    filename = f"{project.code}_MachineSpec_v1_{kind}.xlsx"
    audit(session, project.id, "template.downloaded", "TemplateVersion", "1.0", {"kind": kind})
    session.commit()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/v1/projects/{project_id}/imports", status_code=201)
def create_import(
    project_id: str,
    file: UploadFile = File(...),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith(".xlsx") or filename.lower().endswith((".xlsm", ".xls")):
        raise api_error("UNSUPPORTED_FILE_TYPE", "只接受未加密 .xlsx 文件", action="下载当前项目模板")
    content = file.file.read(runtime_settings.max_upload_bytes + 1)
    if len(content) > runtime_settings.max_upload_bytes:
        raise api_error(
            "FILE_TOO_LARGE",
            f"文件超过 {runtime_settings.max_upload_bytes // (1024 * 1024)} MB 限制",
            413,
            action="压缩文件或拆分资料后重新上传",
        )
    artifact = store_bytes(
        session, runtime_settings, content, filename,
        file.content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    next_version = (
        session.scalar(
            select(func.max(ImportVersion.version)).where(ImportVersion.project_id == project.id)
        )
        or 0
    ) + 1
    import_version = ImportVersion(
        project_id=project.id, version=next_version,
        source_artifact_id=artifact.record.id, filename=artifact.record.original_name,
        status="parsing",
    )
    session.add(import_version)
    session.flush()
    try:
        spec, parse_issues = parse_workbook(content, runtime_settings)
    except WorkbookInputError as exc:
        import_version.status = "failed"
        import_version.failure_reason = str(exc)
        project.current_import_id = import_version.id
        project.status = "资料导入失败"
        project.revision += 1
        audit(session, project.id, "import.failed", "ImportVersion", import_version.id, {"code": exc.code, "filename": filename})
        session.commit()
        raise api_error(exc.code, str(exc), 422, action="保留原文件并重新上传有效模板")

    expected = {
        "id": project.id, "code": project.code,
        "plc_brand": project.plc_brand, "plc_series": project.plc_series,
        "plc_model": project.plc_model,
    }
    issues = parse_issues + validate_spec(spec, expected)
    revision = create_revision(session, project, import_version, spec, 1, issues)
    audit(session, project.id, "import.created", "ImportVersion", import_version.id, {"filename": filename, "sha256": artifact.record.sha256})
    session.commit()
    return {
        "import": {
            "id": import_version.id, "version": import_version.version,
            "filename": import_version.filename, "status": import_version.status,
            "revision": import_version.revision,
        },
        "revision": revision_dict(session, revision),
        "artifact": {
            "id": artifact.record.id, "sha256": artifact.record.sha256,
            "size_bytes": artifact.record.size_bytes,
        },
    }


@router.get("/api/v1/imports/{import_id}")
def get_import(import_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    item = session.get(ImportVersion, import_id)
    if item is None:
        raise api_error("IMPORT_NOT_FOUND", "导入版本不存在", 404)
    revision = session.get(MachineSpecRevision, item.current_revision_id) if item.current_revision_id else None
    return {
        "id": item.id, "project_id": item.project_id, "version": item.version,
        "filename": item.filename, "status": item.status, "revision": item.revision,
        "failure_reason": item.failure_reason,
        "spec_revision": revision_dict(session, revision) if revision else None,
    }


@router.get("/api/v1/imports/{import_id}/issues")
def get_import_issues(import_id: str, session: Session = Depends(app_session)) -> list[dict[str, Any]]:
    item = session.get(ImportVersion, import_id)
    if item is None:
        raise api_error("IMPORT_NOT_FOUND", "导入版本不存在", 404)
    if not item.current_revision_id:
        return []
    issues = session.scalars(
        select(ValidationIssue)
        .where(ValidationIssue.spec_revision_id == item.current_revision_id)
        .order_by(ValidationIssue.created_at)
    ).all()
    return [issue_dict(issue) for issue in issues]


@router.get("/api/v1/imports/{import_id}/sheets/{sheet}")
def get_import_sheet(import_id: str, sheet: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    item = session.get(ImportVersion, import_id)
    if item is None or not item.current_revision_id:
        raise api_error("IMPORT_NOT_FOUND", "导入版本不存在", 404)
    revision = require_spec(session, item.current_revision_id)
    try:
        return sheet_payload(json.loads(revision.data_json), sheet)
    except WorkbookInputError as exc:
        raise api_error(exc.code, str(exc), 404)


@router.get("/api/v1/spec-revisions/{revision_id}")
def get_spec_revision(revision_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    return revision_dict(session, require_spec(session, revision_id))


@router.post("/api/v1/imports/{import_id}/validate")
def validate_import(
    import_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    item = session.get(ImportVersion, import_id)
    if item is None or not item.current_revision_id:
        raise api_error("IMPORT_NOT_FOUND", "导入版本不存在", 404)
    check_expected_revision(item.revision, None, if_match)
    current = require_spec(session, item.current_revision_id)
    data = json.loads(current.data_json)
    project = require_project(session, item.project_id)
    expected = {
        "id": project.id, "code": project.code,
        "plc_brand": project.plc_brand, "plc_series": project.plc_series,
        "plc_model": project.plc_model,
    }
    new_revision = create_revision(
        session, project, item, data, current.sequence + 1,
        validate_spec(data, expected),
    )
    item.revision += 1
    audit(session, project.id, "import.validated", "ImportVersion", item.id, {"revision_id": new_revision.id})
    session.commit()
    return revision_dict(session, new_revision)


@router.patch("/api/v1/imports/{import_id}/cells")
def edit_import_cells(
    import_id: str,
    payload: CellPatchRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    item = session.get(ImportVersion, import_id)
    if item is None or not item.current_revision_id:
        raise api_error("IMPORT_NOT_FOUND", "导入版本不存在", 404)
    current = require_spec(session, item.current_revision_id)
    check_expected_revision(current.revision, payload.expected_revision, if_match)
    try:
        updated = patch_cells(
            json.loads(current.data_json),
            [edit.model_dump() for edit in payload.edits],
        )
    except WorkbookInputError as exc:
        raise api_error(exc.code, str(exc))
    project = require_project(session, item.project_id)
    expected = {
        "id": project.id, "code": project.code,
        "plc_brand": project.plc_brand, "plc_series": project.plc_series,
        "plc_model": project.plc_model,
    }
    new_revision = create_revision(
        session, project, item, updated, current.sequence + 1,
        validate_spec(updated, expected),
    )
    item.revision += 1
    audit(
        session, project.id, "spec.edited", "MachineSpecRevision", new_revision.id,
        {"edits": [edit.model_dump() for edit in payload.edits], "parent_revision_id": current.id},
    )
    session.commit()
    return revision_dict(session, new_revision)


@router.put("/api/v1/spec-revisions/{revision_id}/confirmations/{view}")
def confirm_view(
    revision_id: str,
    view: str,
    payload: ConfirmationRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    revision = require_spec(session, revision_id)
    check_expected_revision(revision.revision, payload.expected_revision, if_match)
    allowed = set(required_review_views(json.loads(revision.data_json)))
    if view not in allowed:
        raise api_error("UNKNOWN_REVIEW_VIEW", "当前 MachineSpec 不包含该审阅视图")
    confirmation = session.scalar(
        select(ReviewConfirmation).where(
            ReviewConfirmation.spec_revision_id == revision.id,
            ReviewConfirmation.view == view,
        )
    )
    if confirmation is None:
        session.add(ReviewConfirmation(
            spec_revision_id=revision.id, view=view, confirmed_by=payload.confirmed_by,
        ))
    else:
        confirmation.confirmed_by = payload.confirmed_by
    revision.revision += 1
    audit(session, revision.project_id, "spec.view_confirmed", "MachineSpecRevision", revision.id, {"view": view})
    session.commit()
    return revision_dict(session, revision)


@router.post("/api/v1/spec-revisions/{revision_id}/warnings/{issue_id}/accept")
def accept_warning(
    revision_id: str,
    issue_id: str,
    payload: WarningAcceptRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    revision = require_spec(session, revision_id)
    check_expected_revision(revision.revision, payload.expected_revision, if_match)
    issue = session.get(ValidationIssue, issue_id)
    if issue is None or issue.spec_revision_id != revision.id:
        raise api_error("ISSUE_NOT_FOUND", "校验问题不存在", 404)
    if issue.severity != "warning":
        raise api_error("ISSUE_NOT_ACCEPTABLE", "只有 warning 可以接受风险")
    issue.resolved = True
    issue.accepted_reason = payload.reason
    revision.revision += 1
    audit(session, revision.project_id, "spec.warning_accepted", "ValidationIssue", issue.id, {"reason": payload.reason})
    session.commit()
    return revision_dict(session, revision)


@router.post("/api/v1/spec-revisions/{revision_id}/lock")
def lock_spec(
    revision_id: str,
    payload: ConfirmationRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    revision = require_spec(session, revision_id)
    check_expected_revision(revision.revision, payload.expected_revision, if_match)
    data = json.loads(revision.data_json)
    issues = session.scalars(
        select(ValidationIssue).where(ValidationIssue.spec_revision_id == revision.id)
    ).all()
    blockers = [item for item in issues if item.severity == "blocker" and not item.resolved]
    warnings = [item for item in issues if item.severity == "warning" and not item.resolved]
    confirmed = {
        item.view for item in session.scalars(
            select(ReviewConfirmation).where(ReviewConfirmation.spec_revision_id == revision.id)
        ).all()
    }
    missing_views = sorted(set(required_review_views(data)) - confirmed)
    if blockers or warnings or missing_views:
        raise api_error(
            "LOCK_GATE_FAILED", "MachineSpec 尚未满足锁定条件", 409,
            action=f"处理 {len(blockers)} 个阻断、{len(warnings)} 个警告并确认视图：{', '.join(missing_views)}",
        )
    snapshot = json.dumps(
        {
            "machine_spec": data, "revision_id": revision.id,
            "content_hash": revision.content_hash,
            "locked_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    artifact = store_bytes(
        session, runtime_settings, snapshot, f"MachineSpec_{revision.id}.json", "application/json",
    )
    locked = session.scalar(
        select(LockedMachineSpec).where(LockedMachineSpec.spec_revision_id == revision.id)
    )
    if locked is None:
        locked = LockedMachineSpec(
            project_id=revision.project_id, spec_revision_id=revision.id,
            content_hash=revision.content_hash, snapshot_artifact_id=artifact.record.id,
            locked_by=payload.confirmed_by,
        )
        session.add(locked)
        session.flush()
    revision.status = "locked"
    revision.revision += 1
    project = require_project(session, revision.project_id)
    project.status = "规格锁定"
    project.current_spec_revision_id = revision.id
    project.revision += 1
    audit(session, project.id, "spec.locked", "LockedMachineSpec", locked.id, {"revision_id": revision.id, "content_hash": revision.content_hash})
    session.commit()
    return {
        "locked": True, "id": locked.id,
        "revision": revision_dict(session, revision),
        "snapshot_artifact_id": locked.snapshot_artifact_id,
    }


@router.get("/api/v1/artifacts/{artifact_id}")
def download_artifact(
    artifact_id: str,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> FileResponse:
    artifact = session.get(SourceArtifact, artifact_id)
    if artifact is None:
        raise api_error("ARTIFACT_NOT_FOUND", "文件工件不存在", 404)
    try:
        path = artifact_path(runtime_settings, artifact)
    except ValueError:
        raise api_error("ARTIFACT_PATH_INVALID", "文件工件路径无效", 500)
    if not path.is_file():
        raise api_error(
            "ARTIFACT_MISSING",
            "文件工件已丢失",
            410,
            action="从原始来源重新上传",
        )
    return FileResponse(
        path,
        media_type=artifact.media_type,
        filename=artifact.original_name,
    )


@router.post("/api/v1/projects/{project_id}/generation-runs", status_code=201)
def create_generation_run(
    project_id: str,
    payload: GenerationRequest,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    project = require_project(session, project_id)
    revision_id = payload.spec_revision_id or project.current_spec_revision_id
    if not revision_id:
        raise api_error("LOCKED_SPEC_REQUIRED", "生成程序前必须先锁定 MachineSpec", 409, action="返回规格审阅并完成锁定")
    revision = require_spec(session, revision_id)
    if revision.project_id != project.id or revision.status != "locked":
        raise api_error("LOCKED_SPEC_REQUIRED", "只能从当前项目已锁定的 MachineSpec 生成程序", 409, action="选择已锁定规格")
    locked = session.scalar(
        select(LockedMachineSpec).where(LockedMachineSpec.spec_revision_id == revision.id)
    )
    if locked is None:
        raise api_error("LOCKED_SPEC_REQUIRED", "规格缺少不可变锁定快照", 409)

    try:
        workspace, repo = workspace_for_project(session, runtime_settings, project.id)
        branch_name = payload.branch_name or f"generated/spec-{revision.sequence}-{new_id()[:8]}"
        validate_branch_name(branch_name)
        existing = session.scalar(
            select(ProgramBranch).where(
                ProgramBranch.workspace_id == workspace.id,
                ProgramBranch.name == branch_name,
            )
        )
        if existing is not None:
            raise api_error("BRANCH_ALREADY_EXISTS", "程序分支已存在", 409, action="使用新的分支名称")
        checkout_branch(repo, branch_name)
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422, action="检查分支名称和本地 Git 环境")

    branch = ProgramBranch(
        workspace_id=workspace.id,
        name=branch_name,
        git_ref=f"refs/heads/{branch_name}",
        status="generating",
    )
    session.add(branch)
    session.flush()
    run = GenerationRun(
        project_id=project.id,
        spec_revision_id=revision.id,
        branch_id=branch.id,
        generator_version=GENERATOR_VERSION,
        status="generating",
    )
    session.add(run)
    session.flush()

    try:
        bundle = generate_bundle(json.loads(revision.data_json))
        control_ir_json = stable_json(bundle.control_ir)
        control_ir = ControlIRRevision(
            project_id=project.id,
            spec_revision_id=revision.id,
            generator_version=GENERATOR_VERSION,
            content_hash=content_hash(control_ir_json),
            data_json=control_ir_json,
        )
        session.add(control_ir)
        session.flush()
        run.control_ir_revision_id = control_ir.id
        run.warnings_json = json.dumps(bundle.warnings, ensure_ascii=False)

        write_files(repo, bundle.files)
        for output_path, file_content in bundle.files.items():
            media_type = "application/json" if output_path.endswith(".json") else "text/plain"
            stored = store_bytes(
                session,
                runtime_settings,
                file_content.encode("utf-8"),
                output_path.rsplit("/", 1)[-1],
                media_type,
            )
            session.add(
                ProgramArtifact(
                    generation_run_id=run.id,
                    path=output_path,
                    kind="test_spec" if output_path == "tests/TestSpec.json" else "generated_source",
                    content_hash=content_hash(file_content),
                    source_artifact_id=stored.record.id,
                )
            )
        test_json = stable_json(bundle.test_spec)
        session.add(
            TestSpecRevision(
                generation_run_id=run.id,
                content_hash=content_hash(test_json),
                data_json=test_json,
            )
        )
        for link in bundle.trace_links:
            session.add(TraceLink(generation_run_id=run.id, **link))

        sha = commit_all(repo, f"Generate FX5U ST from MachineSpec {revision.sequence}")
        branch.base_commit = parent_of(repo, sha)
        branch.head_commit = sha
        branch.status = "clean"
        branch.revision += 1
        program_commit = ProgramCommit(
            branch_id=branch.id,
            git_sha=sha,
            message=f"Generate FX5U ST from MachineSpec {revision.sequence}",
            machine_spec_revision_id=revision.id,
            control_ir_revision_id=control_ir.id,
        )
        session.add(program_commit)
        run.status = "review_ready"
        run.revision += 1
        workspace.revision += 1
        audit(
            session,
            project.id,
            "program.generated",
            "GenerationRun",
            run.id,
            {"branch": branch_name, "generator_version": GENERATOR_VERSION, "git_sha": sha},
        )
        session.flush()
        persist_automated_review(
            session, runtime_settings, run, repeat_count=20
        )
        session.commit()
    except (RepositoryError, OSError, ValueError) as exc:
        session.rollback()
        raise api_error("GENERATION_FAILED", str(exc), 422, action="检查规格内容和本地 Git 环境")
    return generation_dict(session, run)


@router.get("/api/v1/generation-runs/{run_id}")
def get_generation_run(run_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise api_error("GENERATION_RUN_NOT_FOUND", "生成任务不存在", 404)
    return generation_dict(session, run)


@router.get("/api/v1/projects/{project_id}/generation-runs")
def list_generation_runs(
    project_id: str,
    session: Session = Depends(app_session),
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    runs = session.scalars(
        select(GenerationRun)
        .where(GenerationRun.project_id == project_id)
        .order_by(GenerationRun.created_at.desc())
    ).all()
    return [generation_dict(session, item) for item in runs]


@router.get("/api/v1/projects/{project_id}/branches")
def list_project_branches(
    project_id: str,
    session: Session = Depends(app_session),
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    workspace = session.scalar(
        select(ProgramWorkspace).where(ProgramWorkspace.project_id == project_id)
    )
    if workspace is None:
        return []
    branches = session.scalars(
        select(ProgramBranch)
        .where(ProgramBranch.workspace_id == workspace.id)
        .order_by(ProgramBranch.updated_at.desc())
    ).all()
    return [branch_dict(item) for item in branches]


@router.post("/api/v1/projects/{project_id}/branches", status_code=201)
def create_program_branch(
    project_id: str,
    payload: BranchCreateRequest,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    require_project(session, project_id)
    try:
        workspace, repo = workspace_for_project(session, runtime_settings, project_id)
        validate_branch_name(payload.name)
        duplicate = session.scalar(
            select(ProgramBranch).where(
                ProgramBranch.workspace_id == workspace.id,
                ProgramBranch.name == payload.name,
            )
        )
        if duplicate is not None:
            raise api_error("BRANCH_ALREADY_EXISTS", "程序分支已存在", 409)
        checkout_branch(repo, payload.name, payload.base_commit)
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422)
    branch = ProgramBranch(
        workspace_id=workspace.id,
        name=payload.name,
        git_ref=f"refs/heads/{payload.name}",
        base_commit=payload.base_commit,
        head_commit=payload.base_commit,
    )
    session.add(branch)
    workspace.revision += 1
    audit(session, project_id, "program.branch_created", "ProgramBranch", branch.id, {"name": payload.name})
    session.commit()
    return branch_dict(branch)


def branch_repository(
    session: Session,
    settings: Settings,
    branch: ProgramBranch,
) -> tuple[ProgramWorkspace, Any]:
    workspace = require_workspace(session, branch.workspace_id)
    try:
        repo = ensure_repository(settings, workspace.project_id)
        checkout_branch(repo, branch.name)
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422)
    return workspace, repo


@router.get("/api/v1/branches/{branch_id}/files")
def list_branch_files(
    branch_id: str,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    branch = require_branch(session, branch_id)
    _workspace, repo = branch_repository(session, runtime_settings, branch)
    return {"branch": branch_dict(branch), "files": list_files(repo)}


@router.get("/api/v1/branches/{branch_id}/files/{path:path}")
def get_branch_file(
    branch_id: str,
    path: str,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    branch = require_branch(session, branch_id)
    _workspace, repo = branch_repository(session, runtime_settings, branch)
    try:
        content = read_file(repo, path)
    except RepositoryError as exc:
        raise api_error("PROGRAM_FILE_NOT_FOUND", str(exc), 404)
    return {"path": path, "content": content, "branch_revision": branch.revision}


@router.patch("/api/v1/branches/{branch_id}/files/{path:path}")
def update_branch_file(
    branch_id: str,
    path: str,
    payload: ProgramFilePatch,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    branch = require_branch(session, branch_id)
    check_expected_revision(branch.revision, payload.expected_revision, if_match)
    normalized_path = path.replace("\\", "/").lstrip("/")
    if normalized_path in {"generated/ControlIR.json", "tests/TestSpec.json"}:
        raise api_error(
            "IMMUTABLE_GENERATION_BASELINE",
            "Control IR 和 TestSpec 属于不可变生成基线，不能手工编辑",
            409,
            action="修改锁定 MachineSpec 后创建新的生成任务",
        )
    workspace, repo = branch_repository(session, runtime_settings, branch)
    try:
        write_files(repo, {path: payload.content})
    except RepositoryError as exc:
        raise api_error("PROGRAM_FILE_PATH_INVALID", str(exc), 422)
    branch.status = "modified"
    branch.revision += 1
    audit(
        session,
        workspace.project_id,
        "program.file_updated",
        "ProgramBranch",
        branch.id,
        {"path": path, "reason": payload.reason},
    )
    session.commit()
    return {"path": path, "content": payload.content, "branch": branch_dict(branch)}


@router.post("/api/v1/branches/{branch_id}/commits", status_code=201)
def create_program_commit(
    branch_id: str,
    payload: ProgramCommitRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    branch = require_branch(session, branch_id)
    check_expected_revision(branch.revision, payload.expected_revision, if_match)
    workspace, repo = branch_repository(session, runtime_settings, branch)
    if branch.status != "modified":
        raise api_error("NO_PROGRAM_CHANGES", "当前分支没有待提交的修改", 409)
    try:
        sha = commit_all(repo, payload.message, payload.author)
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422)
    commit = ProgramCommit(
        branch_id=branch.id,
        git_sha=sha,
        message=payload.message,
        author=payload.author,
        machine_spec_revision_id=None,
        control_ir_revision_id=None,
    )
    generation = session.scalar(
        select(GenerationRun).where(GenerationRun.branch_id == branch.id)
    )
    if generation is None or not generation.control_ir_revision_id:
        raise api_error(
            "GENERATION_BASELINE_INCOMPLETE",
            "当前分支没有可继承的生成基线",
            409,
        )
    commit.machine_spec_revision_id = generation.spec_revision_id
    commit.control_ir_revision_id = generation.control_ir_revision_id
    session.add(commit)
    session.flush()
    branch.head_commit = sha
    branch.status = "clean"
    branch.revision += 1
    generation.revision += 1
    audit(session, workspace.project_id, "program.committed", "ProgramCommit", commit.id, {"git_sha": sha})
    persist_automated_review(session, runtime_settings, generation, repeat_count=20)
    session.commit()
    return commit_dict(commit)


@router.get("/api/v1/projects/{project_id}/commits")
def list_project_commits(
    project_id: str,
    session: Session = Depends(app_session),
) -> list[dict[str, Any]]:
    require_project(session, project_id)
    workspace = session.scalar(
        select(ProgramWorkspace).where(ProgramWorkspace.project_id == project_id)
    )
    if workspace is None:
        return []
    commits = session.scalars(
        select(ProgramCommit)
        .join(ProgramBranch, ProgramCommit.branch_id == ProgramBranch.id)
        .where(ProgramBranch.workspace_id == workspace.id)
        .order_by(ProgramCommit.created_at.desc())
    ).all()
    return [commit_dict(item) for item in commits]


@router.get("/api/v1/commits/{commit_id}")
def get_program_commit(commit_id: str, session: Session = Depends(app_session)) -> dict[str, Any]:
    commit = session.get(ProgramCommit, commit_id)
    if commit is None:
        raise api_error("PROGRAM_COMMIT_NOT_FOUND", "程序提交不存在", 404)
    return commit_dict(commit)


@router.get("/api/v1/commits/{commit_id}/diff")
def get_program_commit_diff(
    commit_id: str,
    runtime_settings: Settings = Depends(app_settings),
    session: Session = Depends(app_session),
) -> dict[str, Any]:
    commit = session.get(ProgramCommit, commit_id)
    if commit is None:
        raise api_error("PROGRAM_COMMIT_NOT_FOUND", "程序提交不存在", 404)
    branch = require_branch(session, commit.branch_id)
    _workspace, repo = branch_repository(session, runtime_settings, branch)
    try:
        diff = commit_diff(repo, commit.git_sha)
    except RepositoryError as exc:
        raise api_error("REPOSITORY_ERROR", str(exc), 422)
    return {"commit": commit_dict(commit), "diff": diff}


app = create_app()

