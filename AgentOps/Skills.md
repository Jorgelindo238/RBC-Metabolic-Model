# AgentOps Skills

Reusable workflows and playbooks for recurring development tasks.

## Purpose
This file defines repeatable procedures the coding agent can follow.
A skill is not a policy and not a lesson.
A skill is a reusable way to perform a type of task correctly.

---

## Skill Format

Each skill should answer:
- when to use it
- what to inspect first
- what to change
- how to validate
- what common failure modes to watch for

---

## Skill Registry

### Skill: Sidebar Restructure
When to use:
- changing product navigation
- reorganizing sidebar sections
- moving from query-param navigation to route-backed navigation

Basic flow:
1. inspect current route model
2. inspect current sidebar section config
3. map existing pages to target structure
4. create missing route files
5. update active-state logic
6. validate with type check and browser flow when possible

Validation:
- route files exist
- sidebar renders
- active-state logic works
- old links do not break unexpectedly

---

### Skill: Home Surface Reordering
When to use:
- changing the order of hero, cards, grids, or feature sections on the home surface

Basic flow:
1. inspect shared wrappers first
2. inspect feature-local component second
3. determine where composition is actually controlled
4. make the smallest move at the correct layer
5. verify visually

Validation:
- render order matches requirement
- no other pages regress

---

### Skill: Active Sidebar Highlight Fix
When to use:
- nested route highlighting is wrong

Basic flow:
1. inspect route-to-feature mapping
2. check exact-match handling
3. check prefix-match handling
4. prefer longest valid prefix
5. verify against nested routes

Validation:
- child pages highlight correctly
- section overview pages still work

---

### Skill: FastAPI Router Addition
When to use:
- adding a new API route group

Basic flow:
1. create router module
2. define endpoints
3. register router in main entrypoint
4. verify route is reachable
5. verify response serialization

Validation:
- no 404
- JSON response works
- route appears in API surface

---

### Skill: Scientific Data Response Hardening
When to use:
- returning model, flux, calibration, or scientific arrays through FastAPI

Basic flow:
1. inspect response payload
2. convert numpy-heavy structures
3. avoid leaking non-serializable objects
4. test with real payload shape

Validation:
- no JSON serialization error
- response shape remains useful to frontend

---

### Skill: Authenticated UI Verification
When to use:
- verifying protected routes or signed-in UX

Basic flow:
1. confirm safe authenticated path exists
2. if not, stop and document blocker
3. launch browser verification only after auth path is clear
4. test click-through, routing, active states, key visual behavior

Validation:
- protected routes render in-session
- redirects behave correctly
- features are testable under real auth state

---

### Skill: Calibration Autoresearch Monitoring
When to use:
- following a real autoresearch run

Basic flow:
1. confirm base policy and manifest
2. locate run directory
3. monitor case progress
4. inspect partial artifacts carefully
5. do not overclaim completion before top-level artifacts exist

Validation:
- distinguish:
  - running
  - partial
  - timed_out
  - completed
  - failed

---

### Skill: Timeout-Path Validation
When to use:
- validating time-aware search behavior

Basic flow:
1. run with intentionally tight budget
2. inspect eval summary
3. inspect completed run manifest
4. inspect registry projection
5. inspect decision record
6. inspect memory ledger
7. confirm consistency across all layers

Validation:
- completion status agrees everywhere
- timeout is not misclassified as crash or normal discard

---

### Skill: LangSmith Trace Validation
When to use:
- verifying orchestration observability

Basic flow:
1. run a traced workflow
2. inspect root trace
3. inspect node traces
4. verify important metadata/tags
5. verify node-level usefulness if applicable

Validation:
- root workflow present
- node runs present
- metadata is sufficient for debugging/audit

---

### Skill: Research Calibration Provenance Validation
When to use:
- proving a calibration or registry result end to end
- validating custom-data versus Bordbar/default provenance
- checking that RoBoCop explains setup and result states truthfully

