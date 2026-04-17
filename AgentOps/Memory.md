# AgentOps Memory

Persistent lessons, repeat failure patterns, preventive rules, and important reminders.

## Purpose
This file stores what the coding agent should remember across sessions:
- mistakes that repeat
- useful prevention rules
- important repo-specific reminders
- patterns that save time or prevent regressions

---

## High-Value Persistent Lessons

### 1. Verify before declaring success
- Symptom:
  - implementation sounds correct but was not actually validated
- Rule:
  - never declare a task complete without the most direct verification that is realistically available
- Prevention:
  - always state clearly what was:
    - proven
    - partially proven
    - inferred

### 2. Authentication is a first-class dependency
- Symptom:
  - UI verification blocked by redirect to `/sign-in`
- Rule:
  - before promising authenticated Playwright/browser verification, confirm a safe auth path exists
- Prevention:
  - check for:
    - disposable test credentials
    - stored auth state
    - documented bypass
    - safe pre-auth session flow

### 3. Route-backed navigation is required for real platform structure
- Symptom:
  - query-param navigation made sidebar restructuring fragile
- Rule:
  - use real App Router pages for serious information architecture
- Prevention:
  - do not keep major product structure trapped behind `?feature=` patterns

### 4. Keep components small
- Symptom:
  - large components become hard to reason about and break easily
- Rule:
  - do not allow large UI components to sprawl
- Prevention:
  - split into sub-components and wrappers before complexity grows

### 5. Scientific core must not be duplicated
- Symptom:
  - temptation to copy `streamlit_app/core` logic into API routes
- Rule:
  - never duplicate scientific core files just to expose them in FastAPI
- Prevention:
  - import through stable boundaries and shims

### 6. Numpy-heavy outputs need serialization discipline
- Symptom:
  - FastAPI responses fail JSON serialization
- Rule:
  - scientific responses must be converted to JSON-safe structures
- Prevention:
  - always use serialization helpers before returning data

### 7. New fields should be additive
- Symptom:
  - extended contracts can break downstream consumers
- Rule:
  - when evolving manifests, registry payloads, or decision records, prefer additive optional fields
- Prevention:
  - preserve old consumer expectations where possible

### 8. Timeout is not the same as failure
- Symptom:
  - a timed-out run can be misread as a bad scientific candidate
- Rule:
  - distinguish:
    - completed
    - partial
    - timed_out
    - crashed
- Prevention:
  - preserve runtime, coverage, and completion status across all artifacts

### 9. Mutation engines should improve through bounded structure
- Symptom:
  - direct coupling to external engines creates architecture mismatch
- Rule:
  - keep RoBoCop in control and use bounded mutation layers
- Prevention:
  - improve the native candidate generator before introducing external mutation engines

### 9b. Overnight autosearch should advance bounded policy state, not scientific core files
- Symptom:
  - a single bounded search iteration is too weak to capture the useful “run it overnight and inspect in the morning” autoresearch pattern
- Rule:
  - keep the LangGraph cycle bounded, but wrap it in a session loop that promotes `Keep` candidates as the next base policy
- Prevention:
  - use a session-level CLI loop rather than mutating scientific source files directly
  - persist a session summary JSON for the whole run
  - keep the promotion step confined to generated policy/manifest artifacts

### 10. LangSmith root traces are not enough forever
- Symptom:
  - root trace exists but node-level observability is weak
- Rule:
  - when orchestration matters, enrich node-level traces too
- Prevention:
  - attach meaningful metadata per node when stable enough

### 11. RoBoCop module context pattern
- Symptom:
  - Need to make RoBoCop useful across multiple research modules
- Rule:
  - Create module-specific context contracts that extend a base interface
- Prevention:
  - Define `BaseModuleContext` with common fields
  - Each module implements its own context (e.g., `SimulationContext`)
  - Interpretation service receives typed context, not raw data

### 12. Grounded interpretation over generic fluff
- Symptom:
  - AI interpretations that ignore actual data
- Rule:
  - Always ground interpretations in specific observations from the module output
- Prevention:
  - Include `grounding` field with dataSource and keyObservations
  - Generate insights from actual trends, not imagination
  - Set confidence based on data quality, not model capability

### 13. LLM-based chat needs structured context contracts
- Symptom:
  - LLM responses become generic without proper context
- Rule:
  - Always provide structured module context to LLM chat endpoints
- Prevention:
  - Define typed context contracts for each module type
  - Include inputs, outputs, and summary metrics
  - Reference context parts in responses for grounding

### 14. Research-wide chat architecture requires module abstraction
- Symptom:
  - Chat implementation becomes module-specific and hard to reuse
- Rule:
  - Create shared chat UI and module-specific context builders
- Prevention:
  - Separate concerns: UI is shared, context is module-specific
  - Use TypeScript interfaces to enforce context structure
  - Make backend endpoint generic over context type

### 15. Floating assistants need context providers, not props
- Symptom:
  - Passing context through many component layers becomes unwieldy
- Rule:
  - Use React context providers for global UI elements like floating assistants
- Prevention:
  - Create a context provider at the shell level
  - Individual pages set context, global components consume it
  - Avoid prop drilling for cross-cutting concerns

### 16. Discreet UI requires careful visual hierarchy
- Symptom:
  - Floating elements can interfere with main content
- Rule:
  - Keep floating assistants subtle and non-intrusive by default
- Prevention:
  - Use collapsed/expanded states
  - Position away from main content areas
  - Add backdrop blur and transparency for premium feel
  - Ensure easy dismiss/collapse behavior

### 17. OpenAI integration needs graceful fallbacks
- Symptom:
  - LLM responses fail when API key is missing or invalid
- Rule:
  - Always provide rule-based fallbacks when external services are unavailable
- Prevention:
  - Check service configuration before attempting API calls
  - Implement clear error messages for missing configuration
  - Keep rule-based responses as backup for development

### 18. LLM prompts must include structured context
- Symptom:
  - Generic LLM responses without grounding in actual data
- Rule:
  - Always inject full structured context into LLM prompts
- Prevention:
  - Serialize context objects as JSON in prompts
  - Include module-specific instructions in system prompts
  - Reference specific data points in responses

### 19. Upload parsing is not dataset activation
- Symptom:
  - the UI accepts a file, previews it, and maps metabolites, but downstream workflows still behave as if Bordbar/default data is active
- Rule:
  - treat upload, validation, and activation as separate steps
- Prevention:
  - only mark a custom dataset active after a shared research-level switch is set
  - keep Bordbar/default as the fallback until activation succeeds

### 20. One research dataset must drive every module
- Symptom:
  - calibration or simulation can drift onto different data assumptions if each page decides independently
- Rule:
  - route calibration, simulation, and later research modules through one shared active dataset decision
- Prevention:
  - store `ResearchDataMode` and `ActiveResearchDataset` at the research shell level
  - pass the same context into all module-specific builders

