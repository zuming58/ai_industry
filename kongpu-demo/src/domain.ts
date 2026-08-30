export type Project = {
  id: string;
  code: string;
  name: string;
  customer_code?: string | null;
  plc_brand: string;
  plc_series: string;
  plc_model: string;
  status: string;
  archived: boolean;
  is_demo: boolean;
  revision: number;
  current_import_id?: string | null;
  current_spec_revision_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type ValidationIssue = {
  id: string;
  code: string;
  severity: "blocker" | "warning" | "suggestion" | "info";
  title: string;
  detail: string;
  sheet?: string | null;
  row_number?: number | null;
  column_name?: string | null;
  entity_id?: string | null;
  resolved: boolean;
  accepted_reason?: string | null;
};

export type Confirmation = { view: string; confirmed_by: string; created_at: string };

export type MachineSpec = {
  project: Record<string, unknown>;
  plc_target: Record<string, unknown>;
  components: Array<Record<string, unknown>>;
  signals: Array<Record<string, unknown>>;
  sequence: Array<Record<string, unknown>>;
  interlocks: Array<Record<string, unknown>>;
  exceptions: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

export type SpecRevision = {
  id: string;
  project_id: string;
  import_id: string;
  sequence: number;
  schema_version: string;
  content_hash: string;
  status: string;
  revision: number;
  data: MachineSpec;
  issues: ValidationIssue[];
  confirmations: Confirmation[];
  required_views: string[];
  created_at: string;
  updated_at: string;
};

export type ImportVersion = {
  id: string;
  project_id: string;
  version: number;
  filename: string;
  status: string;
  revision: number;
  failure_reason?: string | null;
  spec_revision?: SpecRevision | null;
};

export type ProgramBranch = {
  id: string;
  workspace_id: string;
  name: string;
  git_ref: string;
  base_commit?: string | null;
  head_commit?: string | null;
  status: string;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type ProgramFile = { path: string; size_bytes: number; sha256: string };

export type ProgramCommit = {
  id: string;
  branch_id: string;
  git_sha: string;
  message: string;
  author: string;
  machine_spec_revision_id?: string | null;
  control_ir_revision_id?: string | null;
  created_at: string;
};

export type GenerationRun = {
  id: string;
  project_id: string;
  spec_revision_id: string;
  branch_id: string;
  control_ir_revision_id: string;
  generator_version: string;
  status: string;
  warnings: Array<{ code: string; message: string }>;
  revision: number;
  artifacts: Array<{ id: string; path: string; kind: string; content_hash: string }>;
  trace_links: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type AdapterDescriptor = {
  adapter_id: string;
  name: string;
  version: string;
  vendor: string;
  capabilities: Record<string, string>;
  verification_level: string;
};

export type AdapterEnvironment = {
  id: string;
  project_id: string;
  adapter_id: string;
  adapter_version: string;
  status: string;
  verification_level: string;
  fingerprint: string;
  details: Record<string, unknown>;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type AuditFinding = {
  code: string;
  severity: string;
  title: string;
  detail: string;
  file?: string | null;
  line?: number | null;
  entity_id?: string | null;
  source?: Record<string, unknown> | null;
  action: string;
};

export type GenerationAudit = {
  id: string;
  generation_run_id: string;
  audit_version: string;
  input_hash: string;
  program_commit_id?: string | null;
  baseline_scope?: string;
  status: string;
  findings: AuditFinding[];
  summary: { total: number; blocker: number; warning: number };
  report_artifact_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type AutomatedReviewCheck = {
  id: string;
  title: string;
  status: "passed" | "failed";
  severity: string;
  detail: string;
  evidence: Record<string, unknown>;
  action?: string | null;
};

export type ExternalValidationGate = {
  id: string;
  title: string;
  status: "pending_external";
  required_evidence: string;
};

export type AutomatedReviewRun = {
  id: string;
  project_id: string;
  generation_run_id: string;
  program_commit_id: string;
  review_version: string;
  input_hash: string;
  status: "passed" | "blocked";
  verification_level: "automatic";
  repeat_count: number;
  checks: AutomatedReviewCheck[];
  summary: { total: number; passed: number; failed: number; external_pending: number };
  external_validation_gates: ExternalValidationGate[];
  claim_boundary: string;
  report_artifact_id: string;
  report_sha256?: string | null;
  reused?: boolean;
  created_at: string;
  updated_at: string;
};

export type CompileRun = {
  id: string;
  project_id: string;
  generation_run_id: string;
  program_commit_id?: string | null;
  adapter_id: string;
  adapter_environment_id?: string | null;
  status: string;
  verification_level: string;
  diagnostics: Array<Record<string, unknown>>;
  failure_reason?: string | null;
  revision: number;
  evidence_count?: number;
  created_at: string;
  updated_at: string;
};

export type SimulationRun = {
  id: string;
  project_id: string;
  generation_run_id: string;
  program_commit_id?: string | null;
  test_spec_revision_id?: string | null;
  engine_version: string;
  status: string;
  verification_level: string;
  results: Record<string, unknown>;
  trace_artifact_id?: string | null;
  revision: number;
  trace_count: number;
  created_at: string;
  updated_at: string;
};

export type ReleaseCandidate = {
  id: string;
  project_id: string;
  generation_run_id: string;
  program_commit_id: string;
  automated_review_id: string;
  version: string;
  input_hash: string;
  manifest_hash: string;
  manifest: {
    claim_boundary: string;
    external_validation_gates: ExternalValidationGate[];
    baseline: Record<string, unknown>;
    entries: Array<{ path: string; sha256: string; size_bytes: number }>;
    [key: string]: unknown;
  };
  status: "external_validation_required";
  verification_level: "automatic_package";
  package_artifact_id: string;
  package_sha256: string;
  package_size_bytes: number;
  revision: number;
  reused?: boolean;
  created_at: string;
  updated_at: string;
};

export type CandidateVerification = {
  id: string;
  project_id: string;
  release_candidate_id: string;
  input_hash: string;
  status: "passed";
  verification_level: "automatic_integrity";
  checks: Array<{
    id: string;
    title: string;
    status: "passed" | "failed";
    detail: string;
    evidence: Record<string, unknown>;
  }>;
  summary: { total: number; passed: number; failed: number };
  report_artifact_id: string;
  report_sha256?: string | null;
  reused?: boolean;
  created_at: string;
  updated_at: string;
};

export type ProjectAcceptanceRun = {
  id: string;
  project_id: string;
  generation_run_id: string;
  program_commit_id: string;
  automated_review_id: string;
  generation_audit_id: string;
  simulation_run_id: string;
  release_candidate_id?: string | null;
  candidate_verification_id?: string | null;
  input_hash: string;
  status: "automatic_passed_external_pending";
  verification_level: "automatic";
  checks: Array<{
    id: string;
    title: string;
    status: "passed" | "not_applicable";
    detail: string;
    evidence: Record<string, unknown>;
  }>;
  summary: { total: number; passed: number; external_pending: number };
  external_validation_gates: ExternalValidationGate[];
  claim_boundary: string;
  report_artifact_id: string;
  report_sha256?: string | null;
  reused?: boolean;
  created_at: string;
  updated_at: string;
};

export type CommitComparison = {
  base: ProgramCommit;
  target: ProgramCommit;
  same_commit: boolean;
  diff: string;
};

export type RestoreBranchResult = {
  branch: ProgramBranch;
  generation_run: GenerationRun;
  commit: ProgramCommit;
  source_commit: ProgramCommit;
  inherited_results: unknown[];
  verification_boundary: string;
};

export type MonitoringVariable = {
  name: string;
  signal_id: string;
  address?: string | null;
  data_type?: string | null;
  direction?: string | null;
  source: { sheet?: string | null; row?: number | null };
  access: "read_only";
};

export type MonitoringPlan = {
  id: string;
  project_id: string;
  release_candidate_id: string;
  target_fingerprint: string;
  variable_map_hash: string;
  variable_map: MonitoringVariable[];
  status: string;
  verification_level: "unverified";
  access: "read_only";
  evidence_count: number;
  revision: number;
  reused?: boolean;
  created_at: string;
  updated_at: string;
};

export type MonitoringEvidence = {
  id: string;
  project_id: string;
  monitoring_plan_id: string;
  source_artifact_id: string;
  artifact_sha256: string;
  status: "recorded_unverified" | "data_incomplete";
  verification_level: "manual_unverified";
  analysis: {
    current_step_id?: string | null;
    waiting_condition?: string | null;
    condition_values: Record<string, boolean | number>;
    missing_condition_values: string[];
    captured_variable_count: number;
    claim_boundary: string;
    [key: string]: unknown;
  };
  note?: string | null;
  commissioning_task_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type CommissioningTask = {
  id: string;
  project_id: string;
  monitoring_evidence_id: string;
  branch_id: string;
  generation_run_id: string;
  description: string;
  status: "open";
  created_at: string;
  updated_at: string;
};

export type ApiError = { code?: string; message?: string; action?: string; location?: unknown };
