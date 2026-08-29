from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .artifacts import artifact_path, store_bytes
from .config import Settings, get_settings
from .database import DatabaseRuntime
from .generator import GENERATOR_VERSION, content_hash, generate_bundle, stable_json
from .machine_spec import (
    MachineSpec, WorkbookInputError, generate_workbook, parse_workbook, patch_cells,
    required_review_views, sheet_payload, spec_hash, validate_spec,
)
from .models import (
    AuditEvent, ControlIRRevision, GenerationRun, ImportVersion, LockedMachineSpec,
    MachineSpecRevision, ProgramArtifact, ProgramBranch, ProgramCommit,
    ProgramWorkspace, Project, ReviewConfirmation, SourceArtifact,
    TemplateVersion, TestSpecRevision, TraceLink, ValidationIssue, new_id,
)
from .repository import (
    RepositoryError, checkout_branch, commit_all, commit_diff, ensure_repository,
    list_files, parent_of, read_file, repository_path, validate_branch_name, write_files,
)
from .schemas import (
    BranchCreateRequest, CellPatchRequest, ConfirmationRequest, GenerationRequest,
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


def check_expected_revision(current: int, expected: int | None, etag: str | None = None) -> None:
    requested = expected
    if etag:
        token = etag.strip('\"')
        if token.isdigit():
            requested = int(token)
    if requested is not None and requested != current:
        raise api_error("REVISION_CONFLICT", f"数据已更新，当前版本为 {current}", 409, action="刷新后重新操作")


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
        session.add(
            ProgramCommit(
                branch_id=branch.id,
                git_sha=sha,
                message=f"Generate FX5U ST from MachineSpec {revision.sequence}",
                machine_spec_revision_id=revision.id,
                control_ir_revision_id=control_ir.id,
            )
        )
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
    session.add(commit)
    session.flush()
    branch.head_commit = sha
    branch.status = "clean"
    branch.revision += 1
    audit(session, workspace.project_id, "program.committed", "ProgramCommit", commit.id, {"git_sha": sha})
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