### 21. Orchestration should expose the active data mode
- Symptom:
  - LangGraph / LangSmith traces show the workflow, but not whether the run used Bordbar/default or custom uploaded data
- Rule:
  - carry the active data mode into trace metadata and tags
- Prevention:
  - include dataset mode and dataset identity in the shared orchestration state
  - make the mode visible in trace metadata so runs are explainable later

### 22. Canonical calibration core is `src/MM_calibration.py`
- Symptom:
  - the repo contains both legacy `streamlit_app/core/parameter_calibration.py` and the active benchmark/eval calibration path
- Rule:
  - treat `src/MM_calibration.py` as the authoritative calibration core for the current product and benchmark flow
- Prevention:
  - use `scripts/run_calibration_eval.py` and the calibration harness as the reference path
  - treat Streamlit calibration code as legacy unless a live product route explicitly depends on it
  - treat the FastAPI calibration route as an adapter until it is explicitly reconciled with the canonical core

### 23. Simulation becomes dataset-aware by seeding from the active upload
- Symptom:
  - mode metadata alone is not enough if the solver still seeds from Bordbar/reference initial conditions
- Rule:
  - when a custom dataset is active, overlay its mapped first-timepoint values onto the solver seed and report the applied/fallback state explicitly
- Prevention:
  - keep Bordbar/reference initial conditions as the fallback seed
  - surface `dataset_applied`, `dataset_applied_metabolites`, and `dataset_fallback_reason` in the simulation response
  - use an isolated smoke-test API when the existing dev process on 8000 is stale so validation reflects the current code

### 24. Historical ledgers need an explicit action handoff
- Symptom:
  - a registry page can feel like a dead end if it only shows history and never points to the next operational step
- Rule:
  - when a page is primarily evidence-first, include a clearly labeled transition into the action workspace
- Prevention:
  - add a visible calibration handoff on the Calibration Registry so uploaded custom data can move from ledger review into the calibration run without hunting through hidden routes

### 25. Calibration time grids must respect the solver window
- Symptom:
  - custom uploaded datasets can include time points earlier than the calibration solver's start day and trigger `t_eval` outside `t_span`
- Rule:
  - only pass experimental time points that fall inside the supported calibration window
- Prevention:
  - filter custom calibration inputs to the `[1, t_max]` window before building the objective
  - keep the Bordbar/reference flow unchanged for the default case

### 25b. Strategy racing should learn only from full physiological verdicts
- Symptom:
  - a candidate can win on calibration fit or report-level triage while still failing the true pure-ODE replay
- Rule:
  - do not warm-start strategy memory or select a race winner from partial evidence alone
- Prevention:
  - run the pure ODE replay before scoring strategy-race winners
  - compute `combined_triage` before persisting memory hits
  - treat report-only wins as incomplete evidence

### 25c. Pure-ODE reruns need isolated artifacts
- Symptom:
  - direct reuse of `src/main.py` global output folders creates collisions between web runs, worker jobs, and historical artifacts
- Rule:
  - every web/worker rerun must write isolated `all_metabolites.csv` and `reaction_fluxes.csv` artifacts
- Prevention:
  - use a temp or run-scoped output folder for replay artifacts
  - never let product-plane calibration runs overwrite canonical simulation folders

### 25d. Production UI and production worker are separate milestones
- Symptom:
  - the calibration surface can be visibly deployed in `web` while the worker-backed orchestration is still unavailable behind the proxy
- Rule:
  - distinguish:
    - UI deployed
    - proxy configured
    - worker reachable
    - end-to-end orchestration live
- Prevention:
  - verify `/api/calibration/*` from the production web domain after every deploy
  - do not claim worker-backed calibration is live until `CALIBRATION_API_BASE_URL` and `CALIBRATION_API_SHARED_SECRET` are set and the worker responds

### 25e. Teacher-flux rescue should stay bounded to supported reactions
- Symptom:
  - a generic rescue loop can overpromise universality while only a subset of reactions have explicit reconstruction logic
- Rule:
  - expose teacher-flux rescue only for reactions with a clear teacher curve / balance contract
- Prevention:
  - keep the supported set explicit (`VEGLC`, `VELAC`, `VLDH`)
  - return structured `skipped` results rather than inventing pseudo-teacher targets

### 26. Registry pages must surface active dataset state
- Symptom:
  - the user uploads custom data, navigates to Calibration Registry, and assumes the upload was lost because the registry page only shows historical records
- Rule:
  - evidence-first pages still need a visible active-dataset indicator when the page is part of a cross-step workflow
- Prevention:
  - show the current research dataset label and mode directly in the registry hero or header
  - keep the registry honest about Bordbar/default versus custom upload state instead of relying on the user to infer it from other pages

### 27. Research dataset state should restore from persisted storage on client init
- Symptom:
  - a custom upload exists in browser storage, but navigation to a different Research page still shows the Bordbar fallback until the provider happens to refresh
- Rule:
  - the active research dataset should be read from persisted browser storage as the provider initializes on the client
- Prevention:
  - treat browser storage as the canonical cross-page state source for the current tab
  - avoid provider bootstrap patterns that depend on a delayed refresh event to become correct

### 28. Hydration-safe persisted state needs a stable server snapshot
- Symptom:
  - a client-only dataset read makes the server render Bordbar/default while the browser immediately renders the custom dataset, causing hydration mismatch
- Rule:
  - if a Research surface depends on persisted browser state, expose it through a hydration-safe subscription with a stable server snapshot
- Prevention:
  - use `useSyncExternalStore` or an equivalent hydration-safe store pattern
  - render the same fallback snapshot on the server and on the initial client hydration pass
  - only let the persisted custom dataset appear after React has reconciled the client store

### 29. Calibration results must be persisted separately from the dataset
- Symptom:
  - the simulation can know the active dataset mode, but still misses the latest optimized ODE parameters after a successful calibration
- Rule:
  - keep the active dataset identity and the latest successful calibration snapshot as separate persisted research states
- Prevention:
  - persist the latest successful calibration result with its source dataset id and optimized parameter map
  - only inject those parameters into simulation when the calibration snapshot matches the active dataset context
  - surface the parameter source explicitly so the UI and RoBoCop can explain whether the ODE used provided, auto-loaded, or default parameters

### 30. RoBoCop must mirror simulation provenance, not just result values
- Symptom:
  - the simulation can be dataset-aware while the assistant still explains it like a generic Bordbar run
- Rule:
  - always thread data mode, active dataset label, dataset fallback, calibration source, and calibrated-parameter state into RoBoCop context
- Prevention:
  - keep summary cards and chat grounding aligned with the actual run provenance
  - do not let the assistant guess whether Bordbar or custom uploads were used

### 31. Smoke tests should prove the full chain, not just the first hop
- Symptom:
  - a route or page can look correct until the live POST and assistant response are checked together
- Rule:
  - validate the custom dataset flow through simulation, then through RoBoCop chat, before calling the work done
