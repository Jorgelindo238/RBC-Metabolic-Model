# AgentOps Tasks

Current active work, execution state, blockers, and immediate next actions.

## Current Objective
Keep the airbc / RoBoCop platform moving forward with:
- a stable product shell
- a stable scientific backend
- explicit research vs monitoring structure
- reliable calibration/autoresearch workflows

### Immediate Next Action
- Commit and push the current repository hygiene follow-up on `main`:
  - root `.gitignore`
  - `.python-version`
  - calibration-worker runtime note
  - Storybook assets required by the tracked onboarding docs
- Redeploy production from GitHub `main`:
  - `web` -> `app.airbc.org`
  - `marketing` -> `airbc.org`
- Verify Vercel production deployments are GitHub-backed, not local/Codex uploads.
- Then rerun a production smoke test:
  - Calibration Registry parameter load
  - `/research/parameter-calibration`
  - worker job creation / polling

### Active Workstreams

#### Repository hygiene - main
- Status: In progress; branch cleanup completed
- Goal:
  - keep `main` deployable from GitHub while keeping runtime artifacts and credentials out of Git
- Current state:
  - local and remote branches have been collapsed back to `main`
  - the previous `kimi-2` cleanup commit has been cherry-picked onto `main`
  - root docs have been reduced to `README.md` and `ARCHITECTURE.md`
  - a root `.gitignore` is staged to ignore secrets, local Vercel state, build outputs, logs, caches, SQLite runtime data, generated simulation outputs, and archived task notes
  - `.python-version` is staged to pin the current supported Python runtime while the Python 3.14 migration remains deferred
- Decision:
  - do not stage `.env`, `.streamlit/secrets.toml`, `.vercel`, `.next`, `node_modules`, logs, `__pycache__`, runtime DB files, or generated `Simulations/...` output directories
  - keep only the canonical tracked Bordbar calibration seed/report under `Simulations/brodbar/calibration/`
- Next step:
  - commit and push the staged hygiene follow-up, then redeploy `web` and `marketing` from GitHub `main`

#### Python 3.14 runtime migration
- Status: Deferred backlog
- Goal:
  - evaluate whether the Python scientific/runtime stack can safely move from Python 3.12 to Python 3.14
- Current finding:
  - Python 3.14 is installable with a modern stack (`numpy>=2.3`, `scipy>=1.17`, `pandas>=3.0`)
  - the current `numpy<2.0.0` constraint is the blocker because NumPy 1.26 does not provide a stable Python 3.14 wheel in this environment and falls back to source compilation
- Decision:
  - keep production on Python 3.12 for now
  - revisit later on a dedicated migration branch rather than changing production runtime directly
- Future validation plan:
  - update `requirements.txt`, `api/requirements.txt`, and `apps/calibration-worker/requirements.txt`
  - run a clean Python 3.14 install
  - run `py_compile` on API, worker, and scientific entrypoints
  - run `qa/robocop`
  - compare at least one calibration/simulation output against the Python 3.12 baseline before promoting

#### 3. RoBoCop Research Assistant v1 - Simulation
- Status: Completed Phase 1-6 (rule-based interpretation)
- Goal: In-app scientific assistant for Simulation module interpretation
- Scope: Research mode, Simulation page only
- Deliverables:
  - RoBoCop UI surface on Simulation page ✓
  - Simulation context ingestion ✓
  - Selection-aware metabolite focus from the Simulation chart ✓
  - Route-safe context reset when leaving the Simulation page ✓
  - Grounded result interpretation ✓
  - Extensible architecture for future modules ✓
- Implementation:
  - Context contracts in `types/robocop-context.ts`
  - Simulation context builder in `lib/robocop/simulation-context.ts`
  - Rule-based interpretation service in `lib/robocop/interpretation-service.ts`
  - RoBoCop UI component in `components/features/robocop/RoBoCopAssistant.tsx`
  - Integrated into `SimulationWorkspace` with selection-aware context updates

#### 4. RoBoCop Research Chat v1 - LLM-based Assistant Across Research Pages
- Status: Completed Phases 1-7
- Goal: LLM-backed conversational assistant for all Research pages
- Scope: Research mode, all pages (starting with Simulation)
- Deliverables:
  - Shared Research-page RoBoCop chat pattern ✓
  - Reusable module context contract for all Research pages ✓
  - LLM-backed chat flow ✓
  - First live implementation on Simulation page ✓
  - Architecture ready for other Research modules ✓
- Implementation:
  - Research context contracts in `types/research-context.ts`
  - Context builders for all Research modules in `lib/robocop/research-context-builders.ts`
  - RoBoCop Chat UI component in `components/features/robocop/RoBoCopChat.tsx`
  - Backend chat endpoint in `apps/api/routers/robocop.py`
  - Chat client in `lib/robocop/chat-client.ts`
  - Integrated into `SimulationWorkspace` with selection-aware research context

#### 5. RoBoCop Shared Chat Surface v1 - Discreet Research Assistant
- Status: Completed Phases 1-8
- Goal: Shared chat surface with expandable panel for Research pages
- Scope: Research mode, all pages (starting with Simulation)
- Deliverables:
  - Discreet shared chat surface component ✓
  - Compact expandable chat panel/drawer ✓
  - Reusable Research-page pattern ✓
  - First implementation on Simulation page ✓
  - Premium, non-intrusive UX ✓
