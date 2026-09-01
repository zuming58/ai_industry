import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type {
  ApiError,
  AdapterDescriptor,
  AdapterEnvironment,
  AutomatedReviewRun,
  CompileRun,
  GenerationAudit,
  GenerationRun,
  ImportVersion,
  ProgramBranch,
  ProgramCommit,
  ProgramFile,
  Project,
  ReleaseCandidate,
  ReleaseCandidateEvidence,
  ReleaseEvidenceKind,
  SpecRevision,
  SimulationRun,
  MonitoringPlan,
  MonitoringEvidence,
  CandidateVerification,
  CommissioningTask,
  CommitComparison,
  ProjectAcceptanceRun,
  ProjectReadiness,
  RestoreBranchResult,
  ProjectTimeline,
  LocalSettings,
  TemplateVersionHistory,
  CompatibilityMatrix,
  SettingsAuditEvent,
  SimulationScenario,
  SimulationTraceResponse,
} from "../domain";

export const apiClient = createClient<paths>({ baseUrl: "" });

function fileBodySerializer(body: { file: File }) {
  const form = new FormData();
  form.append("file", body.file);
  return form;
}

function evidenceBodySerializer(body: { file: File; evidence_kind: string; expected_revision?: number }) {
  const form = new FormData();
  form.append("file", body.file);
  form.append("evidence_kind", body.evidence_kind);
  if (body.expected_revision !== undefined) form.append("expected_revision", String(body.expected_revision));
  return form;
}

function releaseEvidenceBodySerializer(body: { file: File; evidence_kind: ReleaseEvidenceKind; expected_candidate_revision: number; note?: string }) {
  const form = new FormData();
  form.append("file", body.file);
  form.append("evidence_kind", body.evidence_kind);
  form.append("expected_candidate_revision", String(body.expected_candidate_revision));
  if (body.note) form.append("note", body.note);
  return form;
}

function ensure<T>(result: { data?: unknown; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const error = (result.error || {}) as ApiError;
    const message = error.message || "请求失败（HTTP " + result.response.status + "）";
    throw new Error(error.action ? message + "。" + error.action : message);
  }
  return result.data as T;
}