- Prevention:
  - confirm the simulation POST, the returned provenance fields, and the chat response in the same smoke path
  - keep one concise end-to-end script handy when the browser UI is flaky

### 32. Calibration UI can underrepresent the canonical parameter space
- Symptom:
  - the page only offers `vmax` and `km` toggles even though the scientific core knows about broader parameter classes and staged scopes
- Rule:
  - treat the UI parameter list as an adapter surface, not as the source of truth
- Prevention:
  - keep the canonical taxonomy in `src/MM_calibration.py` as the reference
  - expose parameter classes / scopes through a dedicated adapter if the UI needs to grow
  - do not assume the bounded autosearch mutation space is the same thing as the calibration parameter space

### 33. Agentic search mutates strategy knobs unless explicitly widened
- Symptom:
  - RoBoCop bounded autosearch changes optimization strategy and run-level budget knobs, but not the kinetic parameters exposed in calibration
- Rule:
  - separate run-policy mutation from scientific parameter selection
- Prevention:
  - when reasoning about “what the agent can optimize,” check the mutation policy and candidate generator, not only the calibration page
  - surface parameter-selection evidence explicitly if the UI or RoBoCop is expected to explain it

### 33b. Parent-guided multi-field mutations must be reduced to effective changes
- Symptom:
  - a proposal can look like a real multi-field mutation while one or more fields are already equal to the current base policy
- Rule:
  - only score and archive the fields that actually change the candidate policy
- Prevention:
  - filter proposed mutations against `base_run` before writing candidate notes, significance, and promotion logic
  - if every field collapses to the current value, treat the proposal as a no-op instead of a fake mutation

### 33c. Extracellular calibration should not silently widen back to all metabolites
- Symptom:
  - `glycolysis_extracellular` calibration can look profile-aware while the primary objective still falls back to all supported metabolites, weakening EGLC/ELAC pressure
- Rule:
  - keep the primary objective aligned with the intended extracellular/glycolysis/energy anchor set when that profile is selected
- Prevention:
  - resolve a scoped primary target list for `glycolysis_extracellular` instead of broadening to the full measured metabolite set
  - when custom/uploaded targets are provided, intersect them with each pathway-phase target group so a large target list does not erase the phase structure

### 33d. Extracellular Vmax anchoring benefits from a narrow Km follow-up, not a broad Km sweep
- Symptom:
  - once EGLC/ELAC are anchored well, a broad Km stage can be slow and may not recover the coupled `GLC` / `LAC` shape efficiently
- Rule:
  - after a successful extracellular Vmax anchor, prefer a narrow phase-1 Km refinement on transport and lactate/glucose-shape parameters first
- Prevention:
- seed from the Vmax-anchored result
- start with `km_GLC_transport`, `km_EGLC`, `km_LAC`, `km_PYR`, `km_GLC_HK`, `km_NADH_NAD`, and `km_NAD_NADH`
- only widen the Km scope if that narrow pass stalls

### 33e. If a micro follow-up reproduces the same retained solution, stop squeezing that subspace
- Symptom:
  - a second tiny follow-up on `vmax_VLDH`, `km_PYR`, `km_LAC`, `km_NADH_NAD`, and `km_NAD_NADH` can simply return the same retained solution as the previous narrow Km refinement
- Rule:
  - treat an unchanged retained solution as a local-optimum signal, not as a cue to keep rerunning the same microscopic search
- Prevention:
  - compare the retained metrics and parameter values to the seeded result
  - if they are effectively identical, change the hypothesis or widen to a nearby but different coupled subsystem instead of repeating the same LDH-local pass

### 33f. Lower-glycolysis rescue can improve ATP and extracellular anchors while breaking PEP/PYR
- Symptom:
  - a focused probe on `vmax_VPGM`, `vmax_VENOPGM`, `vmax_VDPGM`, and `vmax_V23DPGP` can materially improve total fit loss, `P3G`, `ATP`, `AMP`, `IMP`, `LAC`, `EGLC`, and `ELAC`, but at the cost of a large `PEP` / `PYR` regression
- Rule:
  - treat lower-glycolysis rescue as a coupled tradeoff, not a free improvement
- Prevention:
  - compare `P3G`, `P2G`, `PEP`, and `PYR` together whenever `VPGM` / `VENOPGM` / `VDPGM` / `V23DPGP` are moved
  - if `PEP` or `PYR` blow up, follow with a coupled buffering hypothesis around `VPK`, `VLDH`, or `km_PEP` / `km_PYR` instead of locking in the lower-glycolysis move blindly

### 33g. Coupled buffering can rescue PEP while pushing the distortion downstream
- Symptom:
  - adding `vmax_VPK`, `vmax_VLDH`, `km_PEP`, and `km_PYR` to the lower-glycolysis probe can recover `PEP` strongly and keep ATP/extracellular gains, but `PYR` and `B23PG` can become the new distortion sink
- Rule:
  - treat downstream buffering as redistribution, not guaranteed resolution
- Prevention:
  - compare `PEP`, `PYR`, and `B23PG` together after any buffered lower-glycolysis follow-up
  - if `PEP` improves while `PYR` or `B23PG` blow up, move the next hypothesis toward pyruvate/lactate handling or phase coupling rather than adding more lower-glycolysis freedom

### 33h. A narrow downstream recovery set can simply reproduce the buffered seed
- Symptom:
  - once the buffered candidate is established, letting only `vmax_VLDH`, `km_PYR`, `km_LAC`, and a tightly bounded `vmax_VPK` move can converge back to exactly the same retained solution
- Rule:
  - if a narrow downstream recovery pass reproduces the buffered seed, stop searching that same tiny recovery pocket
- Prevention:
  - compare final loss and key `PYR`, `PEP`, `LAC`, `ATP`, `EGLC`, and `ELAC` metrics directly against the buffered seed
  - if they are identical, shift the hypothesis to a different coupling seam instead of tightening the same downstream set again

### 34. Flux Analysis needs compact result grounding
- Symptom:
  - Flux pages can look “complete” in the UI even when the assistant only has a generic setup snapshot
- Rule:
  - RoBoCop should only interpret Flux Analysis after it has pathway totals, dominant pathway, top flux signals, and provenance
- Prevention:
  - carry `fluxStatus`, dataset provenance, and calibration linkage into the shared Research context
  - if the run is still in progress or results are missing, RoBoCop must say that explicitly

### 35. Stale local dev servers can mask the real code path
- Symptom:
  - the browser shows a generic or outdated answer even though the source files already contain the fix
- Rule:
  - when live behavior disagrees with code, verify the running API process before changing logic again
- Prevention:
  - inspect the active local processes
  - restart the stale service if needed
  - rerun the browser smoke after the fresh process is up

### 38. Plot trust needs an auditable ODE trajectory export
- Symptom:
  - a metabolite plot can look suspicious, but the runtime only writes a tiny pH CSV, making it hard to prove whether the figure came from the real ODE state