- Implementation:
  - Shared chat surface in `components/features/robocop/RoBoCopChat.tsx`
  - Research context provider in `contexts/ResearchContextProvider.tsx`
  - Integrated into `PlatformShell` for all Research pages
  - Context set by `SimulationWorkspace` component and cleared on route exit
  - Uses existing backend chat endpoint

#### 6. RoBoCop OpenAI Integration v1 - Real LLM Responses for Simulation
- Status: Completed Phases 1-8
- Goal: Connect RoBoCop chat to a real OpenAI backend
- Scope: Research mode, Simulation page only (initially)
- Deliverables:
  - Server-side OpenAI configuration ✓
  - Real OpenAI chat responses ✓
  - Grounded simulation context integration ✓
  - Preserved analytical summary panel ✓
  - Reusable backend pattern for Research pages ✓
- Implementation:
  - OpenAI configuration in `apps/api/config.py`
  - OpenAI service in `apps/api/services/openai_service.py`
  - Updated RoBoCop router to use OpenAI with fallback
  - Enhanced shared chat surface with message display
  - Environment template in `.env.example`

## Active Workstreams

### 1. Platform Navigation & Product Structure
#### Sidebar restructure
- Status: Completed
- Result:
  - HOME
  - RESEARCH
  - MONITORING
  - MY ACCOUNT
- Notes:
  - route-backed navigation implemented
  - required pages scaffolded
  - `RBC Storage Research` renamed to `RBC Research`

#### Authenticated UI verification
- Status: Partially blocked
- What is done:
  - code-level restructure validated
  - route scaffolds created
  - type checks passed
- Blocker:
  - no repo-consistent authenticated test path
- Remaining:
  - signed-in click-through
  - active-state confirmation
  - preserved `RBC Research` rendering in session

---

### 2. Scientific Backend & Autoresearch
#### RoBoCop Mutation Agent
- Status: Strong baseline established
- Current state:
  - native mutation generator v2 exists
  - bounded multi-field mutation exists
  - novelty filtering exists
  - parent-selection exists
  - time-aware search policy exists

#### Time-aware search validation
- Status: Completed
- Result:
  - timeout path validated end-to-end
  - completion status, coverage, and time-aware fields preserved across:
    - evaluator
    - manifest
    - registry
    - decision record
    - ledger

#### Bounded autosearch overnight sessions
- Status: Completed
- Result:
  - the bounded LangGraph loop now supports multi-iteration CLI sessions
  - `Keep` candidates can be promoted as the next base policy in the same session
  - session-level JSON summaries are written for morning-after review
- Current implementation:
  - `scripts/run_bounded_autosearch.py` now supports:
    - `--max-iterations`
    - `--loop-budget-seconds`
    - `--stop-on-keep`
  - session summaries are stored under `Simulations/brodbar/autoresearch/agent_orchestration/sessions/`
  - the runner now filters parent-guided multi-field proposals down to effective mutations so unchanged fields do not create fake `Keep` cycles
- Next step:
  - run a real overnight bounded autosearch session on the calibration policy space once the desired wall-clock budget is chosen

#### Calibration orchestration V1
- Status: Phase D seam-memory reuse across repeated bounded cycles implemented
- Goal:
  - use RoBoCop orchestration as a bounded outer-loop controller for `src/MM_calibration.py` without mutating the scientific core
- Scope:
  - artifact reading
  - subsystem-agent diagnosis
  - bounded stage-plan generation
  - calibration run launch
  - `main.py` pure-ODE validation
  - seam-memory tracking
- Current direction:
  - coordinator plus subsystem agents is preferred over one agent per enzyme
  - the scientific core stays frozen; the orchestration layer should only mutate generated stage-plan / decision artifacts
  - candidate ranking should stay fit-first, pure-ODE-second, penalty-last
- Working spec:
  - `AgentOps/CALIBRATION_ORCHESTRATION.md`
- Current implementation:
  - shared calibration state schema now exists in `services/robocop/calibration_state.py`
  - coordinator prompt contract and structured response schema now exist in `services/robocop/calibration_prompts.py`
  - calibration orchestration toolset now includes:
    - `calibration_get_artifact_summary`
    - `calibration_get_trajectory_group`
    - `calibration_get_candidate_history`
    - `calibration_write_stage_plan`
    - `calibration_coordinate_phase_a`
    - `calibration_execute_phase_b`
    - `calibration_coordinate_phase_c`
    - `calibration_run_phase_d_session`
  - the stage-plan writer only writes bounded JSON under the legacy generated calibration path and stops before execution
  - the Phase A coordinator loop now:
    - reads artifact summaries
    - infers saturated seams from recent run history
    - assembles subsystem proposals
    - selects one bounded next seam
    - writes a manual-review stage-plan and stops
  - the Phase B executor now:
    - executes the drafted stage-plan through `src/MM_calibration.py`
    - reruns `src/main.py` on the seed and the candidate
    - copies the pure-ODE artifacts into a dedicated Phase B comparison folder
    - compares seed vs candidate on fit and pure-ODE behavior
    - classifies the result as `promote`, `informative`, or `discard`
  - the Phase C arbiter now:
    - reads the same artifact / trajectory / history summary inputs as Phase A
    - arbitrates between subsystem proposals instead of picking only the single top proposal
    - can select a small compatible coalition of subsystem seams
    - writes a bounded multi-stage stage plan
    - can optionally pass the written plan into Phase B for execution and classification
  - the Phase D session loop now:
    - runs repeated bounded Phase C + Phase B cycles
    - persists seam-memory after each cycle
    - feeds same-seed saturated seams into the next arbitration pass
    - carries dangerous seams forward across promoted seeds
    - advances the working seed only after a `promote`
    - writes session summaries and seam-memory ledgers under the legacy Phase D artifact path
