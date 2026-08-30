import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
}

test("P01-P06 and P11 complete the real local workflow", async ({ page }) => {
  const projectName = `E2E FX5U ${Date.now()}`;

  await page.goto("/projects");
  await page.getByRole("button", { name: "新建项目" }).click();
  await page.getByLabel("项目名称").fill(projectName);
  await page.getByLabel("客户编号").fill("E2E-CUSTOMER");
  await page.getByRole("button", { name: "保存项目" }).click();
  await expect(page.getByText("项目已创建")).toBeVisible();
  const projectRow = page.getByRole("row").filter({ hasText: projectName });
  await projectRow.getByRole("button", { name: "打开" }).click();

  await expect(page.getByRole("heading", { name: new RegExp(`MachineSpec 模板 · ${projectName}`) })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载完整范例" }).click();
  const template = await downloadPromise;
  const templatePath = await template.path();
  expect(templatePath).toBeTruthy();

  await page.getByRole("link", { name: "P04 导入校验" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "MachineSpec_example.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: readFileSync(templatePath!),
  });
  await expect(page.getByText("Excel 已上传并完成确定性校验")).toBeVisible();
  await expect(page.getByRole("heading", { name: "结构化工作表" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P05 规格审阅" }).click();
  await expect(page.getByRole("heading", { name: "锁定门禁" })).toBeVisible();
  await page.getByRole("button", { name: "锁定规格" }).click();
  await expect(page.locator(".toast--error")).toContainText("MachineSpec 尚未满足锁定条件");
  await expect(page.locator(".toast--error")).toContainText("确认视图");

  while (await page.getByRole("button", { name: /接受：/ }).count()) {
    page.once("dialog", (dialog) => dialog.accept("E2E 自动化复核：接受范例中的非阻断提示"));
    await page.getByRole("button", { name: /接受：/ }).first().click();
    await expect(page.getByText("Warning 已接受并写入审计记录")).toBeVisible();
  }

  const requiredViews = await page.locator(".tab-strip button").allTextContents();
  for (const label of requiredViews) {
    const tab = page.locator(".tab-strip button").filter({ hasText: label.trim() });
    await tab.click();
    const confirmButton = page.getByRole("button", { name: "确认当前视图" });
    if (await confirmButton.isEnabled()) {
      await confirmButton.click();
      await expect(page.getByText(new RegExp(`${label.trim()}已确认`))).toBeVisible();
    }
  }
  await page.getByRole("button", { name: "锁定规格" }).click();
  await expect(page.getByText("MachineSpec 已生成不可变锁定快照")).toBeVisible();
  await expect(page.getByText("locked")).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P06 程序工程" }).click();
  await page.locator(".real-empty").getByRole("button", { name: "生成程序" }).click();
  await expect(page.getByText("已生成确定性 FX5U ST 骨架和 TestSpec")).toBeVisible();
  await expect(page.getByRole("heading", { name: "程序树" })).toBeVisible();
  const editor = page.locator(".code-editor");
  await expect(editor).toHaveValue(/PROGRAM PRG_AutoCycle/);
  await expect(editor).toHaveAttribute("aria-readonly", "false");
  await editor.fill(`${await editor.inputValue()}\n// E2E reviewed change.\n`);
  await page.locator(".code-panel__header").getByRole("button", { name: "保存" }).click();
  await expect(page.getByText("文件已保存到工作分支，尚未提交")).toBeVisible();
  await page.getByLabel("提交说明").fill("E2E review generated program");
  await expect(page.getByRole("button", { name: "创建 Commit" })).toBeEnabled();
  await page.getByRole("button", { name: "创建 Commit" }).click();
  await expect(page.getByText("程序修改已提交到本地 Git 历史")).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P07 编译" }).click();
  await expect(page.getByRole("heading", { name: "项目自动审核与编译准备" })).toBeVisible();
  await expect(page.getByText(/Automated Review v1/)).toBeVisible();
  await expect(page.getByText("确定性重复生成")).toBeVisible();
  await expect(page.getByText("集中外部验证门")).toBeVisible();
  await expect(page.getByText("GX Works3 导入与 Rebuild All")).toBeVisible();
  await page.getByRole("button", { name: "重新运行自动审核" }).click();
  await expect(page.getByText("自动审核输入未变化，已复用不可变报告")).toBeVisible();
  await page.getByRole("button", { name: "创建编译准备任务" }).click();
  await expect(page.getByText("已创建厂商编译准备任务，当前仍为未验证")).toBeVisible();
  await expect(page.getByText("manual_required")).toBeVisible();
  await page.locator('.compile-prep input[type="file"]').setInputFiles({
    name: "gxworks3-manual.log",
    mimeType: "text/plain",
    buffer: Buffer.from("GX Works3 evidence placeholder; no vendor pass claim."),
  });
  await expect(page.getByText("外部证据已按哈希保存，验证等级保持 manual_unverified")).toBeVisible();
  await expect(page.getByText("证据数").locator("..")).toContainText("1");
  await page.reload();
  await expect(page.getByText("确定性重复生成")).toBeVisible();
  await expect(page.getByText("manual_required")).toBeVisible();
  await expect(page.getByText("证据数").locator("..")).toContainText("1");
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P08 模拟" }).click();
  await expect(page.getByRole("heading", { name: "控谱参考逻辑模拟" })).toBeVisible();
  await page.getByRole("button", { name: "运行参考模拟" }).click();
  await expect(page.getByText("控谱参考逻辑模拟已完成；不等同于 GX Simulator3")).toBeVisible();
  await expect(page.getByText(/TestSpec 用例：/)).toBeVisible();
  await expect(page.getByRole("definition").filter({ hasText: "automatic_reference" })).toBeVisible();
  await page.reload();
  await expect(page.getByText(/TestSpec 用例：/)).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P09 发布" }).click();
  await expect(page.getByRole("heading", { name: "交付候选包" })).toBeVisible();
  await page.getByRole("button", { name: "生成交付候选包" }).click();
  await expect(page.getByText("交付候选包已生成；仍需集中外部验证")).toBeVisible();
  await expect(page.getByText("external_validation_required").first()).toBeVisible();
  await expect(page.getByText("automatic_package")).toBeVisible();
  await expect(page.getByText("集中外部验证门")).toBeVisible();
  await expect(page.getByText("GX Works3 导入与 Rebuild All")).toBeVisible();
  await page.getByRole("button", { name: "独立复核 ZIP" }).click();
  await expect(page.getByText("候选 ZIP 已重新读取并通过独立完整性复核")).toBeVisible();
  await expect(page.getByText("passed").first()).toBeVisible();
  await page.getByRole("button", { name: "生成自动验收报告" }).click();
  await expect(page.getByText("项目自动验收完成；厂商、硬件和电气验证仍待集中进行")).toBeVisible();
  await expect(page.getByText("automatic_passed_external_pending").first()).toBeVisible();
  await expect(page.getByText("程序 Commit 与不可变生成基线")).toBeVisible();
  await expect(page.getByText("交付候选包完整性")).toBeVisible();
  const candidateDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 ZIP" }).click();
  const candidateArchive = await candidateDownload;
  expect(await candidateArchive.path()).toBeTruthy();
  await page.getByRole("button", { name: "校验并复用候选包" }).click();
  await expect(page.getByText("不可变输入未变化，已复用交付候选包")).toBeVisible();
  await page.reload();
  await expect(page.getByText("RC-0001").first()).toBeVisible();
  await expect(page.getByText("automatic_passed_external_pending").first()).toBeVisible();
  await page.getByRole("button", { name: "复核并复用验收报告" }).click();
  await expect(page.getByText("自动验收输入未变化，已复用不可变报告")).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P10 监控" }).click();
  await expect(page.getByRole("heading", { name: "只读监控准备" })).toBeVisible();
  await expect(page.getByText("未连接 PLC · 未验证")).toBeVisible();
  await page.getByRole("button", { name: "创建只读监控计划" }).click();
  await expect(page.getByText("只读监控准备计划已创建；尚未连接 PLC")).toBeVisible();
  await expect(page.getByText(/只读变量映射/)).toBeVisible();
  await page.getByLabel("离线变量 JSON").fill("{}");
  await page.getByRole("button", { name: "保存离线快照" }).click();
  await expect(page.getByText("离线快照已按 SHA-256 保存，验证等级保持 manual_unverified")).toBeVisible();
  await expect(page.getByText("未指定等待条件")).toBeVisible();
  await page.getByRole("button", { name: "创建独立调试分支" }).click();
  await expect(page.getByText("已从候选 Commit 创建独立调试分支，发布历史未改写")).toBeVisible();
  await expect(page.getByRole("button", { name: "已创建调试分支" })).toBeDisabled();
  await page.reload();
  await expect(page.getByText("未连接 PLC · 未验证")).toBeVisible();
  await expect(page.getByRole("button", { name: "已创建调试分支" })).toBeDisabled();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: "P11 版本" }).click();
  const baseCommitOption = page.getByLabel("基线 Commit").locator("option").filter({ hasText: "Generate FX5U ST" }).first();
  const targetCommitOption = page.getByLabel("目标 Commit").locator("option").filter({ hasText: "E2E review generated program" }).first();
  const baseCommitValue = await baseCommitOption.getAttribute("value");
  const targetCommitValue = await targetCommitOption.getAttribute("value");
  expect(baseCommitValue).toBeTruthy();
  expect(targetCommitValue).toBeTruthy();
  await page.getByLabel("基线 Commit").selectOption(baseCommitValue!);
  await page.getByLabel("目标 Commit").selectOption(targetCommitValue!);
  await expect(page.locator(".diff-panel")).toContainText("E2E reviewed change");
  await page.getByLabel("恢复分支名").fill("restore/e2e-initial-baseline");
  await page.getByRole("button", { name: "从基线创建恢复分支" }).click();
  await expect(page.getByText(/已创建恢复分支 restore\/e2e-initial-baseline/)).toBeVisible();
  await expect(page.getByText("restore/e2e-initial-baseline", { exact: true })).toBeVisible();
  await expect(page.getByText(/恢复只复制历史源码基线并重新运行自动审核/)).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.setViewportSize({ width: 1366, height: 768 });
  const projectUrl = new URL(page.url());
  const projectId = projectUrl.pathname.split("/")[2];
  for (const route of ["templates", "imports", "review", "program", "compile", "simulation", "release", "monitor", "versions"]) {
    await page.goto(`/projects/${projectId}/${route}`);
    await expect(page.locator("main")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }

  await page.goto("/settings");
  const gxWorksCard = page.locator(".adapter-card-real").filter({ hasText: "MELSOFT GX Works3" });
  await gxWorksCard.getByRole("button", { name: "只读检测环境" }).click();
  await expect(page.getByText("环境快照已更新；检测过程未启动厂商程序")).toBeVisible();
  await expect(gxWorksCard).toContainText(/unavailable|manual_required/);
  await expect(gxWorksCard).toContainText("unverified");
  await expectNoHorizontalOverflow(page);
});

test("unsupported workbook is rejected with a recoverable error", async ({ page, request }) => {
  const response = await request.post("http://127.0.0.1:8010/api/v1/projects", {
    data: { name: `Invalid workbook ${Date.now()}`, customer_code: "E2E-BAD" },
  });
  expect(response.ok()).toBeTruthy();
  const project = await response.json();
  await page.goto(`/projects/${project.id}/imports`);
  await page.locator('input[type="file"]').setInputFiles({
    name: "legacy.xls",
    mimeType: "application/vnd.ms-excel",
    buffer: Buffer.from("not an xlsx workbook"),
  });
  await expect(page.locator(".toast--error")).toContainText(/xlsx|Excel|文件/);
});