- Rule:
  - when scientific trust in the plotted curves matters, export the full simulated metabolite matrix directly from the same `x` array used for plotting
- Prevention:
  - keep a full `all_metabolites.csv` export in `src/main.py` for Brodbar runs
  - use that file to verify that suspicious curves like `EGLC` or `ELAC` match the plotted ODE output exactly

### 39. Audit prints must use the same metabolite index map as the Brodbar ODE
- Symptom:
  - `main.py` can print stale hard-coded indices like `EGLC (x[62])`, which do not match the real Brodbar state order and make plot audits look suspicious
- Rule:
  - any Brodbar metabolite index print or CSV export should derive names/indices from `BRODBAR_METABOLITE_MAP` / `model['metab']`, not legacy hard-coded positions
- Prevention:
  - build the displayed Brodbar metabolite list by inverting `BRODBAR_METABOLITE_MAP`
  - print audit metabolite indices from that same map before or after integration
  - keep plotting and audit outputs tied to the same `x[:, idx]` / `model['metab'][idx]` seam

### 40. A coupled glucose-to-lactate Km seam can steepen EGLC when the glucose-only seam is saturated
- Symptom:
  - once `vmax_VEGLC`, `km_EGLC`, `km_GLC_transport`, `vmax_VHK`, and `vmax_VPFK` are already optimized, rerunning that same narrow glucose seam may return the exact same retained seed
- Rule:
  - if the glucose-only seam is saturated but `EGLC` is still too shallow, shift to a coupled shape probe on `km_GLC_HK`, `km_G6P`, `km_F6P`, `km_PYR`, and `km_LAC`
- Prevention:
  - hold the improved glucose-side Vmax seam fixed
  - let the coupled glucose/lactate Km seam move together
  - check the tradeoff explicitly: `EGLC` and `LAC` can improve while `ELAC` softens

### 41. If both the lactate micro-seam and the PEP/PYR/LDH/PK rebalance seam reproduce the same seed, move on
- Symptom:
  - after the steeper `EGLC` seed is established, both:
    - `km_LAC`, `km_PYR`, `vmax_VLDH`
    - `vmax_VPK`, `vmax_VLDH`, `km_PEP`, `km_PYR`
    can converge back to the exact same retained solution
- Rule:
  - treat that as a local-basin saturation signal, not as a cue to keep adding similar downstream glycolysis/lactate probes
- Prevention:
  - compare final loss and retained metrics directly to the seed
  - if they are unchanged twice in adjacent seams, shift to a genuinely different coupling hypothesis

### 42. If the upstream hexose seam also reproduces the seed, the whole glucose basin is saturated
- Symptom:
  - after establishing the improved `eglc_glucose_lactate_shape_probe` seed, an upstream probe on `vmax_VHK`, `vmax_VPFK`, `km_GLC_HK`, `km_G6P`, and `km_F6P` can also return the exact same retained solution
- Rule:
  - once the downstream lactate seams and the upstream hexose seam all reproduce the same seed, stop searching nearby glucose-basin subsets
- Prevention:
  - recognize that the current seed already contains the useful upstream/downstream glucose adjustments
  - move the next hypothesis to a genuinely different subsystem such as purine/adenylate, PPP/redox, or another structurally distinct coupling seam

### 43. When the glucose basin saturates, a phase-2 purine seam can still open a new improvement basin
- Symptom:
  - after the downstream lactate seams and the upstream hexose seam all reproduce the same `eglc_glucose_lactate_shape_probe` seed, the search can look exhausted even though ATP/ADP/AMP/IMP are still weak
- Rule:
  - once the nearby glucose basin saturates, shift to a genuinely different energetic subsystem before concluding the calibration is stuck
- Prevention:
  - probe a phase-2 adenylate/purine seam such as `vmax_VAK`, `vmax_VAK2`, `vmax_VAMPD1`, and `vmax_VIMPH`
  - evaluate it under `core_glycolysis_energy` rather than an extracellular-only objective
  - check that extracellular anchors like `EGLC`, `LAC`, and `ELAC` stay strong enough while the energy objective improves

### 44. A better long-horizon calibration score still has to survive the full pure ODE
- Symptom:
  - a 42-day adenylate-focused calibration pass can improve the optimization objective while the pure `main.py` Brodbar ODE still drives `ATP` and `ADP` toward zero by the end of the run
- Rule:
  - do not promote a seed based on calibration-report improvement alone when the full pure ODE energy quartet still collapses
- Prevention:
  - rerun `src/main.py` with the candidate seed after any major long-horizon energy/purine pass
  - inspect `ATP`, `ADP`, `AMP`, `IMP`, `EGLC`, `ELAC`, `PYR`, `PEP`, and `LAC` directly from `all_metabolites.csv`
  - if the long-horizon outlet recovery seam simply reproduces the same retained solution, change the hypothesis again instead of squeezing the same pocket

### 45. Hermes should orchestrate calibration from outside the ODE, not inside it
- Symptom:
  - it is tempting to model every enzyme as a live AI agent and let LLM logic leak into the time-step dynamics
- Rule:
  - keep Hermes in the bounded orchestration layer and keep `equadiff_brodbar.py`, `MM_calibration.py`, and `main.py` deterministic
- Prevention:
  - use subsystem agents such as glucose, extracellular transport, lower glycolysis, pyruvate/lactate outlet, adenylate, and purine salvage
- let Hermes read reports, write bounded stage-plan JSON, launch calibration runs, and compare candidates
- require real pure-ODE validation before promotion
- rank candidates by fit first, pure ODE second, penalties last

### 46. Hermes calibration Phase A should stop at draft stage plans
- Symptom:
  - it is easy for a new orchestration layer to blur into uncontrolled execution before the prompt contract and state schema are stable
- Rule:
  - Phase A Hermes calibration should stay read-mostly and write only bounded stage-plan JSON for manual review
- Prevention:
- keep the coordinator prompt contract explicit and versioned
- use a structured subsystem proposal schema instead of free-form notes
- write stage plans only under `config/generated/hermes_calibration/`
- do not auto-run `MM_calibration.py` until the coordinator loop and promotion gate are proven

### 47. Phase A coordinator logic should prefer a different seam once local basins saturate
- Symptom:
  - recent calibration history often contains several zero-improvement retries in the same local glucose or PYR/LAC basin
- Rule:
  - the Phase A coordinator should infer saturated seams from recent run history and avoid selecting them again by default
- Prevention:
  - treat repeated near-zero-improvement runs as saturation evidence
- surface those seams explicitly in coordinator state
- select one different bounded seam for manual review instead of recycling the same pocket

### 48. Phase B must compare seed and candidate through the real pure-ODE rerun, not calibration loss alone
- Symptom:
  - a candidate can look better on `calibration_report.json` while still collapsing ATP/ADP or flattening EGLC in the full `main.py` Brodbar ODE
- Rule:
  - Phase B should execute the drafted stage plan, rerun `main.py` on both seed and candidate, and classify from the combined fit-plus-pure-ODE story