- Current naming note:
  - the local `hermes-agent/` clone has been removed
  - some Python classes, workflow labels, and historical artifact paths still contain `Hermes` / `hermes` as legacy implementation names
  - treat those names as technical debt to migrate later, not as an active runtime dependency
- Next step:
  - exercise the new Phase D session loop on a real calibration seed and inspect whether the seam-memory policy avoids redundant local retries

#### Custom-data calibration orchestration roadmap (P1-P7)
- Status: P1-P7 code path implemented; production worker hookup remains open
- Goal:
  - turn custom-data calibration into a dataset-aware, worker-backed orchestration flow rather than a single fixed strategy call
- What is now implemented:
  - P1 dataset-aware planner in `services/robocop/custom_dataset_planner.py`
  - P2 programmatic curve triage in `services/robocop/curve_triage.py`
  - P3 pure-ODE triage in `services/robocop/pure_ode_triage.py`
  - P3a true pure-ODE replay + `combined_triage` in `apps/api/services/mm_calibration_adapter.py` and `apps/api/services/pure_ode_runtime.py`
  - strategy racing + fingerprint memory in `apps/api/services/custom_calibration_orchestrator.py`
  - generic teacher-flux rescue for supported reactions in `apps/api/services/teacher_flux_generic.py`
  - worker job execution path in `apps/calibration-worker/main.py`
  - async orchestration UI in `apps/web/components/features/ParameterCalibration.tsx`
  - minimal RL triage environment in `services/robocop/calibration_triage_env.py`
- Validation:
  - `qa/robocop` now passes with 90 tests
  - local `apps/web` production build passes
  - the new calibration UI is deployed on `app.airbc.org`
- Remaining blocker:
  - production calibration proxy still returns `503` because the worker is not yet configured on the web deployment
- Next step:
  - connect the future Hetzner worker to production `web`

#### Agent-editable calibration policy
- Status: Full-file autonomy enabled for `src/MM_calibration.py`; guarded write path and Phase E patch loop implemented
- Goal:
  - allow bounded agent edits inside `src/MM_calibration.py` without opening the scientific ODE core
- Scope:
  - objective hierarchy
  - target routing
  - stage planning
  - ranking and diagnostics
- Hard boundary:
  - `src/equadiff_brodbar.py` remains read-only in the initial rollout
- Working spec:
  - `AGENT_EDITABLE_CALIBRATION_POLICY.md`
- Current implementation:
  - `src/MM_calibration.py` remains the only editable scientific-orchestrator file
  - the enforcement service in `services/robocop/calibration_edit_policy.py` now treats the full file as editable
  - the earlier zone markers remain as historical scaffolding but are no longer the active enforcement boundary
  - the calibration orchestration toolset now exposes `calibration_validate_agent_edit`
  - the guarded write path now goes through `calibration_apply_agent_edit`, which refuses to write any patch unless validation already passes
  - the new Phase E loop in `services/robocop/calibration_phase_e.py` now:
    - applies a bounded patch only after the edit gate passes
    - runs `py_compile`
    - runs Phase B scientific validation only after the patch is safely applied
    - keeps or reverts the patch automatically based on the decision policy
  - a first live Phase E smoke test has now been executed on a tiny diagnostics-only patch inside an allowed `MM_calibration.py` zone:
    - the edit gate accepted the patch
    - `py_compile` passed
    - Phase B ran end to end on the patched file
    - the decision came back `discard`
    - the patch was automatically reverted, leaving `src/MM_calibration.py` restored to its pre-smoke content
  - a first live scientific Phase E patch has now also been executed inside `fit_penalty_hierarchy`:
    - the patch reduced the adenylate pool trajectory penalty from `5.0` to `3.0`
    - the edit gate accepted the patch
    - `py_compile` passed
    - Phase B executed a real bounded phase-2 adenylate run plus seed/candidate `main.py` reruns
    - the candidate exactly reproduced the seed (`absolute_gain = 0.0`) and was classified `discard`
    - the patch was automatically reverted, leaving `src/MM_calibration.py` restored
  - a first live full-file Phase E patch has now also been executed on `src/MM_calibration.py`:
    - the patch changed stage-plan parameter resolution so explicit `include_params` can inject valid global parameters even when they are absent from the phase-local map
    - this specifically allowed `km_ADP_ATP` to enter a phase-2 direct adenylate seam that had previously failed to test it
    - the edit gate accepted the full-file patch and `py_compile` passed
    - the resulting candidate run did resolve and optimize `km_ADP_ATP`, but the final fit and pure-ODE behavior still exactly reproduced the seeded basin
    - the scientific decision came back `discard`, so the patch was automatically reverted
  - the current rollout still rejects any attempted edit to `src/equadiff_brodbar.py`