Basic flow:
1. confirm the active dataset mode on the Research page
2. verify calibration inputs, strategy, and provenance fields
3. run or load a completed calibration result
4. inspect the registry or calibration summary for completion state
5. ask RoBoCop one setup question and one result question
6. verify the assistant distinguishes setup-only, running, completed, and failed states

Validation:
- page shows the correct data mode
- result fields match the active dataset and strategy
- RoBoCop answers from structured provenance rather than guessing
- registry and calibration surfaces stay consistent
- if the live backend is blocked, validate the completed scientific result on a fresh backend and then use browser route-mocking only to confirm the UI/provenance handoff

---

### Skill: Flux Analysis Provenance Validation
When to use:
- validating Flux Analysis result interpretation
- proving that RoBoCop understands the active dataset and calibration linkage on Flux pages
- checking that pathway-level answers are grounded in actual flux totals and top signals

Basic flow:
1. inspect the Flux page context builder and provenance helpers first
2. confirm the page exposes dataset mode, calibration linkage, and flux result state
3. run or load a completed flux result
4. ask one provenance question and one result question in RoBoCop
5. verify the assistant distinguishes setup-only, running, completed, and failed states
6. confirm dominant pathway, top flux signals, and fallback provenance line up with the page

Validation:
- Flux page renders normally
- flux result state is explicit
- RoBoCop answers from pathway totals and top flux signals
- Bordbar/default versus custom upload is stated truthfully
- if the backend appears generic, confirm whether the live API process is stale before changing the code again

---

### Skill: Scientific Workspace Redesign
When to use:
- redesigning a research page that already has real scientific outputs
- making a results-heavy surface feel modern without changing its model logic
- improving readability while keeping RoBoCop discreet and contextual

Basic flow:
1. inspect current layout and identify the scientific hierarchy
2. separate setup/provenance, summary, and detail regions
3. use Tailwind and shadcn cards to create clearer visual rhythm
4. keep assistant affordances secondary to the scientific content
5. validate the page in a real browser and confirm the output still reads correctly

Validation:
- the page renders in a cleaner hierarchy
- key metrics and dominant signals are easier to scan
- RoBoCop remains present but not dominant
- scientific outputs still match the underlying payloads

---

### Skill: Research Feature Archival Cleanup
When to use:
- removing a Research module from the active sidebar or overview while keeping its implementation intact
- de-surfacing a page without breaking its direct route or legacy code path
- updating visible product references so archived modules stop looking active

Basic flow:
1. inspect the shared navigation/config source of truth first
2. remove the module from visible sidebar and overview cards
3. keep the route/component wiring intact unless the user asks to delete it
4. update landing-page references and helper text to match the new active surface set
5. validate that the remaining Research navigation still works

Validation:
- archived module no longer appears in active navigation
- other active surfaces remain visible and functional
- direct route can remain reachable if intentionally preserved
- overview copy matches the current active module set

---

### Skill: Monitoring Surface Reorg
When to use:
- reorganizing the Monitoring sidebar and overview around Overview, Bag Repository, Quality Forecast, and Alerts
- hiding a legacy Monitoring RoBoCop placeholder while reserving Hermes as the future messaging gateway
- updating shared monitoring copy so the visible product structure stays consistent

Basic flow:
1. inspect the shared monitoring nav source of truth first
2. remove legacy assistant placeholders from visible navigation
3. keep any future gateway route hidden or clearly marked as planned
4. update the monitoring overview hero, subsection grid, and snapshot cards to match the new structure
5. validate that the sidebar, overview, and hidden gateway copy all agree

Validation:
- Monitoring sidebar shows only the active operational pages
- Overview page reflects the new structure clearly
- hidden future gateway copy stays out of the main nav
- no unrelated Research or shell routes regress

### Skill: Monitoring Overview Command Center
When to use:
- building the Monitoring overview page as a real command center
- turning the overview into a high-signal dashboard with KPI tiles, operational snapshots, and recent activity
- keeping the route cards secondary to the page-level status view

Basic flow:
1. inspect the Monitoring nav and the overview surface theme
2. build a clear hero with command-center language and structural KPIs
3. add operational snapshot cards for repository, forecast, alerts, and future gateway
4. add recent activity or operational trail panels that feel serious, not placeholder-like
5. validate that the active route cards still sit below the command-center content