- Prevention:
- copy seed and candidate `all_metabolites.csv` outputs into a dedicated comparison folder before the next `main.py` run overwrites them
- compare protected metabolites on both the calibration report and the pure ODE summary
- only return `promote` when the fit improvement is meaningful and the protected pure-ODE checks do not regress

### 49. Phase C arbitration should merge only genuinely compatible seams
- Symptom:
  - once Hermes can see several plausible subsystem proposals, it becomes tempting to bundle too many of them into one run and lose scientific attribution
- Rule:
  - Phase C should merge only a very small coalition of subsystem seams, and only when they share a compatible phase/target basin and do not overlap parameter ownership
- Prevention:
- keep the coalition size bounded
- reject proposals that conflict on seam ownership, target scope, phase, or overlapping parameters
- prefer one strong proposal over a noisy bundle unless the supporting seam clearly opens a new basin with it

### 50. Phase D should remember seam outcomes across bounded cycles
- Symptom:
  - without memory, Hermes can keep retrying the same saturated local seam or forget that a seam became dangerous only after pure-ODE validation
- Rule:
  - repeated bounded calibration cycles should reuse seam memory, carry same-seed saturation forward immediately, and only advance the seed after a promoted candidate
- Prevention:
- persist a seam-memory ledger for every Phase D session
- treat same-seed `saturated` seams as blocked in the next arbitration pass
- carry `dangerous` seams forward even across promoted seeds when the pure ODE regressed
- only replace the working seed when Phase B returns `promote`

### 51. Phase B must compare against the candidate run baseline, not only a historical seed report
- Symptom:
  - a live Hermes Phase A / Phase B smoke test can look like a huge regression if Phase B compares the candidate report to a historical seed report generated under a different calibration context
- Rule:
  - Phase B should treat the candidate run's own `results.tsv` baseline/final pair as the primary apples-to-apples fit comparison
- Prevention:
  - pass the seed calibration context (`seed`, `t_max`, `curve_fit_strength`, and related stage settings) from Phase A/C into the written stage plan
  - have Phase B forward that context explicitly to `src/MM_calibration.py`
  - only use historical seed-vs-candidate report comparison as secondary context, not as the primary gain signal
  - if the candidate simply reproduces the seed under the same run context, classify it as `discard` rather than `informative`

### 52. If agent source editing is opened, start with the calibration orchestrator, not the ODE
- Symptom:
  - there is pressure to let agents “improve the model” quickly, but unrestricted edits could silently mutate scientific truth rather than calibration behavior
- Rule:
  - the first editable source layer should be `src/MM_calibration.py`, while `src/equadiff_brodbar.py` stays frozen
- Prevention:
  - only allow edits in fit/ranking/routing/stage-planning/reporting zones
- keep the ODE bridge, state semantics, and parameter identity frozen
- require real `main.py` pure-ODE validation before any patch can be considered `promote`

### 53. Editable-source autonomy needs explicit file and line boundaries
- Symptom:
  - once agent source editing becomes possible, a broad “MM_calibration.py is editable” rule is still too loose and risks silent drift into protected scientific logic
- Rule:
  - enforce agent edits through explicit editable markers plus a frozen-file validator before any live autonomous patching is allowed
- Prevention:
- keep editable markers only on bounded orchestration zones inside `src/MM_calibration.py`
- reject any proposed edit to `src/equadiff_brodbar.py` in the first rollout
- validate before/after changed spans against the marked zones with a dedicated tool before running the scientific validation bundle

### 54. Validation must live on the write path, not only in review mode
- Symptom:
  - a policy validator can exist, but if the actual autonomous edit flow writes files directly, the safeguard is too easy to bypass
- Rule:
  - all future autonomous calibration source edits must pass through a guarded apply step that calls the validator before any file write
- Prevention:
- use `calibration_apply_agent_edit` as the only write-path entry for bounded `MM_calibration.py` edits
- treat `calibration_validate_agent_edit` as a preflight/read-only tool, not as the final gate by itself

### 55. Source-patch autonomy should default to revert-unless-promote
- Symptom:
  - once a bounded source patch can run scientific validation, leaving every `informative` or `discard` patch in the tree would destabilize the working baseline
- Rule:
  - the first autonomous patch loop should keep a source patch only for explicitly allowed decisions and revert it automatically otherwise
- Prevention:
- run the patch through the gate, then `py_compile`, then Phase B scientific validation
- default `keepOnDecision` to `promote`
- automatically restore the original source file when the decision is `discard` or any other non-kept outcome

### 56. Prove the guarded patch loop with a harmless live smoke before trying a scientific source edit
- Symptom:
  - a bounded source-edit loop can look correct in tests while still hiding a write/revert bug in live execution
- Rule:
  - the first live run should use a tiny diagnostics-only patch inside an allowed zone so the plumbing can be proven without risking calibration drift
- Prevention:
- validate the full path on a real file: gate -> apply -> `py_compile` -> Phase B -> automatic revert
- confirm that the patch string is absent afterward when the decision is not kept
- only then move on to a real fit/objective hypothesis inside `MM_calibration.py`

### 57. A tiny fit-first source patch can still hit a fully saturated basin
- Symptom:
  - even a real scientific patch inside `fit_penalty_hierarchy` can compile and validate cleanly yet produce `absolute_gain = 0.0` because the chosen seam/seed combination is already saturated
- Rule:
  - distinguish “the patch loop worked” from “the scientific hypothesis moved the basin”
- Prevention:
- if a bounded source patch lands on a known saturated seam, treat a clean `discard` as a successful live plumbing result, not as evidence the patch loop failed
- choose the next live source-edit hypothesis on a seam that is still expected to move, or on ranking/reporting logic that changes candidate selection more directly

### 58. If we want pure fitting, remove penalty influence from ranking before widening the search
- Symptom:
  - even when `fit_loss` is primary on paper, regularization and physiological penalties can still flatten the search and hide the true worst-fit metabolites we care about most
- Rule:
  - if the scientific goal is explicitly “fit the experiment with the real ODE, even if it is slower,” then `rank_loss` should collapse to `fit_loss` and acceptance should be fit-only
- Prevention:
- keep penalty terms only as diagnostics in the report
- do not let monitor guardrails veto an objectively better fit candidate during the calibration loop
- if the runtime budget allows it, use report-level ODE fidelity for optimization rather than coarser fast/screen approximations

### 59. Once the fit-only true-ODE regime is active, a tiny improvement means the basin itself may be the limiter
- Symptom:
  - after removing penalty influence and aligning optimization fidelity with the report ODE, a broader long-horizon seam can still improve only marginally
- Rule:
  - if a longer fit-only run gains only about `0.1%`, stop blaming penalties and assume the current seed/seam basin is near saturation
