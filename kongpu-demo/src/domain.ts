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
  source_artifact_id?: string | null;
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

export type LocalSettings = {
  schema: "kongpu-settings/v1";
  id: string;
  revision: number;
  settings: {
    model_endpoint: string | null;
    model_name: string | null;
    model_status: string;
    allow_project_context: boolean;
    send_raw_excel: boolean;
    send_generated_artifacts: boolean;
  };
  secret_policy: { api_key_configured: boolean; secret_storage: string; message: string };
  claim_boundary: string;
  updated_at: string;
};

export type TemplateVersionHistory = {
  id: string;
  version: string;
  schema_version: string;
  active: boolean;
  definition: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CompatibilityEntry = {
  profile_id: string;
  target: { brand: string; series: string; model: string };
  program_language: string;
  adapter_id: string;
  vendor_tool: string;
  required_software: string[];
  hardware_prerequisites: string[];
  external_validation_scope: string[];
  machine_spec: string;
  structured_text_generation: string;
  static_audit: string;
  reference_simulation: string;
  vendor_compile: string;
  vendor_simulation: string;
  hardware: string;
  electrical_review: string;
  safety_plc: string;
  claim_boundary: string;
};

export type CompatibilityMatrix = {
  schema: "kongpu-compatibility-matrix/v1";
  entries: CompatibilityEntry[];
  claim_boundary: string;
};

export type SettingsAuditEvent = { id: string; action: string; key: string; changed_keys: string[]; created_at: string };

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
  results: SimulationResults;
  trace_artifact_id?: string | null;
  revision: number;
  trace_count: number;
  created_at: string;
  updated_at: string;
};

export type SimulationScalar = boolean | number;
export type SimulationTestSummary = { total: number; passed: number; failed: number; blocked: number };
export type SimulationResults = {
  status?: string;
  cycles?: number;
  final_step_id?: string | null;
  events?: string[];
  diagnostics?: SimulationDiagnostic[];
  test_summary?: SimulationTestSummary;
  [key: string]: unknown;
};
export type SimulationScenario = {
  input_schedule: Record<string, Record<string, SimulationScalar>>;
  restart_cycles: number[];
  disconnect_cycles: number[];
  cycle_time_ms: number;
};
export type SimulationDiagnostic = {
  code: string;
  severity?: string;
  cycle?: number;
  step_id?: string | null;
  timeout_cycles?: number;
  action?: string;
  detail?: string;
  internal_states?: string[];
};
export type SimulationTrace = {
  cycle: number;
  step_id?: string | null;
  inputs: Record<string, SimulationScalar>;
  outputs: Record<string, SimulationScalar>;
  events: string[];
  entry_condition?: string | null;
  completion_condition?: string | null;
  source?: Record<string, unknown> | null;
  communication?: "connected" | "disconnected" | string;
  internal_state?: Record<string, SimulationScalar>;
};
export type SimulationTraceResponse = {
  simulation_run_id: string;
  engine_version: string;
  verification_level: string;
  traces: SimulationTrace[];
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
  evidence_count: number;
  revision: number;
  reused?: boolean;
  created_at: string;
  updated_at: string;
};

export type ReleaseEvidenceKind =
  | "environment"
  | "vendor_import"
  | "vendor_compile"
  | "vendor_simulation"
  | "hardware_test"
  | "electrical_signoff"
  | "other";

export type ReleaseCandidateEvidence = {
  id: string;
  project_id: string;
  release_candidate_id: string;
  source_artifact_id: string;
  evidence_kind: ReleaseEvidenceKind;
  verification_level: "manual_unverified";
  note?: string | null;
  original_name: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  reused?: boolean;
  candidate?: ReleaseCandidate;
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

export type ProjectReadiness = {
  schema: "kongpu-readiness/v1";
  project: { id: string; code: string; name: string };
  target: { profile_id: string; brand: string; series: string; model: string; vendor_tool: string; adapter_id: string };
  status: "ready_for_external_validation" | "automatic_work_remaining";
  verification_level: "automatic" | "automatic_partial";
  checks: Array<{ id: string; title: string; status: "ready" | "remaining"; detail: string }>;
  summary: { total: number; ready: number; remaining: number; external_pending: number };
  external_validation_gates: ExternalValidationGate[];
  prerequisites: { software: string[]; hardware: string[]; validation_scope: string[] };
  claim_boundary: string;
};

export type CommitComparison = {
  schema: "kongpu-version-comparison/v1";
  base: ProgramCommit;
  target: ProgramCommit;
  same_commit: boolean;
  comparison_hash: string;
  summary: { changed_sections: number; unchanged_sections: number; changed_items: number };
  sections: VersionComparisonSection[];
  source_diff: string;
  diff: string;
  claim_boundary: string;
};

export type VersionComparisonSource = {
  sheet?: string | null;
  row?: number | null;
  column?: string | null;
};

export type VersionFieldChange = {
  field: string;
  before: unknown;
  after: unknown;
};

export type VersionComparisonItem = {
  change: "added" | "removed" | "changed";
  entity_type: string;
  entity_id: string;
  fields: VersionFieldChange[];
  source_before?: VersionComparisonSource | null;
  source_after?: VersionComparisonSource | null;
};

export type VersionComparisonSection = {
  id: string;
  label: string;
  status: "changed" | "unchanged";
  verification_level: string;
  summary: { added: number; removed: number; changed: number; total: number };
  items: VersionComparisonItem[];
  note?: string | null;
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

export type ProjectTimelineEvent = {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  title: string;
  detail: string;
  occurred_at: string;
  author: string;
  request: string;
  tool: string;
  status: string;
  verification_level: string;
  source: Record<string, unknown>;
  payload: Record<string, unknown>;
};

export type ProjectTimeline = {
  schema: "kongpu-project-timeline/v1";
  project_id: string;
  events: ProjectTimelineEvent[];
  summary: { total: number; by_type: Record<string, number>; latest_event_at?: string | null };
  claim_boundary: string;
};

export type ApiError = { code?: string; message?: string; action?: string; location?: unknown };