Validation:
- overview reads like a control tower
- route cards remain visible and coherent below the hero
- Hermes stays framed as the future gateway rather than an active page
- other Monitoring routes are unchanged

---

### Skill: Pathway Visualization Grounding
When to use:
- wiring a pathway network page into RoBoCop
- adding a compact provenance/result summary to a structural map
- keeping a scientific network explorer visually dominant while the assistant remains discreet

Basic flow:
1. inspect the network payload and identify what is actually structural versus inferred
2. bind the page to the shared research context and provenance helpers
3. show compact dataset/calibration/network cues beside the graph
4. keep the assistant surface subtle and grounded in the same snapshot
5. validate both the page and the assistant against the loaded network state

Validation:
- the network page still renders
- the provenance snapshot is visible
- RoBoCop can explain the current research mode and network scale
- the graph remains the visual focus

---

### Skill: Pathway Network Playback Design
When to use:
- turning a static pathway graph into a simulation-aware playback surface
- deciding whether the current SVG renderer is enough or whether a graph library should be introduced
- mapping simulation time series onto nodes and edges

Basic flow:
1. identify the canonical graph source first
2. check whether the pathway data is model-derived or only a visual subset
3. verify what simulation result fields are available for playback
4. choose the rendering engine based on graph scale and interaction needs
5. define node/edge animation rules from concentrations and fluxes
6. keep RoBoCop and provenance secondary to the scientific network itself

Validation:
- graph source matches the model, not just a decorative subset
- time-series data can drive node or edge playback
- the page still reads as a scientific network, not a generic dashboard
- assistant context stays discreet and truthful

---

## Future Skills To Add
- Marketing page polish pass
- Supabase schema rollout validation
- Monitoring-mode page scaffold refinement
- RoBoCop cross-module interpretation validation

---

## Use This File For
- reusable workflows
- repeated procedures
- stable dev playbooks

Do not use this file for one-off tasks or general repo policy.
- For Research replay state, prefer synchronous external-store readers when a page must reflect persisted browser snapshots on first render.
- For Pathway replay work, keep the latest simulation snapshot as the source of truth and surface frame/timepoint plus replay source in RoBoCop before adding richer animation logic.
- For higher-fidelity Pathway graph work, prefer a metabolite/reaction projection from the canonical registry so enzyme identity is visible on the graph instead of being buried in generic edge labels.

### Skill: Pathway Graph Interaction Refinement
When to use:
- improving the readability of an already grounded Pathway graph
- adding node/edge selection and a compact details rail without changing the scientific source
- reducing label collisions on dense scientific maps

Basic flow:
1. keep the canonical graph source and replay projection intact
2. offset labels instead of stacking them directly on top of nodes
3. make node/reaction clicks select an entity and highlight the related neighborhood
4. show the chosen element in a compact details rail beside the graph
5. validate that RoBoCop still fits the page as a secondary lens

Validation:
- graph is still scientifically faithful
- label overlap is reduced
- selection/highlight is obvious but not overwhelming
- the details rail helps interpretation without replacing the network view
- quick-select chips can be used as a fallback when point clicks are dense, and they should mirror the same selected entity summary in the details rail

### Skill: Pathway Compact/Full Overview
When to use:
- adding a compact overview toggle for Pathway Visualization
- surfacing principal bridge metabolites between pathway groups
- keeping a compact summary aligned with the full registry map and replay behavior

Basic flow:
1. derive the compact overview from the canonical registry, not from a separate sketch
2. present one clear bridge metabolite per pathway group, plus a short bridge summary
3. keep the full registry map available as the detailed view and preserve replay/provenance state across the toggle
4. let RoBoCop inherit the same view mode so it can explain either surface truthfully

Validation:
- toggle switches between compact and full views without resetting playback
- compact cards stay readable and identify the principal connector metabolite
- full graph selection and replay still work after switching views
- RoBoCop cues stay aligned with the current view mode

