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

export type ApiError = { code?: string; message?: string; action?: string; location?: unknown };