- Next step:
  - use the full-file autonomy carefully on `src/MM_calibration.py` to test higher-leverage calibration-flow edits, while continuing to keep `src/equadiff_brodbar.py` frozen

#### Fit-only true-ODE calibration regime
- Status: Implemented in `src/MM_calibration.py`
- Goal:
  - remove penalty dominance and rank candidates on experimental fit only, while still using the real Brodbar ODE even if evaluation becomes slower
- Current implementation:
  - `rank_loss` is now equal to `fit_loss`
  - regularization and physiological penalties are still reported for diagnosis, but no longer influence candidate ranking
  - acceptance is now fit-only: improved fit is accepted directly, and ties only use rank/tie logic
  - optimization now evaluates candidates with report-level ODE fidelity instead of the previous coarser fast/screen settings
  - `core_glycolysis_energy` and `glycolysis_extracellular` now weight `ATP`, `ADP`, `EGLC`, `PYR`, `PEP`, and `LAC` more aggressively
- Latest validation:
  - a fit-only true-ODE smoke run completed successfully into `Simulations/brodbar/calibration/fit_only_trueode_smoke/`
  - the run preserved the current adenylate seed with `0.0%` change, but the worst-fit metabolites are now surfaced directly by pure fit rather than penalty-heavy ranking
- Next step:
  - run the next longer fit-only calibration on a seam that can actually move `ATP/ADP`, `EGLC`, and `PYR/PEP/LAC` instead of reusing the already saturated adenylate micro-seam
  - the first longer fit-only combined true-ODE run has now completed into `Simulations/brodbar/calibration/fit_only_combined_trueode_longrun/`
  - outcome:
    - phase 1 (glucose + lower glycolysis + outlet) mostly rediscovered the known basin and stayed on a fit-only tie
    - phase 2 (adenylate + purine) produced the only real gain, improving baseline loss from `2.6264` to `2.6240`
    - total improvement stayed small (`0.1%`), which suggests the current long-horizon seed is still locally saturated even under pure-fit ranking
  - current unresolved targets remain:
    - `AMP`
    - `PYR`
    - `ADP`
    - `PEP`
    - `ATP`
    - `EGLC`
  - next step:
    - run `main.py` on the new fit-only candidate to inspect whether the pure ODE trajectories on `ATP/ADP`, `EGLC`, and `PYR/PEP/LAC` moved enough to justify a new seed
  - a more basin-focused follow-up has now completed into `Simulations/brodbar/calibration/fit_only_basin_targeted_longrun/`
  - outcome:
    - calibration fit improved dramatically from `2.6240` to `1.5317`
    - the direct phase-2 adenylate seam (`VAK2`, `VAK_rev`, `VNDPK`, `VAMPD1`, `VIMPH`) was the main driver of that gain
    - however, the pure `main.py` ODE check showed that this candidate is not promotion-ready as a stable default:
      - `ATP` finished lower than the previous fit-only seed
      - `ADP` still collapsed to zero
      - `EGLC` improved meaningfully
      - `PYR` worsened materially
      - `PEP` fell sharply
      - `LAC` changed only slightly
  - next step:
    - keep this candidate as informative evidence that the basin can be moved strongly in pure fit
    - do not promote it blindly without a new seam that preserves the `EGLC` gain while repairing the pure-ODE energy and pyruvate axis
  - a direct stabilization follow-up from that candidate has now completed into `Simulations/brodbar/calibration/fit_only_stabilization_longrun/`
  - outcome:
    - the narrow phase-1 stabilization seam (`VPK`, `VLDH`, `km_PYR`, `km_PEP`, `km_LAC`) exactly reproduced the seeded candidate
    - the direct phase-2 adenylate stabilization seam (`VAK2`, `VAK_rev`, `VNDPK`, `VAMPD1`, `VIMPH`) also exactly reproduced the seeded candidate
    - total loss remained `1.5317`, with identical protected metrics and the same parameter values
  - current conclusion:
    - the local stabilization pocket around the new fit-only basin is saturated too
    - the next useful move must change the hypothesis again rather than tightening the same energy/pyruvate micro-seam

#### Hybrid kinetics migration planning
- Status: Planning document added
- Goal:
  - open a safe path to evolve `src/equadiff_brodbar.py` beyond pure Michaelis-Menten without breaking state topology, indexing, or the main ODE workflow
- Working plan:
  - `HYBRID_KINETICS_MIGRATION_PLAN.md`
- Current recommendation:
  - first do a zero-math refactor that separates flux computation from `dxdt` assembly
  - then add neutral hybrid-capable wrappers on a tiny Tier-1 reaction subset before exposing new hybrid parameters to calibration
- Current implementation progress:
  - neutral hybrid-family wrappers are now present in `src/equadiff_brodbar.py` for:
    - `VEGLC`
    - `VELAC`
    - `VLDH`
  - the default families preserve the current MM behavior exactly
  - the official `src/main.py --model brodbar` ODE path still runs successfully with a real calibrated seed after this change

#### Ongoing / recent calibration run tracking
- Track:
  - candidate ID
  - run directory
  - current case status
  - final eval summary if produced
