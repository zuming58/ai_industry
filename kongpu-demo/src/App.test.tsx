// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App.tsx";

const apiMock = vi.hoisted(() => ({
  listProjects: vi.fn(),
  getProject: vi.fn(),
  listRuns: vi.fn(),
  listAutomatedReviews: vi.fn(),
  listCompileRuns: vi.fn(),
  listAdapters: vi.fn(),
}));

vi.mock("./api/client", () => ({
  api: {
    listProjects: apiMock.listProjects,
    getProject: apiMock.getProject,
    listRuns: apiMock.listRuns,
    listAutomatedReviews: apiMock.listAutomatedReviews,
    listCompileRuns: apiMock.listCompileRuns,
    listAdapters: apiMock.listAdapters,
  },
  saveBlob: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("real application shell", () => {
  it("loads the persisted project dashboard through the API client", async () => {
    apiMock.listProjects.mockResolvedValue([]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0 } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "工程工作台" })).toBeInTheDocument();
    expect(await screen.findByText("还没有项目")).toBeInTheDocument();
    expect(apiMock.listProjects).toHaveBeenCalledWith(false);
  });

  it("shows an API failure instead of an empty compile workspace", async () => {
    apiMock.getProject.mockResolvedValue({
      id: "project-1",
      name: "审计项目",
      code: "KP-AUDIT",
      plc_brand: "三菱电机",
      plc_series: "FX5U",
      plc_model: "FX5U-32MT/ES",
      status: "规格锁定",
      revision: 1,
    });
    apiMock.listRuns.mockRejectedValue(new Error("生成任务接口不可用"));
    apiMock.listAutomatedReviews.mockResolvedValue([]);
    apiMock.listCompileRuns.mockResolvedValue([]);
    apiMock.listAdapters.mockResolvedValue([]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0 } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/projects/project-1/compile"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("页面数据读取失败")).toBeInTheDocument();
    expect(screen.getByText("生成任务接口不可用")).toBeInTheDocument();
    expect(screen.queryByText("尚无生成物")).not.toBeInTheDocument();
  });
});