- Prevention:
- use the fit-only report to identify the remaining true worst-fit metabolites directly
- pick the next seam from those unresolved metabolites rather than widening another already-rediscovered basin
- validate the candidate again with `main.py` before promoting a new long-horizon seed

### 60. A huge fit-only gain can still make the long-horizon pure ODE worse
- Symptom:
  - a more direct basin-targeted seam can cut calibration loss dramatically while still worsening the actual long-horizon ODE behavior on the metabolites we care about most
- Rule:
  - never promote a fit-only candidate on calibration score alone, even when the gain is very large
- Prevention:
- always rerun `main.py` on the previous seed and the new candidate
- compare `ATP`, `ADP`, `EGLC`, `ELAC`, `PYR`, `PEP`, and `LAC` directly on the pure ODE trajectories
- if `EGLC` improves but `ATP/ADP` collapse harder or `PYR/PEP` worsen materially, keep the candidate as informative rather than promoting it

### 61. If a stabilization seam reproduces the new fit-only basin exactly, stop squeezing that pocket
- Symptom:
  - after a large basin-opening fit-only move, a follow-up stabilization run can return the exact same loss, protected metrics, and optimized parameter values
- Rule:
  - treat that as a true local saturation signal, not as evidence that we only need more trials
- Prevention:
- if both the outlet seam and the direct adenylate seam snap back to the same retained values, change the hypothesis instead of rerunning the same stabilization pocket
- only reopen that pocket later if another upstream or cross-coupled seam has moved the basin first

### 62. Full-file autonomy on MM_calibration.py is acceptable only if the ODE core stays frozen
- Symptom:
  - once local seams saturate, marker-bounded edits can become too restrictive to test higher-level calibration-flow changes
- Rule:
  - if we open full-file autonomy on `src/MM_calibration.py`, keep `src/equadiff_brodbar.py` frozen and keep every patch promotion-gated by the real ODE
- Prevention:
- allow the whole of `MM_calibration.py` to be edited
- reject any write to `equadiff_brodbar.py`
- keep compile + Phase B + `main.py` validation mandatory before a patch can be kept

### 63. Explicit include_params should be able to pull valid global bounds, not only phase-local ones
- Symptom:
  - a stage plan can request a real parameter like `km_ADP_ATP`, but the parameter never gets tested if it is absent from the selected phase-local map
- Rule:
  - when `include_params` explicitly names a valid parameter, the resolver should be allowed to inject its global bounds even if the current phase map does not already expose it
- Prevention:
- compare requested `include_params` against the union of `PHASE_MAP` before assuming a seam was really tested
- validate the fix by checking `resolved_stage_plan.phase_params` and `selected_param_names` in the resulting `calibration_report.json`
- do not keep the code patch automatically if the scientific run still reproduces the seed and is classified `discard`

### 64. Hybrid kinetics should enter as neutral wrappers, not a global ODE rewrite
- Symptom:
  - once pure Michaelis-Menten fitting saturates, the temptation is to rewrite the Brodbar ODE monolithically and lose regression safety
- Rule:
  - keep the state topology and MM scaffold stable, and introduce complementary kinetics only through neutral-by-default wrappers on selected reactions
- Prevention:
- first separate flux computation from `dxdt` assembly in `equadiff_brodbar.py`
- keep neutral defaults that reproduce the existing MM trajectories
- expose hybrid families to calibration only after the zero-math refactor has been regression-checked through `main.py`

### 65. First hybrid families should land on glucose/lactate fluxes with identity defaults
- Symptom:
  - opening `equadiff_brodbar.py` too broadly makes it hard to tell whether a gain comes from better kinetics or from accidental structural drift
- Rule:
  - start hybridization on a very small set of biologically central fluxes and make every new family exactly reproduce the current MM behavior at default settings
- Prevention:
- first wrappers now belong on `VEGLC`, `VELAC`, and `VLDH`
- use explicit `kinetic_family_*` selectors plus `hybrid_blend_*` weights that default to the existing MM path
- always rerun the official `main.py --model brodbar` path after each new wrapper family is introduced

### 66. Hybrid flux parameters need linear sampling and zero-safe reporting
- Symptom:
  - the first hybrid calibration smoke test failed because Optuna still used log sampling on `hybrid_blend_*` parameters with `low = 0`, and later the reporting code divided by zero on zero-default hybrid parameters
- Rule:
  - any hybrid parameter family that includes zero-default blends or scales must use zero-safe optimization and zero-safe diagnostics
- Prevention:
- disable log sampling for `PARAM_CLASS_HYBRID`
- print ratio text as `n/a` when the default value is zero
- validate exposure with a real `hybrid_only` smoke run, not just taxonomy introspection

### 67. A staged MM-anchor then hybrid-opening run can simply reproduce the accepted hybrid seed
- Symptom:
  - a mixed stage plan that first re-opens the glucose/lactate `vmax/km` seam and then re-opens the hybrid seam can converge back to the already accepted hybrid candidate with `0.0%` gain
- Rule:
  - treat an exact fit-only tie on both stages as evidence that the current hybrid glucose/lactate basin is already locally stable
- Prevention:
- compare the mixed run directly against the latest accepted hybrid seed before spending extra ODE validation budget
- if baseline loss, final loss, and retained parameter values are unchanged, change the hypothesis instead of repeating `vmax/km -> hybrid_only`

### 68. Downstream hybrid families should be exposed through a dedicated scope before widening the broad hybrid search
- Symptom:
  - adding `VPK` and `VENOPGM` hybrid degrees of freedom directly into a broad existing hybrid scope would make it harder to tell whether a gain came from transport/LDH hybrids or the new downstream levers
- Rule:
  - open new downstream hybrid families under their own explicit parameter scope first, then decide later whether to merge them into a broader hybrid basin
- Prevention:
- keep `hybrid_glucose_lactate` stable for the current transport/LDH group
- expose `VPK` / `VENOPGM` through a separate `hybrid_downstream_pk_eno` scope
- validate the official `main.py` ODE path with a parameter file that includes the new hybrid parameters before spending a serious search budget

### 69. The first downstream hybrid seam is mobile, but only weakly in the true ODE
- Symptom:
  - a real 42-day `hybrid_downstream_pk_eno` run can improve calibration loss and move `VPK`/`VENOPGM` hybrid parameters off neutral defaults, yet the official pure ODE trajectories barely shift on `ATP/ADP`, `PYR`, `PEP`, and `LAC`
- Rule:
  - treat early downstream hybrid wins as signal that the seam is open, not as proof that it is already strong enough on its own
- Prevention:
- validate every downstream hybrid gain with a seed-vs-candidate `main.py` rerun
- if the ODE deltas are only marginal, prefer a wider combined hybrid hypothesis rather than repeatedly squeezing the downstream seam in isolation

### 36. Pathway graph source of truth should come from the model, not a decorative subset
- Symptom:
  - a pathway page renders a KEGG-style map that looks scientific but omits reactions or labels that the underlying model actually knows about