- Latest calibration correction:
  - `src/MM_calibration.py` now keeps the `glycolysis_extracellular` primary objective focused on a true-Ode extracellular/glycolysis/energy anchor set instead of silently widening back to all supported metabolites
  - pathway phase objectives now intersect user/custom target lists with the actual pathway group instead of letting a full uploaded target set flatten the phase structure
  - a seeded narrow phase-1 Km refinement on `km_GLC_transport`, `km_EGLC`, `km_LAC`, `km_PYR`, `km_GLC_HK`, `km_NADH_NAD`, and `km_NAD_NADH` improved total loss and recovered `GLC` / `LAC` shape without losing the strengthened extracellular objective hierarchy
  - a second micro follow-up on `vmax_VLDH`, `km_PYR`, `km_LAC`, `km_NADH_NAD`, and `km_NAD_NADH` returned the same retained solution, which suggests the current local optimum in that tiny subspace is already saturated
  - the chained phase-1 Vmax-anchor + narrow-Km session also converged back to the same retained solution as `eglc_elac_trueode_km_refine`, confirming that the current objective/seed combination is stable but locally saturated
  - a lower-glycolysis coupling probe on `vmax_VPGM`, `vmax_VENOPGM`, `vmax_VDPGM`, and `vmax_V23DPGP` cut total loss from `4.9375` to `4.2496` and sharply improved `P3G`, `ATP`, `AMP`, `IMP`, `LAC`, `EGLC`, and `ELAC`, but it also materially worsened `PEP` and `PYR`
  - a buffered lower-glycolysis follow-up that kept those four parameters live and added `vmax_VPK`, `vmax_VLDH`, `km_PEP`, and `km_PYR` improved total loss again to `4.1925`, rescued `PEP` strongly, and preserved the ATP/extracellular gains, but `PYR` worsened further and `B23PG` regressed materially
  - a subsequent narrow downstream recovery pass from that buffered candidate, holding the lower-glycolysis block fixed and allowing only `vmax_VLDH`, `km_PYR`, `km_LAC`, and tightly bounded `vmax_VPK` to move, converged back to the same retained solution and did not improve fit further
  - a focused `EGLC` recovery pass from that buffered candidate improved total loss again to `3.7619`, strengthened the glucose-side seam (`vmax_VEGLC`, `km_EGLC`, `km_GLC_transport`, `vmax_VHK`, `vmax_VPFK`, `km_GLC_HK`, `km_G6P`, `km_F6P`), and produced the current best seed
  - the Brodbar metabolite plotting/indexing path was explicitly audited: `EGLC=85` and `ELAC=87` in `BRODBAR_METABOLITE_MAP`, `main.py` inverts that map into `model['metab']`, and `visualization.py` plots `x[:, idx]` directly with that same name list
  - the only audit mismatch was a stale debug print in `main.py` using old hard-coded indices; that print path is now corrected and the real ODE state matrix is exported to `Simulations/brodbar/metabolites/all_metabolites.csv`
  - a final five-parameter glucose-only follow-up from the new `eglc_focused_recovery` seed (`vmax_VEGLC`, `km_EGLC`, `km_GLC_transport`, `vmax_VHK`, `vmax_VPFK`) converged back to the same retained solution, which indicates that this glucose-side seam is locally saturated at the current seed
  - a coupled glucose-to-lactate shape probe from the same `eglc_focused_recovery` seed, letting only `km_GLC_HK`, `km_G6P`, `km_F6P`, `km_PYR`, and `km_LAC` move, improved total loss from `3.7619` to `3.4925`
  - that shape probe materially improved `EGLC` and `LAC`, and the official ODE rerun now shows `EGLC` falling from `25.34` to `22.85` instead of staying almost flat
  - tradeoff: `ELAC` softened from a very strong `0.089` nRMSE to about `0.206`, so the next hypothesis should try to preserve the steeper `EGLC` slope without giving back too much extracellular lactate fit
  - a narrow ELAC recovery seam from that new seed (`km_LAC`, `km_PYR`, `vmax_VLDH`) converged back to the same retained solution, confirming that this local ELAC/lactate pocket is already saturated at the current seed
  - a broader ELAC rebalance seam from that same seed (`vmax_VPK`, `vmax_VLDH`, `km_PEP`, `km_PYR`) also converged back to the same retained solution, so the local PEP/PYR/LDH/PK pocket is saturated too
  - an upstream glucose-commitment / hexose-framing probe from that same seed (`vmax_VHK`, `vmax_VPFK`, `km_GLC_HK`, `km_G6P`, `km_F6P`) also reproduced the same retained solution, which confirms the current seed already contains that upstream basin too
  - a genuinely different phase-2 purine / adenylate seam from that same seed (`vmax_VAK`, `vmax_VAK2`, `vmax_VAMPD1`, `vmax_VIMPH`) improved the core-glycolysis-energy objective from `3.3780` to `2.8082`
  - that phase-2 seam improved glycolysis-energy, nucleotide-purine, and endpoint metrics materially while preserving the strong `EGLC`, `LAC`, and `ELAC` behavior from the glucose-shape seed
  - long-horizon hybrid follow-up from that phase-2 seed, using a stricter 42-day adenylate retention target, improved the long-horizon calibration objective from `2.9001` to `2.7402`
  - however, the pure `main.py` Brodbar ODE rerun still showed `ATP` and `ADP` collapsing toward zero by the end of the 42-day horizon, even though `AMP`/`IMP` improved somewhat and `EGLC`/`ELAC` remained stable
  - the attempted follow-up PYR/LAC outlet recovery stage from that long-horizon adenylate seed reproduced the same retained solution and did not improve the long-horizon objective further
  - current conclusion: the long-horizon phase-2 seed is informative but still not promotion-ready as the stable default because the pure ODE energy quartet remains biologically weak

