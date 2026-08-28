# Homepage Design QA

Result: **passed**

## Review target

- Page: P01 / Engineering workspace homepage
- Desktop viewport: 1440 x 1024 target
- Selected source: `design-reference-homepage.png`
- Current build capture: `design-qa-homepage.png`
- Side-by-side review: `design-qa-comparison.png`

## Visual comparison

- Preserved the selected first direction: deep-navy left navigation, white engineering surfaces, strong blue primary action, active-project overview, recent-project table, and a dedicated local-environment rail.
- Applied the locked `控谱` identity with the rounded application icon and a compact horizontal wordmark.
- Replaced generic white navigation glyphs with a consistent Phosphor 24 x 24 icon system. All inactive icons use one muted navy scale; the active item uses one engineering-blue treatment.
- Reduced decorative noise while improving hierarchy through tighter typography, restrained shadows, precise borders, uniform radii, and clearer status colors.
- Homepage content fits the target desktop view without clipped controls or overlapping regions.

## Interaction checks

- New-device-project modal opens, validates the project name, and closes or submits correctly.
- Recent-project rows switch the current-project summary.
- Search and stage filters update the recent-project table.
- Header notification and user menus open.
- Project action menu opens and returns demo feedback.
- GX Works3 / GX Simulator3 actions return adapter feedback.
- Local-environment refresh displays a loading state and updates the check time.
- PLC connection toggles a clearly labeled read-only monitoring demo state and never claims to write or download a PLC program.
- Navigation items outside P01 acknowledge the click without creating unapproved pages.

## Engineering checks

- `npm run build`: passed.
- `npm run test:sites`: 4 / 4 passed.

## P03-P12 workflow QA

- P03-P12 all have reachable pages through the workflow navigation and sidebar mappings.
- P03 worksheet preview switches between required and optional sheets; template download buttons provide feedback and P03 links to P04.
- P04 displays blocking and warning issues, supports repeated single-item approval, unlocks P05 only after blocking errors reach zero, and preserves the simulated original upload boundary.
- P05 supports eight review views, per-view confirmation, progress tracking, and MachineSpec locking before P06.
- P06 exposes a program tree, ST/TestSpec preview, requirement traceability, regeneration feedback, Commit feedback, and P07 handoff.
- P07 demonstrates vendor diagnostic failure, controlled fix approval, recompile, and P08 handoff after passing.
- P08 demonstrates normal/exception TestSpec execution, live step/signal state, waveform/trace display, passing assertions, and P09 handoff.
- P09 demonstrates release readiness, MANIFEST/package contents, approval, and separate read-only monitoring handoff without PLC download.
- P10 demonstrates safe read-only connection state, watch list, Trace, Agent analysis, evidence saving, and modification-branch creation.
- P11 demonstrates timeline, version comparison, diff preview, and restore-as-new-branch behavior.
- P12 demonstrates local tools, Adapter status, model/data policy, template versions, compatibility matrix, and returns to the homepage correctly.
- Browser checks at 1408 x 762 found no horizontal overflow on P03, P04, P05, P06, P07, P08, P09, P10, P11, or P12.
- `npm run build`: passed after the full workflow implementation.
- `npm run test:sites`: 4 / 4 passed after the full workflow implementation.
- Production assets and Sites runtime packaging are present.
- Browser console capture showed no application JavaScript error.

## P02 continuation QA

- Page: P02 / New Project and Target Environment.
- Added real navigation from the homepage into the full-page setup flow and back.
- Project name, optional customer code, PLC vendor, series, and model are interactive. Vendor changes update the target summary and environment profile together.
- Environment results are explicitly labeled as Demo data. Mitsubishi, Inovance, and CODESYS use different capability states; unverified AutoShop capabilities are not presented as supported.
- Recheck, save-draft, cancel, and create actions return visible feedback. Creating a project inserts it into the recent-project list and resets project statistics to the new-project state.
- Browser inspection at 1408 x 762 found no horizontal overflow or overlapping controls. The page scrolls vertically at this shorter height and is sized to fit the locked 1440 x 1024 desktop target.
- QA capture: `design-qa-p02.png`.
- `npm run build`: passed.
- `npm run test:sites`: 4 / 4 passed.