export const api = {
  async listProjects(includeArchived = false): Promise<Project[]> {
    return ensure(await apiClient.GET("/api/v1/projects", { params: { query: { include_archived: includeArchived } } }));
  },
  async getProject(id: string): Promise<Project> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}", { params: { path: { project_id: id } } }));
  },
  async createProject(payload: { name: string; customer_code?: string; plc_brand: string; plc_series: string; plc_model: string }): Promise<Project> {
    return ensure(await apiClient.POST("/api/v1/projects", { body: payload }));
  },
  async updateProject(project: Project, payload: Partial<Project>): Promise<Project> {
    return ensure(await apiClient.PATCH("/api/v1/projects/{project_id}", {
      params: { path: { project_id: project.id } },
      body: { name: payload.name, customer_code: payload.customer_code, plc_brand: payload.plc_brand, plc_series: payload.plc_series, plc_model: payload.plc_model, expected_revision: project.revision },
    }));
  },
  async archive(project: Project): Promise<Project> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/archive", { params: { path: { project_id: project.id } }, headers: { "If-Match": String(project.revision) } }));
  },
  async restore(project: Project): Promise<Project> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/restore", { params: { path: { project_id: project.id } }, headers: { "If-Match": String(project.revision) } }));
  },
  async currentTemplate(): Promise<Record<string, unknown>> {
    return ensure(await apiClient.GET("/api/v1/template-versions/current"));
  },
  async downloadTemplate(projectId: string, kind: "blank" | "example"): Promise<Blob> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/templates", {
      params: { path: { project_id: projectId }, query: { kind } }, parseAs: "blob",
    }));
  },
  async uploadImport(projectId: string, file: File): Promise<{ import: ImportVersion; revision: SpecRevision }> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/imports", {
      params: { path: { project_id: projectId } }, body: { file } as never, bodySerializer: fileBodySerializer as never,
    }));
  },
  async getImport(id: string): Promise<ImportVersion> {
    return ensure(await apiClient.GET("/api/v1/imports/{import_id}", { params: { path: { import_id: id } } }));
  },
  async downloadImportValidationReport(id: string, kind: "json" | "markdown" | "xlsx"): Promise<Blob> {
    return ensure(await apiClient.GET("/api/v1/imports/{import_id}/validation-report", {
      params: { path: { import_id: id }, query: { kind } },
      parseAs: "blob",
    }));
  },
  async getRevision(id: string): Promise<SpecRevision> {
    return ensure(await apiClient.GET("/api/v1/spec-revisions/{revision_id}", { params: { path: { revision_id: id } } }));
  },
  async patchCells(importId: string, revision: number, edits: Array<{ sheet: string; row: number; column: string; value: unknown }>): Promise<SpecRevision> {
    return ensure(await apiClient.PATCH("/api/v1/imports/{import_id}/cells", {
      params: { path: { import_id: importId } }, body: { expected_revision: revision, edits },
    }));
  },
  async validateImport(importId: string, revision: number): Promise<SpecRevision> {
    return ensure(await apiClient.POST("/api/v1/imports/{import_id}/validate", {
      params: { path: { import_id: importId } }, headers: { "If-Match": String(revision) },
    }));
  },
  async confirmView(spec: SpecRevision, view: string): Promise<SpecRevision> {
    return ensure(await apiClient.PUT("/api/v1/spec-revisions/{revision_id}/confirmations/{view}", {
      params: { path: { revision_id: spec.id, view } }, body: { confirmed_by: "本机工程师", expected_revision: spec.revision },
    }));
  },
  async acceptWarning(spec: SpecRevision, issueId: string, reason: string): Promise<SpecRevision> {
    return ensure(await apiClient.POST("/api/v1/spec-revisions/{revision_id}/warnings/{issue_id}/accept", {
      params: { path: { revision_id: spec.id, issue_id: issueId } }, body: { reason, expected_revision: spec.revision },
    }));
  },
  async lockSpec(spec: SpecRevision): Promise<{ locked: boolean; revision: SpecRevision; snapshot_artifact_id: string }> {
    return ensure(await apiClient.POST("/api/v1/spec-revisions/{revision_id}/lock", {
      params: { path: { revision_id: spec.id } }, body: { confirmed_by: "本机工程师", expected_revision: spec.revision },
    }));
  },
  async listRuns(projectId: string): Promise<GenerationRun[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/generation-runs", { params: { path: { project_id: projectId } } }));
  },
  async generate(projectId: string, specId: string, branchName: string): Promise<GenerationRun> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/generation-runs", {
      params: { path: { project_id: projectId } }, body: { spec_revision_id: specId, branch_name: branchName },
    }));
  },
  async listBranches(projectId: string): Promise<ProgramBranch[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/branches", { params: { path: { project_id: projectId } } }));
  },
  async listFiles(branchId: string): Promise<{ branch: ProgramBranch; files: ProgramFile[] }> {
    return ensure(await apiClient.GET("/api/v1/branches/{branch_id}/files", { params: { path: { branch_id: branchId } } }));
  },
  async getFile(branchId: string, path: string): Promise<{ path: string; content: string; branch_revision: number }> {
    return ensure(await apiClient.GET("/api/v1/branches/{branch_id}/files/{path}", { params: { path: { branch_id: branchId, path } } }));
  },
  async saveFile(branchId: string, path: string, content: string, revision: number): Promise<{ branch: ProgramBranch }> {
    return ensure(await apiClient.PATCH("/api/v1/branches/{branch_id}/files/{path}", {
      params: { path: { branch_id: branchId, path } }, body: { content, reason: "工程师在程序工作区编辑", expected_revision: revision },
    }));
  },
  async commit(branch: ProgramBranch, message: string): Promise<ProgramCommit> {
    return ensure(await apiClient.POST("/api/v1/branches/{branch_id}/commits", {
      params: { path: { branch_id: branch.id } }, body: { message, author: "本机工程师", expected_revision: branch.revision },
    }));
  },
  async listCommits(projectId: string): Promise<ProgramCommit[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/commits", { params: { path: { project_id: projectId } } }));
  },
  async getProjectTimeline(projectId: string): Promise<ProjectTimeline> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/timeline", { params: { path: { project_id: projectId } } }));
  },
  async downloadProjectTimeline(projectId: string, kind: "json" | "markdown"): Promise<Blob> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/timeline/export", {
      params: { path: { project_id: projectId }, query: { kind } },
      parseAs: "blob",
    }));
  },
  async commitDiff(commitId: string): Promise<{ commit: ProgramCommit; diff: string }> {
    return ensure(await apiClient.GET("/api/v1/commits/{commit_id}/diff", { params: { path: { commit_id: commitId } } }));
  },
  async compareCommits(baseCommitId: string, targetCommitId: string): Promise<CommitComparison> {
    return ensure(await apiClient.GET("/api/v1/commits/{base_commit_id}/diff/{target_commit_id}", {
      params: { path: { base_commit_id: baseCommitId, target_commit_id: targetCommitId } },
    }));
  },
  async restoreCommit(commit: ProgramCommit, sourceBranch: ProgramBranch, name?: string): Promise<RestoreBranchResult> {
    return ensure(await apiClient.POST("/api/v1/commits/{commit_id}/restore-branches", {
      params: { path: { commit_id: commit.id } },
      headers: { "If-Match": String(sourceBranch.revision) },
      body: { name: name || null, expected_source_branch_revision: sourceBranch.revision },
    }));
  },
  async listAdapters(): Promise<AdapterDescriptor[]> {
    return ensure(await apiClient.GET("/api/v1/adapters"));
  },
  async getLocalSettings(): Promise<LocalSettings> {
    return ensure(await apiClient.GET("/api/v1/settings"));
  },
  async updateLocalSettings(settings: Partial<LocalSettings["settings"]>, expectedRevision: number): Promise<LocalSettings> {
    return ensure(await apiClient.PATCH("/api/v1/settings", { body: { ...settings, expected_revision: expectedRevision } }));
  },
  async listSettingsAudit(): Promise<SettingsAuditEvent[]> {
    return ensure(await apiClient.GET("/api/v1/settings/audit"));
  },
  async listTemplateVersions(): Promise<TemplateVersionHistory[]> {
    return ensure(await apiClient.GET("/api/v1/template-versions"));
  },
  async getCompatibilityMatrix(): Promise<CompatibilityMatrix> {
    return ensure(await apiClient.GET("/api/v1/compatibility-matrix"));
  },
  async detectAdapter(adapterId: string, projectId?: string): Promise<Record<string, unknown>> {
    return ensure(await apiClient.POST("/api/v1/adapters/detect", { body: { adapter_id: adapterId, project_id: projectId } }));
  },
  async listAdapterEnvironments(projectId: string): Promise<AdapterEnvironment[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/adapter-environments", { params: { path: { project_id: projectId } } }));
  },
  async auditGeneration(runId: string): Promise<GenerationAudit> {
    return ensure(await apiClient.POST("/api/v1/generation-runs/{run_id}/audit", { params: { path: { run_id: runId } } }));
  },
  async getAudit(runId: string): Promise<GenerationAudit> {
    return ensure(await apiClient.GET("/api/v1/generation-runs/{run_id}/audit", { params: { path: { run_id: runId } } }));
  },
  async listAutomatedReviews(projectId: string): Promise<AutomatedReviewRun[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/automated-reviews", { params: { path: { project_id: projectId } } }));
  },
  async getAutomatedReview(reviewId: string): Promise<AutomatedReviewRun> {
    return ensure(await apiClient.GET("/api/v1/automated-reviews/{review_id}", { params: { path: { review_id: reviewId } } }));
  },
  async createAutomatedReview(projectId: string, generationRunId: string, repeatCount: number, expectedGenerationRevision: number): Promise<AutomatedReviewRun> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/automated-reviews", {
      params: { path: { project_id: projectId } },
      headers: { "If-Match": String(expectedGenerationRevision) },
      body: { generation_run_id: generationRunId, repeat_count: repeatCount, expected_generation_revision: expectedGenerationRevision },
    }));
  },
  async listCompileRuns(projectId: string): Promise<CompileRun[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/compile-runs", { params: { path: { project_id: projectId } } }));
  },
  async createCompileRun(projectId: string, generationRunId: string, adapterId: string, expectedGenerationRevision: number): Promise<CompileRun> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/compile-runs", { params: { path: { project_id: projectId } }, body: { generation_run_id: generationRunId, adapter_id: adapterId, expected_generation_revision: expectedGenerationRevision } }));
  },
  async uploadCompileEvidence(runId: string, file: File, evidenceKind = "vendor_report", expectedRevision?: number): Promise<{ id: string; source_artifact_id: string; sha256: string; evidence_kind: string; verification_level: string; compile_run: CompileRun }> {
    return ensure(await apiClient.POST("/api/v1/compile-runs/{run_id}/evidence", {
      params: { path: { run_id: runId } },
      body: { file, evidence_kind: evidenceKind, expected_revision: expectedRevision } as never,
      bodySerializer: evidenceBodySerializer as never,
    }));
  },
  async listSimulationRuns(projectId: string): Promise<SimulationRun[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/simulation-runs", { params: { path: { project_id: projectId } } }));
  },
  async createSimulationRun(projectId: string, generationRunId: string, inputOverrides: Record<string, boolean | number>, maxCycles: number, expectedGenerationRevision: number, scenario: SimulationScenario = { input_schedule: {}, restart_cycles: [], disconnect_cycles: [], cycle_time_ms: 100 }): Promise<SimulationRun> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/simulation-runs", { params: { path: { project_id: projectId } }, body: { generation_run_id: generationRunId, input_overrides: inputOverrides, max_cycles: maxCycles, expected_generation_revision: expectedGenerationRevision, ...scenario } }));
  },
  async getSimulationTrace(runId: string): Promise<SimulationTraceResponse> {
    return ensure(await apiClient.GET("/api/v1/simulation-runs/{run_id}/trace", { params: { path: { run_id: runId } } }));
  },
  async listReleaseCandidates(projectId: string): Promise<ReleaseCandidate[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/release-candidates", { params: { path: { project_id: projectId } } }));
  },
  async createReleaseCandidate(projectId: string, generationRunId: string, expectedGenerationRevision: number): Promise<ReleaseCandidate> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/release-candidates", {
      params: { path: { project_id: projectId } },
      headers: { "If-Match": String(expectedGenerationRevision) },
      body: { generation_run_id: generationRunId, expected_generation_revision: expectedGenerationRevision },
    }));
  },
  async verifyReleaseCandidate(candidate: ReleaseCandidate): Promise<CandidateVerification> {
    return ensure(await apiClient.POST("/api/v1/release-candidates/{candidate_id}/verify", {
      params: { path: { candidate_id: candidate.id } },
      headers: { "If-Match": String(candidate.revision) },
      body: { expected_candidate_revision: candidate.revision },
    }));
  },
  async downloadValidationMaterial(candidateId: string, kind: "json" | "checklist"): Promise<Blob> {
    return ensure(await apiClient.GET("/api/v1/release-candidates/{candidate_id}/validation-material", {
      params: { path: { candidate_id: candidateId }, query: { kind } },
      parseAs: "blob",
    }));
  },
  async downloadEvidenceLedger(candidateId: string, kind: "json" | "markdown"): Promise<Blob> {
    return ensure(await apiClient.GET("/api/v1/release-candidates/{candidate_id}/evidence-ledger", {
      params: { path: { candidate_id: candidateId }, query: { kind } },
      parseAs: "blob",
    }));
  },
  async listReleaseCandidateEvidence(candidateId: string): Promise<ReleaseCandidateEvidence[]> {
    return ensure(await apiClient.GET("/api/v1/release-candidates/{candidate_id}/evidence", {
      params: { path: { candidate_id: candidateId } },
    }));
  },
  async uploadReleaseCandidateEvidence(candidate: ReleaseCandidate, file: File, evidenceKind: ReleaseEvidenceKind, note?: string): Promise<ReleaseCandidateEvidence> {
    return ensure(await apiClient.POST("/api/v1/release-candidates/{candidate_id}/evidence", {
      params: { path: { candidate_id: candidate.id } },
      headers: { "If-Match": String(candidate.revision) },
      body: { file, evidence_kind: evidenceKind, expected_candidate_revision: candidate.revision, note } as never,
      bodySerializer: releaseEvidenceBodySerializer as never,
    }));
  },
  async listAcceptanceRuns(projectId: string): Promise<ProjectAcceptanceRun[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/acceptance-runs", { params: { path: { project_id: projectId } } }));
  },
  async getProjectReadiness(projectId: string, generationRunId?: string): Promise<ProjectReadiness> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/readiness", {
      params: { path: { project_id: projectId }, query: generationRunId ? { generation_run_id: generationRunId } : {} },
    }));
  },
  async createAcceptanceRun(projectId: string, run: GenerationRun, candidateId?: string): Promise<ProjectAcceptanceRun> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/acceptance-runs", {
      params: { path: { project_id: projectId } },
      headers: { "If-Match": String(run.revision) },
      body: { generation_run_id: run.id, release_candidate_id: candidateId || null, expected_generation_revision: run.revision },
    }));
  },
  async downloadArtifact(artifactId: string): Promise<Blob> {
    return ensure(await apiClient.GET("/api/v1/artifacts/{artifact_id}", { params: { path: { artifact_id: artifactId } }, parseAs: "blob" }));
  },
  async listMonitoringPlans(projectId: string): Promise<MonitoringPlan[]> {
    return ensure(await apiClient.GET("/api/v1/projects/{project_id}/monitoring-plans", { params: { path: { project_id: projectId } } }));
  },
  async createMonitoringPlan(projectId: string, candidateId: string, expectedCandidateRevision: number): Promise<MonitoringPlan> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/monitoring-plans", {
      params: { path: { project_id: projectId } },
      headers: { "If-Match": String(expectedCandidateRevision) },
      body: { release_candidate_id: candidateId, expected_candidate_revision: expectedCandidateRevision },
    }));
  },
  async listMonitoringEvidence(planId: string): Promise<MonitoringEvidence[]> {
    return ensure(await apiClient.GET("/api/v1/monitoring-plans/{plan_id}/evidence", { params: { path: { plan_id: planId } } }));
  },
  async createMonitoringSnapshot(plan: MonitoringPlan, values: Record<string, boolean | number>, currentStepId?: string, note?: string): Promise<MonitoringEvidence> {
    return ensure(await apiClient.POST("/api/v1/monitoring-plans/{plan_id}/snapshots", {
      params: { path: { plan_id: plan.id } },
      headers: { "If-Match": String(plan.revision) },
      body: {
        observed_target_fingerprint: plan.target_fingerprint,
        values,
        current_step_id: currentStepId || null,
        note: note || null,
        expected_plan_revision: plan.revision,
      },
    }));
  },
  async createCommissioningTask(evidenceId: string, description: string, expectedPlanRevision: number): Promise<CommissioningTask> {
    return ensure(await apiClient.POST("/api/v1/monitoring-evidence/{evidence_id}/commissioning-tasks", {
      params: { path: { evidence_id: evidenceId } },
      headers: { "If-Match": String(expectedPlanRevision) },
      body: { description, expected_plan_revision: expectedPlanRevision },
    }));
  },
};

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
