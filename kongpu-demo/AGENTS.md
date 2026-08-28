# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Locked product and visual decisions

- Product name: `控谱`; fixed English descriptor: `PLC ENGINEERING AGENT`.
- Keep two logo forms: a rounded-square application icon and a horizontal in-product lockup made from the small application icon plus HTML-rendered brand text.
- The app icon uses a deep-navy rounded tile with a compact ladder-logic / `K` mark. Keep generous internal padding so it never competes with the Chinese wordmark.
- Homepage direction: serious, clean industrial engineering workspace; deep-navy navigation, cool white work surfaces, one engineering-blue action color, cyan only as a restrained accent.
- Navigation icons use Phosphor on a consistent 24 x 24 optical grid, with uniform stroke weight and rounded active containers. Do not introduce multicolor navigation.
- Desktop-first target is 1440 x 1024. Preserve the dense but readable PLC engineering information hierarchy.
- The homepage visual QA passed and the user authorized continuation on 2026-08-28. Continue the clickable Demo page by page using the homepage as the visual system; P02 is the first approved continuation.