---

### 3. Product Architecture Direction
#### Research mode
- Status: Defined structurally
- Modules:
  - Overview
  - Data Upload
  - Calibration Registry
  - Simulation
  - Flux Analysis
  - Pathway Visualization
- Sensitivity Analysis is archived from the main sidebar and remains only as a hidden legacy route/code path
- Pathway Visualization is the next active Research surface to refine

#### Monitoring mode
- Status: In progress; visible surfaces reorganized around Overview, Bag Repository, Quality Forecast, and Alerts
- Modules:
  - Overview
  - Bag Repository
  - Quality Forecast
  - Alerts
- Future gateway:
  - automation gateway (planned)
- Current implementation:
  - Monitoring Overview now acts as the command center with KPI strips, operational snapshot cards, recent activity, and future gateway framing
  - the active route cards underneath the hero stay focused on Bag Repository, Quality Forecast, and Alerts
  - the future gateway remains hidden rather than appearing as a live Monitoring page
  - Bag Repository now uses a backend-backed intake flow with server-side duplicate protection and a shared persisted inventory source
  - Quality Forecast now reads the same persisted bag inventory so newly created bags flow through to the predictive surface
  - Alerts now derives forecast-driven triage items from the same Monitoring inventory and exposes operator workflow actions
- Next implementation step:
  - keep alert workflow actions lightly persistent if backend writes are added later
  - keep the page constrained to monitoring-relevant forecast output and selected Research/Simulation inheritance
  - surface the alert queue, acknowledgements, linked bag context, and forecast explanation in one coherent workspace

#### RoBoCop role
- Status: Clarified
- RoBoCop is the central agent across the product, with Monitoring reserving a hidden future automation gateway slot
- Future two-mode logic:
  - Research
  - Monitoring

---

## Current Blockers
- No reliable authenticated automation path for full sidebar/session verification
- Some long-running scientific runs still require manual monitoring
- Monitoring pages still need product-level content and behavior

---

## Immediate Next Actions
1. Finish authenticated UI verification when a safe path exists
2. Continue product restructuring around Research / Monitoring modes
3. Expand Monitoring pages meaningfully
4. Keep strengthening RoBoCop as a central cross-module interpreter

---

## Validation Required Before Closing Major Work
- Type check
- Build verification
- Route/path verification
- Browser/UI verification when relevant
- Scientific run verification when relevant

---

## Recently Completed
- Sidebar restructure
- Route-backed navigation
- LangGraph + LangSmith first integration
- Per-node trace enrichment
- Mutation Agent v2
- Time-aware search policy
- Timeout-chain validation

---

## New Workstream
### Research Data Mode
- Status: In progress
- Goal:
  - make Bordbar/default data the fallback and custom uploaded data the active Research context when present
- Scope:
  - shared Research shell state
  - Data Upload activation flow
  - Simulation and Calibration
  - later Flux and Pathway interpretation
- Constraints:
  - upload parsing is not dataset activation
  - Bordbar/default flow must keep working when no custom dataset is active
  - one active dataset must drive all Research modules once selected
  - calibration work should follow `src/MM_calibration.py` as the canonical core path
  - the current FastAPI calibration route still appears to be a separate adapter path and needs reconciliation
- Current state:
  - calibration now routes through a thin adapter into `src/MM_calibration.py`
  - research mode metadata is threaded from the Research shell into calibration
  - simulation now applies the active custom dataset to the solver seed and reports whether it was actually used
  - default Bordbar/reference behavior remains the fallback when no active dataset is present
  - Calibration Registry now includes a visible handoff into the calibration workspace so uploaded data has an obvious next step before simulation
  - calibration objectives now ignore pre-day-1 custom dataset points so zero-based uploaded time grids do not trip `t_eval`
  - Calibration Registry now also shows the active research dataset banner so the uploaded file remains visibly present after navigation
  - Research dataset state now restores directly from persisted browser storage so the same uploaded file survives the registry-to-calibration handoff in the live tab
  - Calibration Registry hero chips now explicitly surface `Custom user data active` or `Bordbar fallback active` in the top-left summary row
  - Research dataset persistence now uses a hydration-safe store snapshot so SSR and client rendering stay aligned
  - Simulation now carries the latest successful calibration snapshot when it matches the active dataset, so the ODE can run with the optimized parameter set instead of only the default/autoload path
  - RoBoCop Simulation context now carries explicit provenance for active dataset, dataset fallback, calibration source, and calibrated parameter state
  - RoBoCop chat and analytical summary now explain whether a run used Bordbar defaults or custom uploaded data, and whether the latest calibration was applied
  - Live smoke validation confirmed the custom dataset flow reaches both `/simulate/` and `/robocop/research/chat` with truthful provenance responses
  - Completed custom-data calibration was validated end to end in the live Research UI using `Test_Custom_Data.csv`, with `Joint Vmax + Km` and result-aware RoBoCop interpretation
  - Data Upload now reads the same persisted active dataset through the shared research dataset store, so the custom label can remain visible after navigation
  - Flux Analysis now carries the same provenance-aware, result-grounded RoBoCop interpretation pattern as Simulation and Calibration, including dataset state, calibration linkage, dominant pathway, and top flux signals
  - Next steps:
  - verify the custom upload path end to end in the browser if the current upload surface still looks flaky
  - carry the same provenance/result pattern into Pathway Visualization and any remaining active Research page
  - keep threading the active data mode and result provenance into LangGraph / LangSmith traces