- Rule:
  - the canonical pathway graph should be derived from the model reaction/species registry, with KEGG treated as optional metadata or annotation
- Prevention:
  - do not let a hand-curated layout file become the effective truth for the network
  - keep the graph schema aligned with simulation and flux identifiers so playback can be faithful

### 37. Simulation playback needs a shared result snapshot, not just page-local state
- Symptom:
  - a pathway page wants to animate over time, but the latest simulation result only exists inside the Simulation page hook state
- Rule:
  - if a page needs to replay a simulation, persist or expose the completed result through a shared research context/store
- Prevention:
  - carry `t`, `x`, `metabolite_names`, and optionally `flux_data` into a shared snapshot
  - use the existing `/pathway/network-state` seam as the projection layer instead of inventing a new ad hoc protocol

---

## Repeat Failure Patterns

### CSS / UI verification drift
- Detection:
  - code changed but browser still shows old styles
- Prevention:
  - hard refresh, restart dev server, or verify build artifact path

### Sidebar active-state bugs
- Detection:
  - parent route stays highlighted instead of child route
- Prevention:
  - exact href match first, then longest matching prefix

### Hidden composition layer issues
- Detection:
  - page order doesn't match expectations from feature-local code
- Prevention:
  - inspect shared wrappers before editing only the local component

### Missing router registration
- Detection:
  - FastAPI route exists in code but returns 404
- Prevention:
  - verify router registration in the API entrypoint

---

## Important Persistent Product Context

### App structure direction
The app is being organized around:
- HOME
- RESEARCH
- MONITORING
- MY ACCOUNT

### Research mode
Includes:
- Overview
- Data Upload
- Calibration Registry
- Simulation
- Flux Analysis
- Sensitivity Analysis
- Pathway Visualization

### Monitoring mode
Includes:
- Overview
- RoBoCop
- Bag Repo
- Quality Forecast
- Alerts

### RoBoCop product role
RoBoCop is the central agent.
It is not only a calibration tool.
It should interpret results across research and monitoring modules.

### Hermes relationship
Hermes should be treated as the internal agent engine.
RoBoCop remains the visible product identity and RBC-specific logic.

### Research data mode
When Research mode has no active upload, Bordbar/default remains the fallback dataset.
Once a custom dataset is uploaded and activated, the active dataset identity and mode must be carried explicitly through calibration, simulation, and RoBoCop context.
Do not infer the active mode from the mere presence of experimental payloads; pass `research_data_mode`, `active_dataset_id`, and `active_dataset_label` from the Research shell so Bordbar/default and custom user data stay unambiguous.
`src/MM_calibration.py` is the canonical scientific calibration core for the current product path.
The web calibration route should behave as a thin adapter, not a second source of truth.
Simulation can carry the same mode metadata before the solver itself becomes dataset-aware.

### Calibration taxonomy adapter
The Parameter Optimization page should read kinetic parameters from the canonical MM_calibration taxonomy adapter instead of a manually curated list.
Keep a recommended quick-pick subset in the UI, but expose the full canonical Vmax/Km inventory with phase-specific suggested bounds so the page stays aligned with the scientific core.
Do not merge autosearch triage or run-policy mutation into the kinetic parameter picker; those remain separate orchestration concerns.

### Calibration strategy families
The calibration page strategy control should be named as a real optimization strategy selector, not a generic method dropdown, when the backend operates on canonical `MM_calibration` strategy families/templates.
The UI should expose a small recommended default plus the canonical family list from `MM_calibration.OPTIMIZATION_STRATEGY_CHOICES`, with backend routing through the same canonical contract.
Manual calibration strategy selection stays separate from bounded autosearch mutation and triage; those are different layers and should remain explainable independently.

---

## Use This File For
- persistent lessons
- anti-regression reminders
- important product constraints
- patterns that should not be rediscovered repeatedly

Do not use this file as a task tracker or execution log.
## 2026-03-20 calibration provenance
- Calibration context must distinguish current selection from any loaded calibration result snapshot.
- When a saved calibration exists, the Calibration page should hydrate the visible selection, optimization strategy, and target metabolites from that snapshot instead of showing a blank setup state.
- RoBoCop on the Calibration page should say whether the view is setup-only, freshly run, or auto-loaded from a saved calibration result.
- The shared calibration context should carry canonical taxonomy source/version, selected parameter families, strategy label, and dataset provenance so chat and summary surfaces can answer setup questions truthfully.
### 2026-03-21 completed calibration result awareness
- A calibration run can be fully result-aware without broad scientific rewrites if the page context carries completion status, fit metrics, parameter changes, and provenance.
- RoBoCop should switch from setup-only explanations to result-aware explanations only after the calibration actually completes.
- Completed calibration responses should distinguish Bordbar/default fallback, custom uploaded data, strategy family, and the quality of fit in compact structured fields.
- Long-running calibration work should be validated end to end in the browser when possible, but the assistant should still be truthful about what was directly observed versus inferred from payloads.

### 2026-03-21 canonical taxonomy adapter caching
- When a canonical taxonomy endpoint is heavy on first load, cache the derived inventory on the backend adapter rather than weakening the source of truth.
- Read-only caches are acceptable for taxonomy discovery as long as the canonical calibration core remains the single source of truth.
- Browser validation becomes much more reliable once the taxonomy endpoint stops rebuilding the inventory on every request.

### 2026-03-21 completed custom-data calibration validation
- A completed custom-data calibration can be proven end to end even when the default backend worker is stale, as long as the active dataset, calibration result, and RoBoCop context are kept aligned.
- The browser Research shell should still show the active dataset label, canonical strategy, completed result summary, and RoBoCop result-awareness together on the Calibration page.
- When the live backend is blocked, route-mocked browser validation is acceptable for UI/provenance confirmation if the canonical calibration result has already been validated on a fresh backend instance.

### 2026-03-21 Data Upload persistence gap
- Data Upload should not rely on a delayed one-off state sync if the active dataset is already persisted in the shared research store.
- If the page briefly shows Bordbar/default before the custom upload label appears, switch the provider to a store-backed snapshot so the same dataset state feeds Calibration, Simulation, RoBoCop, and Data Upload consistently.
- The same active dataset label should be visible after Research-page navigation, not only on the calibration and assistant surfaces.

### 2026-03-21 Flux Analysis provenance
- Flux Analysis should not be treated as a generic bar chart page; it needs a compact result context that includes pathway totals, dominant pathway, top flux signals, dataset provenance, and calibration linkage.
- RoBoCop should answer Flux questions from the same provenance contract used by Simulation and Calibration, including setup-only, running, completed, and failed states.
- If the live assistant output looks generic, check whether the API process is stale before assuming the Flux context code is wrong.
### 2026-03-21 Flux Analysis redesign
- Flux Analysis reads better when the page is structured as a premium scientific workspace: hero summary, provenance snapshot, result summary, then ranked pathway cards.
- The dominant pathway, total flux, top reaction, and applied concentration counts should be visually prominent because they are the quickest interpretation anchors.
- RoBoCop should remain discreet on Flux pages, with the main surface staying science-first and the assistant acting as a contextual interpreter rather than the center of attention.

