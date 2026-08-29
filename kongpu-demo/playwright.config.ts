import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const configDir = dirname(fileURLToPath(import.meta.url));
const apiDir = resolve(configDir, "../services/api");
const dataDir = mkdtempSync(join(tmpdir(), "kongpu-e2e-"));
const databasePath = join(dataDir, "kongpu-e2e.sqlite3").replaceAll("\\", "/");
const apiUrl = "http://127.0.0.1:8010";
const webUrl = "http://127.0.0.1:5174";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 12_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: webUrl,
    channel: "msedge",
    viewport: { width: 1440, height: 1024 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "py -3.12 -m uvicorn kongpu_api.main:app --host 127.0.0.1 --port 8010",
      cwd: apiDir,
      url: `${apiUrl}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        KONGPU_DATA_DIR: dataDir,
        KONGPU_DATABASE_URL: `sqlite:///${databasePath}`,
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174",
      cwd: configDir,
      url: webUrl,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { KONGPU_API_TARGET: apiUrl },
    },
  ],
});