### Pathway Visualization
- Status: Next active Research target
- Goal:
  - inspect the current pathway network page and then extend RoBoCop with provenance-aware interpretation of the network map
- Scope:
  - page structure and network readability
  - dataset/calibration provenance
  - RoBoCop setup/result context
- Current findings:
  - the backend pathway map is still a hand-curated KEGG-style subset inside `streamlit_app/core/pathway_visualization.py`
  - the route already exposes `/pathway/network-state`, which is a useful seam for future simulation playback if the page starts consuming time-series state
  - the current SVG graph is fine for a small static map, but it is not enough for a complete animated metabolic network surface
- Recommended next decision:
  - define a canonical model-derived pathway graph registry first, then decide whether Cytoscape.js or a similar graph engine should replace the current static SVG viewport
- Immediate next step:
  - diagnose the current Pathway Visualization payload, UI hierarchy, and assistant context seam

### Calibration Result Awareness
- Status: Completed live validation
- Goal:
  - make RoBoCop explain completed calibration runs truthfully, not only the setup state
- Current state:
  - the canonical calibration taxonomy adapter is cached and fast enough for live page loads
  - the Calibration page now loads canonical taxonomy and strategy families from the MM calibration backend
  - a completed calibration run is visible in the browser and RoBoCop can explain the result, fit quality, data provenance, and strategy used
  - the live completed run validated the result-aware path end to end: setup -> run -> result -> RoBoCop interpretation
  - the custom-data completed path was also validated in the browser with the same result-aware provenance chain
- Result snapshot:
  - run completed successfully on Bordbar/reference data
  - strategy used: Joint Vmax + Km
  - sample completed run showed final loss 4.2543 and R² -0.3420 after 1 iteration
  - RoBoCop correctly distinguished setup-only context from completed-result context
- Next steps:
  - extend the same result-awareness pattern into historical Calibration Registry entries
  - keep setup, running, completed, and failed states explicit in both the page and RoBoCop

### Flux Analysis Provenance
- Status: Completed live validation
- Goal:
  - make RoBoCop explain Flux Analysis truthfully using the active dataset, calibration state, and actual flux outputs
- Current state:
  - Flux Analysis now builds a compact provenance/result context for RoBoCop
  - the page distinguishes setup-only, running, completed, and failed states
  - RoBoCop can answer result questions using dominant pathway, top flux signals, dataset provenance, and calibration linkage
- Result snapshot:
  - Flux Analysis completed successfully on Bordbar/reference data in the live browser
  - dominant pathway surfaced as Glycolysis with VPGLS as the top flux signal in the validated run
  - RoBoCop responded with a Flux-specific grounded interpretation rather than a generic fallback
- Next steps:
  - extend the same provenance-aware interpretation pattern to Sensitivity Analysis and Pathway Visualization
  - keep result-grounded context separate from UI decoration so the assistant remains scientifically honest

### Parameter Optimization Surface
- Status: In progress
- Goal:
  - map the divergence between the web Parameter Optimization page and the canonical calibration/agentic parameter-selection system
- Current findings:
  - the web page now reads a canonical taxonomy adapter from `GET /calibration/available-parameters`
  - the adapter derives the Vmax/Km registry from `src/MM_calibration.py` and keeps a recommended quick-pick subset plus the full canonical inventory
  - the UI method control is now a canonical `Optimization Strategy` selector backed by the strategy families/templates exposed from `src/MM_calibration.py`
  - the canonical core still supports a wider taxonomy and staged parameter classes (`vmax`, `km`, `regulation`, `transport`, `degradation`, `effective_misc`)
  - the bounded autosearch agent remains separate and mutates run-level strategy knobs, not the kinetic parameter list itself
- Next step:
  - confirm the long-running calibration run completes cleanly with the canonical strategy selector, then decide whether to surface strategy provenance / triage metadata separately
  - keep calibration provenance explicit in the page summary and RoBoCop chat: current selection, canonical taxonomy, optimization strategy, and loaded calibration result should stay aligned

### Flux Analysis Page Redesign
- Status: Completed
- Goal:
  - redesign the Flux Analysis page into a modern, intuitive scientific workspace without changing the flux solver or provenance contract
- Scope:
  - Flux Analysis page layout and presentation
  - clearer scientific hierarchy for pathway summaries, key metrics, and reaction detail
  - discreet RoBoCop integration that stays visually secondary