### Skill: Pathway Compact Graph Mode
When to use:
- making compact Pathway mode remain a graph while reducing the displayed network to one principal connector metabolite per pathway group
- adding viewport zoom controls to scientific network playback

Basic flow:
1. derive the compact network from the canonical registry, not a separate hand sketch
2. keep the compact atlas in the side rail, but render the compact view as a reduced graph in the main viewport
3. expose zoom in, zoom out, and reset controls directly on the graph
4. preserve replay, provenance, and RoBoCop context when toggling between compact and full modes

Validation:
- compact mode still renders a graph, not just cards
- the graph can zoom in and out without losing selection or replay state
- the full model toggle still returns to the registry-wide graph cleanly

### Skill: Monitoring Bag Repository Surface
When to use:
- building the Monitoring Bag Repository page as a real inventory workspace
- presenting bag identity, donor metadata, and future monitoring slots without turning the page into CRUD

Basic flow:
1. start with a KPI strip that summarizes inventory state
2. add search and status filters so operators can narrow the bag list quickly
3. render a selectable table of bags with key metadata and state chips
4. show a right-side detail rail for the selected bag with storage context, quality state, and alert/forecast links
5. leave explicit room for linked runs, monitoring events, and future data handoffs

Validation:
- bag selection updates the detail rail
- filters narrow the table without breaking the page shell
- the page stays aligned with Quality Forecast and Alerts as the next Monitoring steps
### Skill: Monitoring Quality Forecast Surface
When to use:
- building the Monitoring Quality Forecast page as a constrained predictive workspace
- inheriting selected Research simulation logic without exposing the full Research simulation UI
- connecting a bag record to extracellular biomarker inputs, projected trajectory, and alert handoff

Basic flow:
1. anchor the page to the selected bag from the Monitoring inventory
2. expose only the limited biomarker inputs needed for operational forecasting
3. derive the forecast from the Monitoring forecast helper and, when present, a shared latest simulation snapshot
4. keep the projection summary, trajectory, and alert handoff visible and easy to scan
5. state clearly what Research capabilities are inherited and what is intentionally excluded

Validation:
- page renders with a clear forecast hierarchy
- selected bag and biomarker inputs remain visible together
- forecast result and trajectory update coherently
- the page stays distinct from the full Research Simulation workspace

### Skill: Monitoring Alerts Triage Surface
When to use:
- building the Monitoring Alerts page as an operational review queue
- deriving alert records from forecast output without turning the page into a rules engine
- keeping biological risk separate from operator workflow state

Basic flow:
1. derive a prioritized queue from forecast projections and bag context
2. expose severity, review window, confidence, and trigger signals in the queue
3. let the user select an alert to inspect its bag context and recommendation
4. keep operator actions local and structurally ready for later persistence
5. provide clear handoffs back to Bag Repository and Quality Forecast

Validation:
- Alerts page renders with a KPI strip and prioritized queue
- selecting an alert updates the detail panel
- workflow status actions change independently from severity
- handoff links to Bag Repository and Quality Forecast are present

### Skill: Monitoring Backend Bag Intake
When to use:
- replacing a client-only Monitoring inventory intake flow with a backend-backed create/read path
- keeping Bag Repository and Quality Forecast aligned on the same persisted bag records
- enforcing server-side duplicate bag protection and separating intake fields from operational defaults

Basic flow:
1. define a canonical intake schema with only true create-time fields
2. expose create and read endpoints in the Monitoring API
3. initialize operational defaults server-side instead of taking them from the form
4. keep localStorage only as a cache or transitional fallback
5. wire Bag Repository creation to the backend and verify Quality Forecast reads the same records

Validation:
- create succeeds from Bag Repository
- duplicate bag IDs are rejected server-side
- created bags are visible in Bag Repository and Quality Forecast
- localStorage is no longer the source of truth
## Monitoring Validation Pattern
- For Monitoring workflow persistence checks, validate both the browser flow and the backend history endpoint.
- When comparing SSR and client-rendered Monitoring pages, prefer deterministic UTC timestamp formatting to avoid hydration mismatches.
- Keep biological risk derivation separate from workflow status overlays when testing operational pages.
