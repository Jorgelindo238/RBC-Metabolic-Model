# Claude Brief: Research, Apple-Inspired Lean UX

## User Request and Scope

The user explicitly asks Claude to review RESEARCH and propose its own
implementation, inspired by Apple: very lean, minimal, clear and easy to use.
This supersedes the old Calibration/Monitoring implementation dispatch.

FIRST deliver an independent, implementable design proposal. Do not apply a
redesign yet. Do not simply endorse Codex's current UI or copy Apple branding.
You may challenge the existing page structure and recommend removing redundant
UI while keeping all scientific functions accessible.

Workspace: `C:/Users/Jorgelindo/Desktop/airbc`.
Current committed baseline: `2a0acecc146a2f6e424d10a93ac4bc6a4c65a99d`, branch
`dev/next-phase`, pushed to GitHub. Inspect actual current files rather than the
older implementation described in this Claude conversation.

## Product and Current Evidence

Scientific desktop/web tool for researchers studying blood-bag/RBC metabolism.
The eventual workflow must accept raw or relative intra-/extracellular metabolite
data, check the observation contract, calibrate allowed Vmax parameters and
inspect trajectories/fluxes with explicit provenance. Do not promise that the
currently incomplete engine can already calibrate arbitrary user datasets.

The seven live local routes are:

- `http://127.0.0.1:3100/research`
- `http://127.0.0.1:3100/research/data-upload`
- `http://127.0.0.1:3100/research/parameter-calibration`
- `http://127.0.0.1:3100/research/simulation`
- `http://127.0.0.1:3100/research/flux-analysis`
- `http://127.0.0.1:3100/research/pathway-visualization`
- `http://127.0.0.1:3100/research/calibration-registry`

Current UI has compact headers/dataset context, real section anchors, collapsed
provenance/legacy controls, a compact/full network view and a small RoBoCop
launcher. This is a baseline, not a design to defend. The current circular
connector layout is display-only; do not treat bridges as kinetic reactions.

Read the first sections of `tasks/fla_current_tasks.md` and `fla_progress_log.md`.
The most recent checkpoint passed501 targeted Python tests,42 Node tests and
TypeScript.16 Research browser cases, six existing Calibration/Monitoring cases
and extra320/390px checks passed locally. This does NOT establish production
deployment, biological validation or unrestricted user-data compatibility.

Useful current visual evidence, if your file/image tools can read it:

- `C:/WINDOWS/TEMP/airbc-research-redesign/after-overview-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/after-data-upload-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/after-parameter-calibration-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/after-simulation-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/after-flux-analysis-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/after-pathway-visualization-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/after-calibration-registry-desktop.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/final-upload-390.png`
- `C:/WINDOWS/TEMP/airbc-research-redesign/final-network-390.png`

Some earlier screenshots precede the final compact-chat polish. Current source
and a fresh permitted UI observation take precedence. Clearly distinguish
screens inspected, source-only findings and unverified assumptions. If browser
or image tools are unavailable, say so; never fabricate a screenshot review.

## Design Direction

Interpret Apple as disciplined hierarchy, restrained chrome, precision,
readability, progressive disclosure and familiar controls. Think a productive
macOS data tool, not a marketing website or an imitation iPhone settings app.

- Propose one strong recommended direction; justify light/dark choice. A short
  alternative is enough. Preserve scientific contrast and meaningful colors.
- One page purpose, one clear title and one primary action. Keep the actual
  task/data visible in the first viewport, including mobile.
- Remove duplicate headings, repeated source/status blocks, placeholder
  counters, verbose instructional copy and unnecessary badges.
- Use open sections, dividers, compact toolbars and tables, not nested cards,
  floating section boxes, giant hero areas, gradients, glass or decorative orbs.
- Define meaningful subsections and distinguish page navigation, view modes,
  workflow status and actions. Do not make static status chips look clickable.
- Stable typography; no viewport-scaled text or negative letter spacing. Use
  existing fonts, Lucide icons and conventional controls. Radius at most8px for
  repeated framed items unless a concrete existing component requires otherwise.
- Favor familiar icon buttons with tooltips, segmented view controls, actual
  form labels, keyboard focus and accessible empty/loading/error/blocked states.
- Keep dense scientific inspection possible: lean does not mean hiding risks,
  stripping necessary units, truncating values or deleting capabilities.
- Keep existing English application labels consistent; write the proposal in
  French. No extra framework, dependency, proprietary font or brand asset.

## Files to Inspect

Shared Research surface, navigation, tokens:

- `apps/web/components/platform/WorkspaceFeatureSurface.tsx`
- `apps/web/components/platform/WorkspaceFeatureContent.tsx`
- `apps/web/components/platform/ResearchSectionNav.tsx`
- `apps/web/components/platform/ResearchDatasetBanner.tsx`
- `apps/web/components/platform/ResearchWorkspaceLanding.tsx`
- `apps/web/components/platform/PlatformHeader.tsx`
- `apps/web/components/platform/PlatformShellWithRoBoCop.tsx`
- `apps/web/lib/platform-navigation.ts`
- `apps/web/app/research.css`, `apps/web/app/globals.css`

Task tools and scientific state boundaries:

- `apps/web/components/features/DataUpload.tsx`
- `apps/web/components/features/CalibrationJourney.tsx`
- `apps/web/components/features/ParameterCalibration.tsx`
- `apps/web/components/features/SimulationWorkspace.tsx`
- `apps/web/components/features/FluxAnalysis.tsx`
- `apps/web/components/features/PathwayVisualization.tsx`
- `apps/web/components/features/pathway/NetworkGraph.tsx`
- `apps/web/contexts/ResearchDatasetProvider.tsx`
- `apps/web/lib/calibration-journey.mjs`
- `apps/web/lib/calibration-lifecycle.mjs`
- `apps/web/e2e/research-workspace.scenarios.mjs`
- `apps/web/e2e/calibration-monitoring.scenarios.mjs`

Read deeper only where needed. Do not restart the scientific history audit.
If relevant UI/product-design/accessibility skills are actually available to
you, read them; no new skill/plugin/dependency installation. The Vmax skill is
scientific context, not permission to run a calibration.

## Invariants

- Preserve routes, dataset identity and history, existing parameter values and
  request payloads, explicit activation checks and preflight restrictions.
- No optimizer/ODE/solver run, model/GEM/stoichiometry/kinetics/J1 changes or
  synthetic scientific results. No scientific default promotion.
- Relative values are not mM. Missing donor, units, compartments, hematocrit or
  initial pools stay missing. Never borrow Bordbar J1 silently for an upload.
- data_valid, engine_compatibility and launch_allowed are distinct. New
  contractual calibration remains blocked when the engine is not qualified.
- Historical reference is preview-only and non-activatable. Do not hide
  ATP/ADP failure, poor EINO fit, assumed units, borrowed geometry or unknown donor.
- Completion is not numerical/biological validation and is not activation.
- Registry is genuinely empty in the reference Supabase project; do not seed
  fake runs, donors, bags, scores or progress to make mockups look populated.
- No Home/Monitoring/account/auth/database/Vercel changes in this proposal.
  Global shell changes, if proposed, must be explicitly scoped to Research.

## Deliverable

Write only `tasks/claude_research_apple_proposal_2026_11_12.md` (new document)
and give a short chat summary. Target150-250 lines, concrete rather than generic.

Include:

1. The highest-impact UX problems with file/page evidence and severity. State
   honestly whether visual inspection was possible.
2. Recommended Research information architecture, route map and subsection
   names. Show where each current function goes; explain any page regrouping.
3. A small design system: colors, typography, spacing, surfaces, icons,
   navigation, controls and desktop/mobile behavior, with explicit tokens.
4. Page-by-page layout and main action for all seven routes, including empty,
   loading, error, blocked and populated states where applicable. Clearly mark
   hypothetical populated-state examples as design specifications, not real data.
5. Two concrete textual wireframes: Data Upload and Calibration. Show how a
   researcher progresses without losing source/units/contract status.
6. Precise component/file implementation plan in2-3 reversible slices; minimal
   optional TSX/CSS excerpts INSIDE the proposal only. State what is deleted,
   simplified, retained and deferred. No code files written at this stage.
7. Acceptance tests: navigation, keyboard/focus,320/390/1440px, no overflow,
   numeric precision, dataset continuity, activation/launch gates, graph modes
   and nonblank content, no invented records and no accidental scientific runs.
8. Risks and genuinely necessary user decisions, with a recommended default.

## Execution Boundary

Read/Grep/Glob and available read-only image/browser observation are allowed.
Write is allowed ONLY for the named proposal Markdown. No code/source edits,
shell/terminal/code execution, tests, new servers, ODEs, optimizers, uploads,
message sending, subagents, installations, git operations or deployment.
Do not use UI controls that start a simulation, calibration or data mutation.
Do not inspect or transmit secrets, credentials, account data or unrelated files.
If a tool needs a new permission, report it rather than changing access.
Stop after delivering the proposal and wait for user/Codex review.