- Outcome:
  - the page now opens with a premium hero and compact provenance snapshot
  - flux results are grouped into a clearer scientific summary and ranked pathway explorer
  - dominant pathway, total flux, top reaction, and applied concentrations are easier to scan
  - RoBoCop remains discreet and contextual rather than visually dominant
- Validation:
  - TypeScript check passed
  - live browser render confirmed the redesigned surface and assistant fit
  - flux provenance/result context remained intact

## Notes
This file should stay focused on:
- current state
- active work
- blockers
- next actions

Do not turn this into a lessons file or a full architecture manual.
- Pathway graph interaction is now the next refinement: use label offsets to reduce collisions, make metabolite/reaction clicks selectable, and keep the details rail compact and secondary to the graph.
- Preserve the replay source and network-state projection while highlighting the selected node or edge.
## 2026-03-20 calibration provenance for RoBoCop
- Keep the Calibration page RoBoCop context aligned with the selected canonical taxonomy, selected parameters, and optimization strategy.
- RoBoCop should distinguish setup-only calibration states from loaded or completed calibration results.
- Preserve the split between calibration setup provenance and the separate autosearch/triage layer.
## Pathway Visualization Update
- Pathway Visualization now has a compact provenance/result summary and a discreet RoBoCop lens wired to the shared research context.
- Latest simulation snapshot persistence now uses a synchronous external-store reader so Pathway can pick up custom-data replay immediately from browser storage.
- Pathway replay-aware RoBoCop now surfaces the current frame/timepoint, replay source, and path provenance from the latest simulation snapshot without manual browser-store seeding.
- Pathway Visualization now uses a metabolite/reaction projection from the canonical registry so reactions appear as first-class graph nodes and the page speaks in metabolites/reactions instead of generic edges.
- Pathway interaction now also includes quick-select chips and larger hit targets for metabolites/reactions so selection remains easy to verify while the graph stays the main scientific surface.
- Pathway now needs a compact/full toggle: keep the replay behavior, but let researchers switch between the full registry map and a compact bridge-metabolite overview that highlights the principal connector metabolite for each pathway group.
- Pathway compact mode is now graph-first rather than card-first: it renders a reduced bridge graph with one connector metabolite per pathway group, keeps zoom controls in the viewport, and leaves the compact atlas as a secondary rail.
- The local API CORS policy should allow any localhost/127.0.0.1 dev port so the Pathway browser session can load the graph on whichever frontend port is active.

## 2026-03-22 Bag Repository inventory surface
- Bag Repository now reads like a real biobank inventory workspace instead of a placeholder list.
- Keep the page centered on a KPI strip, search and status filters, a selectable inventory table, and a right-side detail rail.
- Leave room in the details rail for future bag status, storage context, quality state, linked forecast, linked alerts, linked runs, and monitoring events.
- The page should stay connected to Quality Forecast and Alerts so the Monitoring flow remains inventory-first rather than CRUD-first.
## Monitoring Alerts Persistence
- Alerts workflow state now persists in the backend DB layer instead of runtime JSON.
- Workflow history records actual transitions only; no-op updates do not create duplicate rows.
- The current implementation uses Supabase when the schema is available and SQLite as the local development DB fallback.
- Next Monitoring follow-up: consider a true audit/history UI and later move the workflow store to a first-class shared database table set everywhere.
- Supabase provisioning status:
  - the repo includes the SQL setup and the Supabase CLI is available
  - the environment does not expose a usable Supabase access token or direct DB password
  - the Supabase service-role key is not accepted as a management token
  - direct DB host attempts for the project ref timed out or failed DNS resolution
  - the shared Supabase path remains unprovisioned from this environment until a real Supabase token or database password is provided
## Calibration follow-up
- The custom-data calibration path now routes through a profile-aware helper in `src/MM_calibration.py` so extracellular and energetic targets get differentiated treatment.
- The web adapter now defaults to `vmax_then_km` and passes calibration profile signals through explicitly instead of hard-coding `all` / `joint_vmax_km`.
- ATP/ADP remain structurally stubborn on the custom dataset; the strongest gain in this pass came from lower-glycolysis and extracellular-relevant behavior rather than a clean adenylate rescue.
- Next calibration iteration should stay narrow: target datasets with explicit extracellular trajectories, then test whether the profile routing improves Monitoring-facing glucose/lactate forecasting without widening compensatory parameters.

## 2026-03-27 Hermes Phase B comparison fix
- Status: Completed and revalidated on a real live Phase A / Phase B smoke test
- What changed:
  - Phase A / Phase C stage plans now carry the seed calibration context (`seed`, `t_max`, `curve_fit_strength`)
  - Phase B now forwards that context back into `src/MM_calibration.py` instead of falling back to default CLI values
  - Phase B fit comparison now uses the candidate run's own `results.tsv` baseline/final pair as the primary apples-to-apples comparison basis
- Real rerun result:
  - the same live adenylate Phase A choice was executed again after the fix
  - the candidate reproduced the seed under the same calibration context and is now classified `discard`
  - this is more scientifically reliable than the earlier `informative`, which had been inflated by a mismatched comparison context
- Next step:
  - keep using the fixed Phase B gate for future Hermes live trials
  - if we want a stronger live proof next, run a Phase A/B trial on a seam that is expected to move rather than one that is already locally saturated
