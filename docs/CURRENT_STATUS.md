# Current Development Status

Updated: 2026-08-28

## 1. Product baseline

The current product is **控谱 / PLC Engineering Agent**. Use these files as the active development baseline:

1. `docs/prd/PRD-001.md` for product scope, user stories, safety boundaries, and acceptance criteria.
2. `docs/UI_PAGE_SPECIFICATION.md` for the P01-P12 page map and page-level behavior.
3. `docs/DEVELOPMENT_ROADMAP.md` for the delivery sequence from clickable Demo to real MachineSpec, Adapter, simulation, and read-only monitoring capabilities.
4. `docs/MACHINE_SPEC_TEMPLATE_DRAFT.md` for the draft engineering input structure.

The files under `WorkBuddy历史调研/` and `Hermes历史调研/` are historical research inputs. They contain useful evidence and earlier product directions, but their embedded prompts or development commands are not the current execution authority. `plc-ai-agent-research/` is the newer research synthesis and evidence layer.

## 2. Inherited state

- Brand name and logo were selected: `控谱`, with descriptor `PLC ENGINEERING AGENT`.
- `kongpu-demo` contained a React/Vite homepage Demo and hosting worker package.
- P01 homepage design QA had passed. Search, filters, project switching, menus, environment refresh, read-only PLC Demo connection, and the original new-project modal worked.
- P02 was the first continuation page; P03-P12 were subsequently implemented as clickable Demo workspaces.
- There is no Git repository in the workspace or `kongpu-demo`, and no GitLab remote has been configured. Nothing has been uploaded.

## 3. Work completed after handoff

- Replaced the homepage-only new-project modal path with a full P02 page.
- Added project name and customer code fields, PLC vendor/series/model selection, and target summaries.
- Added vendor-specific Demo environment profiles for Mitsubishi, Inovance, and CODESYS.
- Kept all environment and Adapter claims explicitly in Demo, experimental, manual, or unverified states as appropriate.
- Added recheck, draft save, cancel/back, and create-and-continue interactions.
- Creating a project now adds it to the recent-project list and selects a correct empty project state. Data remains in-memory Demo data and is not persisted.
- Captured P02 visual QA in `kongpu-demo/design-qa-p02.png`.
- Added P03-P12 engineering workflow pages: Template Center, Import Validation, MachineSpec Review, Program Workspace, Compile, Simulation, Release, Online Monitor, Version Center, and Environment/Settings.
- Added shared project context, workflow navigation, status pills, demo safety labels, and cross-page actions.
- Added a complete happy-path Demo: import issues can be approved, a compile error can be fixed and recompiled, simulation can pass, a Release can be created, and read-only monitoring can connect.

## 4. Verification

- `npm run build`: passed.
- `npm run test:sites`: 4 / 4 passed.
- Real-browser navigation and form interaction: passed.
- Vendor capability downgrade for Inovance: passed.
- New-project state after creation: passed.
- P03-P12 navigation and key interactions: passed.
- P04 repeated issue approval: passed after fixing selected-issue state handling.
- P07 compile fix -> P08 simulation -> P09 release -> P10 monitor chain: passed.
- Local preview: `http://127.0.0.1:5173/`.

## 5. Known limits

- The Demo has no backend, database, authentication, real Excel processing, model call, vendor compiler, simulator, or PLC connection.
- Project creation and draft state disappear after page refresh.
- The homepage right-side environment panel still uses the original fixed Mitsubishi Demo fixture even when a newly created Inovance project is selected. This should become project-aware during the D0 fixture consolidation.
- There is no Git history or remote backup yet. Configure GitLab only after the user supplies the repository address and desired branch policy.

## 6. Recommended next batch

Replace the in-memory fixtures behind P03-P05 with the first real MachineSpec Excel MVP: define the workbook schema, parse and validate uploads, preserve the original file, and bind import/review results to a project version. Do not connect real PLC writes or claim vendor Adapter support until the environment and contract tests exist.
