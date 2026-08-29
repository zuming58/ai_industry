import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type {
  ApiError,
  GenerationRun,
  ImportVersion,
  ProgramBranch,
  ProgramCommit,
  ProgramFile,
  Project,
  SpecRevision,
} from "../domain";

export const apiClient = createClient<paths>({ baseUrl: "" });

function fileBodySerializer(body: { file: File }) {
  const form = new FormData();
  form.append("file", body.file);
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
  async createProject(payload: { name: string; customer_code?: string; plc_model: string }): Promise<Project> {
    return ensure(await apiClient.POST("/api/v1/projects", { body: { ...payload, plc_brand: "三菱电机", plc_series: "MELSEC iQ-F" } }));
  },
  async updateProject(project: Project, payload: Partial<Project>): Promise<Project> {
    return ensure(await apiClient.PATCH("/api/v1/projects/{project_id}", {
      params: { path: { project_id: project.id } },
      body: { name: payload.name, customer_code: payload.customer_code, plc_model: payload.plc_model, expected_revision: project.revision },
    }));
  },
  async archive(id: string): Promise<Project> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/archive", { params: { path: { project_id: id } } }));
  },
  async restore(id: string): Promise<Project> {
    return ensure(await apiClient.POST("/api/v1/projects/{project_id}/restore", { params: { path: { project_id: id } } }));
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
  async commitDiff(commitId: string): Promise<{ commit: ProgramCommit; diff: string }> {
    return ensure(await apiClient.GET("/api/v1/commits/{commit_id}/diff", { params: { path: { commit_id: commitId } } }));
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