### 2026-03-21 active-surface pruning
- If a Research module is no longer part of the main product navigation, remove it from the sidebar and overview cards but keep the implementation route intact for direct access or legacy use.
- Research navigation should stay focused on the currently active scientific surfaces so the overview reads like a live workflow instead of an archive.
- When a module is de-surfaced, record the next active target explicitly so the team knows where the assistant and provenance work should move next.

### 2026-03-22 Monitoring surface reorg
- Monitoring should present a visible core of Overview, Bag Repository, Quality Forecast, and Alerts, with Hermes reserved as the hidden future messaging gateway.
- The overview page reads better when it states the four-part structure explicitly and keeps assistant messaging out of the active sidebar.
- If the legacy Monitoring RoBoCop route remains in the codebase, it should stay hidden and be described as Hermes rather than a live product-facing monitoring page.

### 2026-03-22 Monitoring Overview command center
- The Monitoring Overview page should read like a command tower, not a placeholder or generic landing page.
- Good Overview structure:
  - KPI strip for structural state
  - operational snapshot cards for Bag Repository, Quality Forecast, Alerts, and the future Hermes gateway
  - recent activity / alert / forecast panels that feel like a serious operations surface
- Keep the route cards below the hero focused on the three live operational pages so the page remains a status hub as well as a navigator.

### 2026-03-21 Pathway Visualization grounding
- Pathway Visualization is a structural network map, not a flux or calibration result, so RoBoCop should explain provenance and network scale without inventing result semantics.
- Compact RoBoCop cues work best as a small context surface beside the graph, with dataset mode, calibration state, network size, and key pathways visible in one glance.
- The shared Pathway context should stay honest about the current research mode while keeping the graph itself the scientific focus.
- Pathway replay now reads the latest simulation snapshot synchronously from browser storage, which removes the manual custom-data seeding step after Simulation.
- Pathway replay-aware RoBoCop should mention the current frame/timepoint, replay source, and provenance state directly from the shared replay snapshot when interpreting the network.
- Pathway Visualization reads better when the canonical registry is projected as a metabolite/reaction graph, with reaction nodes and counts called out explicitly instead of hiding everything behind generic edge labels.
- Once the graph is structurally stronger, the next readability gain comes from interaction, not more source truth: offset labels to avoid collisions, let users click metabolites/reactions, and show the selected element in a compact details rail.
- Keep graph interaction state local to the page, but mirror the selection summary into the shared Pathway context so RoBoCop can explain the chosen node or edge too.
- Quick-select chips are now part of the Pathway interaction layer, giving a deterministic way to verify metabolite/reaction selection while preserving the compact details rail as the interpretive anchor.

### 2026-03-22 Pathway compact/full overview
- The Pathway page should expose a compact overview mode that organizes the model into bridge-metabolite cards, alongside the full registry map.
- Principal connectors are best treated as interpretation anchors for each pathway group, with G6P, R5P, B23PG, ATP, NADPH, GLU, GLC, OAA, and IMP-style hubs surfacing where they bridge groups most clearly.
- The compact overview should stay tied to the same replay/provenance context as the full graph so RoBoCop can explain either view without changing the scientific story.

### 2026-03-22 Pathway compact graph + zoom
- Compact Pathway mode should still be a graph, just a reduced bridge graph built from the canonical registry, with one key connector metabolite per pathway group.
- The compact atlas belongs in the side rail as secondary guidance, while the main viewport keeps the graph and its zoom controls.
- For local browser validation, the API CORS allowlist should accept any localhost/127.0.0.1 dev port; otherwise the graph page can look broken even when the code is correct.

### 2026-03-22 Bag Repository inventory surface
- Bag Repository should feel like a real inventory workspace: KPI strip, search/filter bar, selectable table, and a compact details rail.
- Keep donor metadata, bag identity, storage context, quality state, forecast state, and alert links visible in one place so the page can feed future Monitoring flows.
- Avoid turning the page into a CRUD admin screen; the page should stay operational and biobank-oriented.
### 2026-03-22 Quality Forecast predictive surface
- Quality Forecast should stay framed as a constrained Monitoring predictor, not a full Research simulation page.
- The page works best when it anchors to one selected bag, a limited extracellular biomarker panel, and a snapshot-aware projection if one is available.
- Monitoring and Research should share the same selected-bag identity, but the forecast must clearly say which parts are inherited from Research and which parts are intentionally excluded.
### 2026-03-22 Monitoring bag intake backend
- Monitoring bag intake should be backed by a real create/read API so Bag Repository and Quality Forecast share the same persisted inventory source.
- localStorage is fine as a cache or transitional fallback, but it should not be the source of truth once the backend intake flow exists.
- The create endpoint should only accept true intake fields and let the backend initialize operational defaults like quality state, forecast state, alerts, linked runs, and monitoring events.
- Duplicate bag IDs should be rejected server-side so the repository and forecast stay consistent across pages.

### 2026-03-22 Monitoring alerts derivation
- Alerts should be derived from forecast output with a shared queue model, not reconstructed inside the page UI.
- Keep biological risk severity separate from operator workflow status so triage can stay readable.
- Use forecast projections, review windows, and simulation linkage to prioritize the queue, then let local UI actions change workflow state until a backend action API exists.
## Monitoring Alerts Persistence
- Alert workflow state is now backend-persisted with a minimal transition history trail.
- The first real workflow change from the default `New` state is recorded as a history transition.
- Biological forecast severity remains deterministic and separate from operator workflow status.
- In SSR Monitoring surfaces, avoid locale-sensitive timestamps when the same page hydrates on the client, or render UTC-stable timestamps instead.
- Supabase provisioning gotcha:
  - the service-role JWT is not a Supabase management API token
  - the Supabase CLI needs either a real Supabase access token (`sbp_...`) for linked operations or a usable remote Postgres password for `db-url` / `db push`
  - if neither is available, the remote workflow tables cannot be provisioned from this environment even though the SQL setup exists in-repo
## Calibration memory
- For custom-data calibration, preserve exact parameter/class names when building stage plans; uppercasing names broke matching and had to be corrected in the API adapter.
- The right default route for Monitoring-relevant custom data is profile-aware: extracellular targets should use `glycolysis_extracellular`, while ATP/ADP-only datasets should use `core_glycolysis_energy`.
- `vmax_then_km` is now the preferred default strategy for the custom-data path because it gives a disciplined Vmax-first pass before tightening Km values.
- ATP/ADP are still the hardest targets. The profile-aware bridge parameters can be useful, but the acceptance gate correctly rejected a destabilizing adenylate bridge when it hurt protected core metrics.
- Better extracellular fit should improve Monitoring forecasts because Monitoring is driven primarily by extracellular signals, even when the calibration work is done in Research mode.
