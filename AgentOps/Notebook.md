# AgentOps Notebook

Scientific progress notes for the bloodai / RoBoCop platform.

---

## 2026-04-17

Delivered the custom-data calibration orchestration stack from P3a through P7 and deployed the new calibration surface to production `web`.

What improved:
- custom-data calibration can now run a true pure-ODE replay after fitting and derive a real `combined_triage`
- the worker path now supports `strategy_race` orchestration, dataset fingerprint memory, and bounded teacher-flux rescue for supported reactions
- the Calibration page now exposes single-run vs worker-race execution, pure-ODE replay, teacher-flux rescue, orchestration summaries, and richer planner/triage evidence
- a minimal RL triage environment now exists so future policy learning can reuse the same verdict contracts

What was validated:
- `qa/robocop` passes with 90 tests after adding orchestration, teacher-flux, and RL-env coverage
- local `apps/web` production build passes
- the updated Calibration page is deployed on `app.airbc.org`

What remains open:
- the production `web` proxy still returns `503` for `/api/calibration/*` because `CALIBRATION_API_BASE_URL` and `CALIBRATION_API_SHARED_SECRET` are not yet configured against a live worker
- the next step is therefore infra, not product-surface code: wire the future Hetzner worker into production and rerun end-to-end smoke tests

Why it matters:
- the custom-data calibration system now selects and remembers candidates using full physiological evidence instead of fit-only wins
- the product plane is ready for long-running orchestration without another UI rewrite
- the remaining production blocker is narrow and explicit

---

## 2026-03-21

Completed a cross-module provenance pass for Research calibration and registry flows.

What improved:
- RoBoCop now distinguishes setup-only, running, completed, failed, and historical registry states.
- Calibration and Simulation now share explicit active-dataset and calibration provenance.
- Calibration Registry now reads as a historical ledger with comparison lanes and a clear handoff back into calibration.

What was validated:
- live calibration-result interpretation on the Calibration page
- live custom-data Simulation provenance
- live registry-ledger interpretation without calibration-fit confusion

Why it matters:
- the platform can now explain scientific state truthfully across workflow stages
- custom user data no longer disappears behind Bordbar/default assumptions
- the research shell is becoming a coherent provenance-aware workflow layer rather than isolated pages

## 2026-03-21

Extended the Pathway Visualization page into a provenance-aware network atlas.

What improved:
- the network map now carries a compact dataset/calibration provenance snapshot beside the graph
- RoBoCop can interpret the pathway map from the same shared research context without becoming the visual center
- the page now separates structural network reading from broader Research workflow state

What was validated:
- the Pathway page renders with the new provenance summary and RoBoCop lens
- the graph remains the main scientific focus
- the assistant context now reflects the current research mode and network scale

Why it matters:
- pathway interpretation is now aligned with the rest of the Research provenance story
- the workspace can explain structural maps truthfully, not just compute them
- future cross-module interpretation can reuse the same compact context pattern

## 2026-03-21

Clarified the scientific direction for Pathway Visualization as a future simulation playback surface.

What improved:
- the current pathway core is now recognized as a hand-curated KEGG-style subset rather than a canonical network source
- the simulation engine already exposes the time-series data needed for metabolite playback
- the router-level `/pathway/network-state` seam can project concentrations and fluxes onto the graph without inventing a new protocol

What was validated:
- the existing pathway UI and backend route structure were inspected end to end
- the current visualization can be treated as a starting shell, not the final scientific source of truth
- the animation path should be driven from shared simulation state rather than page-local memory

Why it matters:
- the Pathway module is moving from a static map toward a scientific replay surface
- the network can become faithful to the modeled RBC system instead of only looking KEGG-like
- future work can focus on canonical graph truth first, then animation and interaction second

## 2026-03-21

Redesigned Flux Analysis into a more modern scientific workspace.

What improved:
- Flux results now read through a clearer hierarchy: provenance, summary, ranked pathways, then reaction-level detail
- dominant pathway and total-flux signals are visually emphasized instead of being buried in the page
- RoBoCop remains discreet and contextual, so the page still feels science-first

What was validated:
- live Flux page render with the redesigned scientific layout
- Flux provenance and result state still carried through to RoBoCop
- assistant interpretation stayed grounded in the actual pathway totals and top signals

Why it matters:
- flux interpretation is now easier to scan and explain
- the Research workspace is moving from functional pages toward a polished scientific surface
- the layout supports future cross-module interpretation without turning RoBoCop into the visual center of the page

Pruned the Research sidebar to the currently active scientific surfaces and left Pathway Visualization as the next interpretation target.

Why it matters:
- the workspace reads more like a live scientific flow than an archive of all historical modules
- researchers are guided toward the active analysis path without losing access to the underlying implementation routes

---

## 2026-03-21

Extended provenance-aware interpretation to Flux Analysis and validated the live assistant path.

What improved:
- Flux Analysis now carries a compact result context with dataset provenance, calibration linkage, dominant pathway, and top flux signals
- RoBoCop now distinguishes Flux setup, running, completed, and failed states
- Flux chat can explain Bordbar/reference versus custom upload provenance truthfully

What was validated:
- live Flux page render with result summary and provenance cards
- live RoBoCop chat answering a Flux-specific prompt from the completed result context
- fallback behavior no longer collapses to a generic empty-answer response when the backend is current

Why it matters:
- Flux Analysis now joins Simulation and Calibration as a provenance-aware Research surface
- the assistant can interpret pathway fluxes instead of only describing a chart
- the research workflow is closer to a coherent cross-module scientific narrative

---

## 2026-03-21

Validated the full completed custom-data calibration path on a fresh backend and in the live Research UI.

What improved:
- custom uploaded data can complete calibration with the canonical MM calibration path
- the completed result keeps dataset provenance, strategy provenance, and fit-quality provenance together
- RoBoCop on Calibration now explains completed custom-data runs truthfully

What was validated:
- custom dataset `Test_Custom_Data.csv` activated in Research context
- completed calibration using `Joint Vmax + Km`
- result-aware RoBoCop interpretation for the completed custom-data run

Why it matters:
- the platform now proves custom-data science can complete, not just start
- result awareness is now grounded in the same provenance contract as setup and simulation
- the calibration workflow is closer to a publishable, auditable research story
- Research platform note: custom-data simulation snapshots now flow into Pathway replay through a synchronous browser-store reader, making the simulation-to-pathway handoff fully hands-off after upload and run.

### 2026-03-21 Pathway replay-aware RoBoCop
- Improved the Pathway Visualization surface so RoBoCop can explain the active replay frame, timepoint, and replay source directly from the latest simulation snapshot.
- Validated the custom-data replay handoff end to end in the live browser: uploaded dataset, Simulation, browser-stored latest snapshot, Pathway replay, and RoBoCop provenance all remained coherent.
- This matters because the Research workspace now communicates a fuller scientific narrative from upload to simulation to pathway interpretation without manual seeding.

### 2026-03-22 Pathway reaction-node graph
- Upgraded Pathway Visualization from a compact edge sketch to a metabolite/reaction projection so enzyme identity is visible as part of the graph structure.
- Validated the graph readability change in the live browser: the page now shows reaction counts, reaction-labeled nodes, and clearer pathway summaries while keeping replay controls and RoBoCop secondary.
- This matters because Pathway is moving closer to a real scientific network surface instead of a mere connection diagram, which should make future replay and interpretation easier to trust.

### 2026-03-22 Pathway interaction layer
- Added click-to-inspect selection for metabolite circles, reaction diamonds, and pathway edges so the graph can answer “what am I looking at?” without obscuring the network itself.
- Reduced label crowding by offsetting labels away from the node center and surfacing the chosen entity in a compact details rail beside the graph.
- This matters because a clearer interaction layer makes the scientific graph more legible without changing the underlying pathway truth or replay provenance.
- Added quick-select chips for metabolites and reactions so the interaction layer remains easy to verify even when the graph is visually dense.

### 2026-03-22 Pathway compact/full overview
- The Pathway module now supports a compact bridge-metabolite atlas alongside the full registry map, which gives researchers a faster way to see how the RBC model connects across pathway groups.
- This matters because the compact view turns the model into a better communication surface for cross-pathway reasoning without sacrificing the replay-aware full network.
- The bridge-metabolite framing is especially useful for explaining transitions like Glycolysis ↔ Pentose Phosphate through G6P/R5P-style connectors while keeping the underlying registry unchanged.
### 2026-03-22 Pathway compact graph milestone
- Pathway Visualization now has a registry-backed compact graph mode that keeps the network scientific rather than collapsing into a card-only summary.
- The compact view surfaces one principal connector metabolite per pathway group, while the full model remains available for detailed inspection.
- Zoomable graph playback plus the compact/full split make the Pathway surface more useful for scientific interpretation without losing provenance or RoBoCop grounding.

### 2026-03-22 Monitoring surface reorg
- Monitoring now reads more coherently as an operations area centered on Overview, Bag Repository, Quality Forecast, and Alerts.
- Hermes is reserved as the future messaging gateway instead of being presented as a live Monitoring assistant page.
- This matters because the monitoring shell now communicates a clearer operational story without mixing in an active assistant placeholder.

### 2026-03-22 Monitoring Overview command center
- The Overview page now acts as a dashboard-style command center instead of a generic landing surface.
- KPI tiles, operational snapshot cards, recent activity, and future gateway framing make the page feel like a real monitoring cockpit.
- This matters because Monitoring can now introduce live bag, forecast, and alert data without rethinking the page hierarchy.

### 2026-03-22 Bag Repository inventory architecture
- The Monitoring Bag Repository now provides a serious inventory surface with a KPI strip, a searchable table, a selected-bag detail rail, and forecast/alert handoff cards.
- This matters because Monitoring now has a credible inventory foundation that can feed Quality Forecast and Alerts without needing a separate CRUD screen.
### 2026-03-22 Quality Forecast predictive bridge
- The Monitoring Quality Forecast page now acts as the constrained predictive bridge between Bag Repository and Alerts.
- It reuses selected Research/Simulation trend-shaping logic, but only through a limited extracellular biomarker panel and a single selected bag context.
- This matters because Monitoring can now explain future bag quality in operational terms while remaining clearly separate from the full Research simulation workspace.

### 2026-03-22 Monitoring bag intake backend
- The Bag Repository intake flow now writes through a backend create/read path instead of relying on localStorage as the source of truth.
- Newly created bags persist into the shared Monitoring inventory and remain visible in Quality Forecast through the same inventory source.
- This matters because Monitoring now has a credible operational inventory backbone that can grow into forecast and alert workflows without rewriting the page structure.

### 2026-03-22 Monitoring Alerts triage surface
- Alerts now turns forecast-derived Monitoring risk into a prioritized review queue with a selected-alert detail rail and operator workflow actions.
- Biological risk and workflow state are modeled separately, which keeps the triage story scientifically honest while still being operationally useful.
- This matters because Monitoring now closes the loop from bag intake to quality forecast to actionable triage, making the product feel like a real operational surface rather than a collection of pages.
## Monitoring Alerts Audit Trail
- Alerts now carries a persistent operator workflow state that survives reloads and stays separate from forecast-derived biological severity.
- The minimal history trail is enough to show state transitions without turning Alerts into a full audit system yet.
- The current Monitoring backend can fall back from Supabase to a local SQLite store in development when the remote workflow tables are not provisioned.

## 2026-03-23

Attempted to provision Monitoring Alerts workflow persistence onto the shared Supabase database path.

What happened:
- the repo already contains the SQL setup for workflow-state and workflow-history tables
- the Supabase CLI is available in this environment
- the Supabase service-role key is not accepted as a management API token
- the environment does not expose a usable Supabase access token or direct Postgres password
- direct DB host attempts for the project ref failed DNS resolution or timed out on the database port

Why it matters:
- the Monitoring persistence code is ready for the shared Supabase path, but the remote database cannot be provisioned from this environment until a real Supabase token or DB password is available
- until then, the local SQLite fallback remains the only operational development path
## Calibration notebook
- The current custom-data calibration pass is profile-aware and should be treated as a routing improvement, not just a parameter sweep.
- When extracellular data are present, use the `glycolysis_extracellular` profile so Monitoring-relevant glucose/lactate behavior gets first-class weighting.
- When the dataset is ATP/ADP-heavy, the `core_glycolysis_energy` profile is the right anchor, but the current fixture still shows a structural ATP plateau.
- Lower-glycolysis improvements (PEP, PYR, F6P, lactate) were more reliable than widening adenylate bridge parameters; the acceptance gate protected the protected core when bridge widening degraded metrics.

## 2026-03-25

Implemented the missing overnight-session layer for bounded autosearch, using Karpathy-style autoresearch runs as inspiration without replacing the local scientific safety boundaries.

What improved:
- the existing bounded LangGraph cycle can now be run repeatedly in one CLI session
- `Keep` candidates are promoted as the next base policy, which lets the search advance configuration state overnight
- every session writes a durable JSON summary so the run can be inspected the next morning
- parent-guided multi-field proposals are now filtered down to effective mutations before scoring or promotion

What was validated:
- multi-iteration dry runs completed cleanly across repeated bounded graph invocations
- promoted candidate policies advanced across iterations instead of reusing the original base every time
- session summaries were written under `Simulations/brodbar/autoresearch/agent_orchestration/sessions/`

Why it matters:
- the repo now has a real bounded analogue to the “let it run overnight, inspect the branch in the morning” workflow from `autoresearch`
- the search stays scientifically disciplined because it still mutates only generated policies/manifests, not the protected scientific core
- the next calibration/autosearch step can focus on real overnight evaluation instead of re-implementing loop mechanics

Refocused `glycolysis_extracellular` calibration on the true ODE extracellular anchor set instead of letting the primary objective widen back to the entire measured Bordbar panel.

What improved:
- the primary `glycolysis_extracellular` objective now concentrates on the coupled extracellular/glycolysis/energy targets that actually matter for EGLC and ELAC
- pathway phase objectives now intersect uploaded/custom target lists with the phase-specific pathway groups instead of flattening into one broad target list
- a focused `vmax_only` Brodbar run kept the true ODE path and produced strong extracellular fits with `EGLC` nRMSE about `0.071` and `ELAC` about `0.089`

What was validated:
- `src/MM_calibration.py` still compiles
- the true ODE calibration run completed on Bordbar data with the narrowed objective
- the resulting report shows the primary target set explicitly reduced to `GLC, G6P, F6P, F16BP, P3G, B23PG, P2G, PEP, PYR, LAC, ATP, ADP, AMP, IMP, EGLC, ELAC`

Why it matters:
- Monitoring depends heavily on extracellular signals, so keeping EGLC/ELAC as first-class calibration anchors should improve the realism of downstream forecasting inputs
- the true ODE already had enough structure to fit extracellular curves well; the important fix was making the objective hierarchy reflect that scientific priority

Ran the next narrow phase-1 Km refinement seeded from the extracellular-anchored Vmax result.

What improved:
- a seven-parameter phase-1 Km pass improved total loss from about `5.075` to `4.938`
- `GLC` recovered from about `0.583` nRMSE to about `0.303`
- `LAC` recovered from about `0.960` nRMSE to about `0.836`
- the extracellular monitor metric improved from about `0.546` to about `0.541`

What changed:
- refined only `km_GLC_transport`, `km_EGLC`, `km_LAC`, `km_PYR`, `km_GLC_HK`, `km_NADH_NAD`, and `km_NAD_NADH`
- kept the patched extracellular primary objective and the true Brodbar ODE path intact

Why it matters:
- the Vmax anchor plus narrow Km follow-up is behaving like a useful two-step extracellular calibration recipe
- `EGLC` / `ELAC` stayed strong while the coupled intracellular glucose/lactate shape improved enough to make the calibration more useful for downstream Monitoring signals

Ran one more micro follow-up in the LDH/lactate subspace, seeded from the Km-refined result.

What happened:
- refined only `vmax_VLDH`, `km_PYR`, `km_LAC`, `km_NADH_NAD`, and `km_NAD_NADH`
- the retained result stayed effectively identical to the seeded `eglc_elac_trueode_km_refine` solution
- total loss stayed about `4.9375`, with the same protected metrics and the same top metabolite errors

Why it matters:
- this tiny lactate/LDH-local search region appears locally saturated for the current objective and seed
- the right next move is no longer “squeeze the same five parameters harder”
- the next useful search should either chain the successful Vmax+Km recipe in one longer run or shift to a nearby coupled hypothesis such as lower-glycolysis / upstream-glucose shape

Ran the longer chained phase-1 session that combined the successful extracellular Vmax anchor and the successful narrow Km refinement, seeded from the current best result.

What happened:
- the chained run reproduced the same retained solution and the same final loss as `eglc_elac_trueode_km_refine`
- both stage 1 and stage 2 accepted the same already-retained parameter values from the seed
- the final protected metrics and top metabolite errors stayed effectively unchanged

Why it matters:
- the extracellular-anchor recipe is stable, not fragile
- but the current seed/objective combination appears to be sitting in a local optimum that repeated Vmax→Km chaining will not escape on its own
- the next useful calibration hypothesis should move to a different coupled subsystem rather than repeating the same chain from the same basin

Ran a focused lower-glycolysis coupling probe from the current best extracellular seed.

What improved:
- a phase-1 probe on `vmax_VPGM`, `vmax_VENOPGM`, `vmax_VDPGM`, and `vmax_V23DPGP` reduced total loss from about `4.9375` to about `4.2496`
- `P3G` improved sharply from about `23.32` nRMSE to about `1.00`
- `ATP` improved from about `0.243` to about `0.179`
- `AMP`, `IMP`, `LAC`, `EGLC`, and `ELAC` also improved

What regressed:
- `PEP` worsened from about `0.299` to about `4.832`
- `PYR` worsened from about `0.614` to about `1.939`
- `GLC`, `ADP`, `B23PG`, and `G6P` softened slightly

Why it matters:
- lower glycolysis is clearly a real lever for the extracellular and energetic fit, not just noise
- but this part of the network behaves like a tradeoff surface: rescuing `P3G` and ATP too aggressively can distort `PEP` / `PYR`
- the next useful move should preserve this lower-glycolysis insight while re-coupling it to downstream buffering rather than keeping these four Vmax terms isolated

Ran a buffered lower-glycolysis follow-up from the informative lower-glycolysis candidate.

What improved:
- adding `vmax_VPK`, `vmax_VLDH`, `km_PEP`, and `km_PYR` reduced total loss again from about `4.2496` to about `4.1925`
- `PEP` recovered sharply from about `4.83` nRMSE to about `0.63`
- `P3G` improved further from about `1.00` to about `0.83`
- ATP remained strong and improved slightly again
- `LAC`, `EGLC`, and `IMP` also improved a bit further

What regressed:
- `PYR` worsened again, from about `1.94` to about `2.22`
- `B23PG` regressed materially from about `0.07` to about `0.28`
- `ELAC` softened slightly while staying strong overall

Why it matters:
- the downstream buffering hypothesis was directionally right: it rescued the `PEP` failure from the raw lower-glycolysis probe
- but the system is still redistributing error rather than eliminating it, with `PYR` and `B23PG` becoming the new stress points
- the next calibration move should shift toward pyruvate/lactate or phase-coupling hypotheses rather than adding still more freedom to the same lower-glycolysis pocket

Ran the next narrow downstream recovery pass from the buffered candidate, while holding the lower-glycolysis block fixed.

What was tested:
- only `vmax_VLDH`, `km_PYR`, `km_LAC`, and a tightly bounded `vmax_VPK` were allowed to move
- the buffered candidate stayed as the seed and the lower-glycolysis VPGM/ENOPGM/DPGM/23DPGP block was left fixed

What happened:
- the optimizer converged back to the same retained buffered solution
- total loss stayed at about `4.1925`
- the key metabolite profile stayed effectively unchanged

Why it matters:
- the next gain is not hiding in that tiny downstream recovery pocket
- `PYR` is still the main unresolved distortion sink after the buffered run, but it will need a different coupling hypothesis than simply re-optimizing `VLDH`, `km_PYR`, `km_LAC`, and `VPK`

Added a full Brodbar ODE trajectory export to the main simulation path and reran the improved-parameter simulation through `src/main.py`.

What improved:
- `src/main.py` now writes `Simulations/brodbar/metabolites/all_metabolites.csv` directly from the same `x` matrix that feeds the metabolite plotting code
- this makes it possible to audit suspicious curves like `EGLC` and `ELAC` without guessing from the figure alone

What was validated:
- the improved calibrated parameter set was loaded into the Brodbar ODE through `--load-params`
- the metabolite plots still use the direct `solve_ivp` output from `equadiff_brodbar`
- the exported `all_metabolites.csv` confirms that the plotted `EGLC` curve is indeed the real ODE trajectory, not a plotting artifact

Why it matters:
- `EGLC` is still scientifically bad in the current seed, but now that conclusion is fully auditable from the official simulation export
- the next calibration step can focus on fixing the real ODE behavior instead of doubting the plotting pipeline

Completed an explicit Brodbar metabolite-index audit before the next glucose-side calibration pass.

What was validated:
- `BRODBAR_METABOLITE_MAP` in `src/equadiff_brodbar.py` defines `EGLC = 85` and `ELAC = 87`
- `src/main.py` builds `model['metab']` by inverting that exact index map
- `src/visualization.py` plots `x[:, idx]` and titles it with `model['metab'][idx]`, with no reordering in between
- the `FUM / RIB / SUCARG / CYT / EGLC / ENH4 / ELAC / EADO / EADE` page ordering therefore matches the real ODE state order

What was corrected:
- `src/main.py` still had stale hard-coded debug prints like `EGLC (x[62])` and `ELAC (x[68])`, which were misleading even though plotting was correct
- those debug prints now use `BRODBAR_METABOLITE_MAP`, so the runtime audit output matches the actual Brodbar state indices

Why it matters:
- the plotting path for `EGLC` and `ELAC` is now both scientifically auditable and human-auditable
- if `EGLC` still looks shallow after the next run, we can treat it as a real model/calibration issue with more confidence

Ran a final narrow glucose-side follow-up from the new `eglc_focused_recovery` seed.

What was tested:
- only `vmax_VEGLC`, `km_EGLC`, `km_GLC_transport`, `vmax_VHK`, and `vmax_VPFK` were allowed to move
- the run kept the patched `glycolysis_extracellular` routing and the same true ODE path

What happened:
- the optimizer converged back to the same retained `eglc_focused_recovery` solution
- final loss stayed at about `3.7619`
- the retained parameter values for that seam stayed the same:
  - `vmax_VEGLC = 1.412739`
  - `km_EGLC = 28.271243`
  - `km_GLC_transport = 3.499915`
  - `vmax_VHK = 0.215124`
  - `vmax_VPFK = 1.663293`

Why it matters:
- the current glucose-side seam is locally saturated at the new seed
- repeating the same narrow glucose-only pass is unlikely to rescue the still-shallow `EGLC` trajectory further
- the next useful move should change the hypothesis rather than squeezing the same five parameters again

Ran the next coupled glucose-to-lactate shape probe from the same `eglc_focused_recovery` seed.

What was tested:
- only `km_GLC_HK`, `km_G6P`, `km_F6P`, `km_PYR`, and `km_LAC` were allowed to move
- the glucose-side Vmax seam stayed fixed at the improved `eglc_focused_recovery` values

What improved:
- total loss improved from about `3.7619` to about `3.4925`
- `EGLC` improved to about `0.0436` nRMSE
- `LAC` improved sharply to about `0.0672` nRMSE
- `endpoint_nrmse` improved from about `0.5885` to about `0.5134`
- the official ODE rerun now shows `EGLC` dropping from `25.34` to about `22.85` over the run, which is materially steeper than the previous shallow trace

What regressed:
- `ELAC` softened from about `0.089` nRMSE to about `0.206`
- `extracellular` aggregate worsened slightly from about `0.5405` to about `0.5525`, even though the glucose side improved

Why it matters:
- the shallow `EGLC` problem is not frozen; the coupled glucose/lactate Km seam can move it in the right direction
- the next calibration step should now preserve this steeper glucose trajectory while trying to recover extracellular lactate fit rather than reopening the already-saturated glucose-only seam

Ran the narrow ELAC recovery seam from the new `eglc_glucose_lactate_shape_probe` seed.

What was tested:
- only `km_LAC`, `km_PYR`, and `vmax_VLDH` were allowed to move
- the steeper glucose-side shape from the new seed was held fixed

What happened:
- the optimizer returned the exact same retained solution as the seeded `eglc_glucose_lactate_shape_probe`
- final loss stayed at about `3.4925`
- `ELAC` remained at about `0.206` nRMSE
- `EGLC` and the other protected metrics also stayed unchanged

Why it matters:
- this local ELAC/lactate seam is already saturated at the current seed
- the next useful move is not to rerun `km_LAC` / `km_PYR` / `vmax_VLDH` again, but to change the hypothesis to a different coupled subsystem

Ran a broader ELAC rebalance seam from the same `eglc_glucose_lactate_shape_probe` seed.

What was tested:
- `vmax_VPK`, `vmax_VLDH`, `km_PEP`, and `km_PYR`
- this was meant to check whether the ELAC tradeoff was really hiding in the `PEP/PYR/LDH/PK` seam rather than the smaller lactate-only seam

What happened:
- the optimizer returned the exact same retained solution as the seeded `eglc_glucose_lactate_shape_probe`
- final loss stayed at about `3.4925`
- `ELAC` stayed at about `0.206` nRMSE
- `EGLC`, `LAC`, `ATP`, and the protected metrics stayed unchanged

Why it matters:
- the local `PEP/PYR/LDH/PK` rebalance pocket is saturated too
- this strengthens the case that the next useful move must shift to a genuinely different coupled subsystem instead of squeezing more downstream glycolysis/lactate micro-seams

Ran the upstream glucose-commitment / hexose-framing seam from the same `eglc_glucose_lactate_shape_probe` seed.

What was tested:
- `vmax_VHK`, `vmax_VPFK`, `km_GLC_HK`, `km_G6P`, and `km_F6P`
- this was intended to test whether the next gain was hiding upstream rather than in the already-saturated ELAC/downstream seams

What happened:
- the optimizer returned the exact same retained solution as the seeded `eglc_glucose_lactate_shape_probe`
- final loss stayed at about `3.4925`
- the retained upstream values stayed the same as the current seed:
  - `vmax_VHK = 0.215124`
  - `vmax_VPFK = 1.663293`
  - `km_GLC_HK = 0.006171`
  - `km_G6P = 0.099049`
  - `km_F6P = 0.331375`

Why it matters:
- the current seed already includes the useful upstream glucose-commitment / hexose-framing adjustment
- this is another saturation signal, so the next useful calibration move should be a genuinely different subsystem rather than another re-expression of the same glucose basin

Ran the phase-2 adenylate / purine seam from the same `eglc_glucose_lactate_shape_probe` seed.

What was tested:
- `vmax_VAK`
- `vmax_VAK2`
- `vmax_VAMPD1`
- `vmax_VIMPH`
- target scope was switched to `core_glycolysis_energy` so the objective could actually reward energetic recovery instead of only extracellular shape

What improved:
- baseline loss improved from about `3.3780` to about `2.8082`
- `glycolysis_energy` improved from about `3.4168` to about `2.8063`
- `nucleotide_purine` improved from about `2.5143` to about `2.4337`
- `endpoint_nrmse` improved from about `0.4607` to about `0.3554`
- `AMP` improved to about `2.825` nRMSE
- `ADP` improved slightly to about `0.891`

What stayed strong:
- `EGLC` remained strong at about `0.043`
- `LAC` remained strong at about `0.067`
- `ELAC` stayed around `0.206`

Tradeoffs:
- `glycolysis` aggregate softened from about `0.7383` to about `0.8775`
- `ATP` softened slightly from about `0.178` to about `0.189`
- `PYR` remained a major miss

Why it matters:
- after the whole nearby glucose basin saturated, the purine/adenylate phase-2 seam was the first genuinely different basin that produced a meaningful fit improvement
- this is now the strongest candidate for the next full pure-ODE validation through `main.py`

Ran a stricter 42-day hybrid follow-up from that phase-2 adenylate seed, then validated it through the full pure ODE.

What improved:
- the long-horizon phase-2 adenylate-retention pass improved the calibration objective from about `2.9001` to about `2.7402`
- `AMP` and `IMP` improved somewhat on the long-horizon calibration report
- `EGLC`, `ELAC`, and `LAC` stayed directionally stable

What did not hold up in the pure ODE:
- `ATP` still collapsed from about `0.933` to about `0.0014`
- `ADP` still collapsed to essentially zero
- `EGLC` remained too shallow over the 42-day ODE horizon
- the attempted PYR/LAC outlet recovery stage reproduced the same retained solution and did not improve the hybrid seed further

Why it matters:
- long-horizon calibration improvement is still not enough on its own; the full `main.py` ODE remains the real promotion gate
- the next calibration hypothesis needs to tackle the energy-collapse mechanism more directly, not just the same PYR/LAC outlet pocket

## 2026-03-26

Drafted a concrete Hermes-assisted calibration V1 architecture for the RBC model.

What improved:
- the earlier brainstorming idea now has a repo-facing spec in `HERMES_CALIBRATION_V1.md`
- Hermes is scoped as a bounded outer-loop orchestrator rather than a simulator or equation mutator
- the design now names concrete subsystem agents, calibration tools, shared state, and a fit-first decision hierarchy

What was decided:
- use subsystem/pathway agents instead of one LLM per enzyme
- keep `src/equadiff_brodbar.py`, `src/MM_calibration.py`, and `src/main.py` deterministic and promotion-gated by the real ODE
- align the Hermes loop with `AUTOSEARCH_ARCHITECTURE.md` so only generated stage plans, manifests, and decision artifacts are mutated

Why it matters:
- this gives the calibration work a realistic path to Hermes empowerment without compromising scientific discipline
- the design captures seam memory, bounded hypothesis selection, and pure-ODE-aware promotion logic in one place
- it provides a concrete V1 implementation target instead of leaving the idea at the metaphor stage

Implemented the first Phase A Hermes calibration surface on top of that V1 plan.

What improved:
- there is now a shared calibration state schema in `services/robocop/calibration_state.py`
- there is now a coordinator prompt contract plus structured response schema in `services/robocop/calibration_prompts.py`
- the Hermes calibration toolset can now:
  - summarize calibration artifacts
  - summarize pure-ODE trajectory groups
  - summarize recent candidate history
  - write a bounded stage-plan JSON for manual review

What was validated:
- focused Python compile checks passed for the new schema/prompt/tool modules
- focused Hermes calibration tool tests passed, including stage-plan writing without execution
- the new stage-plan writer produces a `stage_plan` document that matches the current `MM_calibration.py --stage-plan-file` contract

Why it matters:
- Hermes now has enough scaffolding to act as a real read-mostly calibration critic instead of only a concept note
- the next implementation step can focus on the coordinator loop itself rather than re-deciding schemas and prompt shape

Built the actual coordinator-side Phase A loop.

What improved:
- Hermes can now run a full read-only coordination cycle around calibration artifacts
- the loop reads:
  - calibration artifact summary
  - pure-ODE trajectory summary
  - recent candidate history
- it then:
  - infers saturated seams from recent near-zero-improvement runs
  - assembles subsystem proposals
  - chooses one bounded seam
  - writes a `stage_plan` document for manual review
  - stops before execution

What was validated:
- the new `calibration_coordinate_phase_a` tool passed focused tests
- in the test harness it selected the adenylate seam from an ATP/ADP-collapse scenario and wrote a valid manual-review stage plan

Why it matters:
- Hermes can now help choose the next experiment instead of only summarizing the last one
- the loop is still safe because it never launches `MM_calibration.py` automatically
- the next step can focus on Phase B execution and comparison rather than Phase A decision scaffolding

Built the bounded Phase B execution loop for Hermes-assisted calibration.

What improved:
- Hermes can now take a drafted stage plan and execute it through `src/MM_calibration.py`
- Phase B reruns `src/main.py` on both the seed and the candidate, copies the resulting ODE artifacts into a dedicated comparison folder, and compares them side by side
- the loop now produces a bounded decision record with `promote`, `informative`, or `discard`

What was validated:
- focused unit tests now mock a full Phase B pass end to end
- the test executes a drafted stage plan, simulates seed/candidate `main.py` reruns, writes a decision record, and confirms the promote classification logic
- the calibration Hermes toolset now exposes `calibration_execute_phase_b`

Why it matters:
- Hermes is no longer limited to drafting the next experiment; it can now also evaluate the result in a controlled way
- the pure-ODE rerun remains part of the decision gate, which keeps the orchestration fit-first but still scientifically disciplined
- the next step can move to subsystem-agent arbitration rather than more execution plumbing

Built the Phase C subsystem-agent arbitration layer on top of the current Phase A + Phase B loop.

What improved:
- Hermes can now arbitrate between subsystem proposals instead of only selecting the single top-scoring seam
- the new arbiter can form a small compatible coalition of subsystem agents and write a bounded multi-stage stage plan
- the Phase C tool can optionally hand that stage plan directly into Phase B for seed-vs-candidate execution and classification

What was validated:
- focused tests now cover a compatible phase-2 coalition, selecting `adenylate` plus `purine_salvage`
- the generated stage plan now supports multiple bounded stages when the seams are compatible
- the optional Phase B handoff path was validated with a mocked execution result and decision propagation

Why it matters:
- Hermes can now reason about subsystem cooperation rather than only single-seam retries
- the calibration loop remains bounded and interpretable because Phase C still rejects conflicting or overlapping seams
- the next implementation step can focus on seam-memory reuse across repeated cycles instead of more coordination scaffolding

Built the Phase D seam-memory reuse layer on top of the current Phase A + Phase B + Phase C stack.

What improved:
- Hermes can now run repeated bounded calibration cycles while carrying forward what each seam already taught us
- same-seed `saturated` seams are fed back into the next arbitration pass so the coordinator avoids redundant local retries
- `dangerous` seams can persist across promoted seeds when the pure ODE regressed, which keeps one bad basin from being rediscovered over and over
- the working seed now advances only after a Phase B `promote`, so informative or regressive candidates cannot silently replace the baseline

What was validated:
- the new Phase D session helper writes a seam-memory ledger plus a session summary under `Simulations/brodbar/hermes/phase_d/`
- focused unit tests now cover a two-cycle story where one seam becomes saturated, a different seam is chosen next, and the seed advances only after the promoted candidate
- the Hermes calibration toolset now exposes `calibration_run_phase_d_session`

Why it matters:
- Hermes can now learn across bounded calibration cycles instead of treating each cycle like isolated amnesia
- this is the first point where the orchestration layer starts to accumulate practical calibration experience, not just execute one-off proposals
- the next natural step is to exercise this Phase D loop on real calibration artifacts and inspect whether the seam-memory policy actually reduces wasted retries

Validated and corrected the first real post-update Hermes Phase A / Phase B live smoke test.

What improved:
- Phase A / Phase C now propagate the seed calibration context (`seed`, `t_max`, and `curve_fit_strength`) into the written stage plan
- Phase B now forwards that context back into `src/MM_calibration.py`, so the candidate run no longer falls back to the wrong default calibration horizon or seed
- Phase B fit comparison now uses the candidate run's own `results.tsv` baseline/final pair as the primary apples-to-apples comparison basis

What was validated:
- the same real smoke test was rerun on `hybrid_long_horizon_phase2_only`
- Phase A again selected the `adenylate` seam and wrote the same bounded plan
- after the fix, Phase B reran the candidate under the same calibration context and observed:
  - baseline target loss `2.7402`
  - final target loss `2.7402`
  - identical pure-ODE seed/candidate behavior
- the candidate is now classified `discard`, which matches the scientific reality that this seam simply reproduced the seed

Why it matters:
- Hermes no longer overstates a fake seed-vs-candidate regression caused by a mismatched historical comparison context
- the Phase B gate is now more trustworthy for real live calibration trials
- future live Hermes runs can now be judged on genuine within-run gain plus pure-ODE behavior rather than accidental context drift

## 2026-03-27

Drafted an explicit agent-editable calibration policy for the next autonomy step.

What improved:
- the repo now has a written boundary for allowing agent source edits in `src/MM_calibration.py`
- the policy clearly freezes `src/equadiff_brodbar.py` in the initial rollout
- the editable scope is limited to objective design, target routing, stage planning, ranking, and diagnostics

What was decided:
- the first editable source layer should be the calibration orchestrator, not the ODE core
- every agent patch must be validated through both calibration output and the real `src/main.py` pure ODE
- patch outcomes must still be classified as `promote`, `informative`, or `discard`

Why it matters:
- this creates a safe path toward more autonomous calibration improvement without letting agents rewrite scientific truth
- it turns the earlier brainstorming into an enforceable operating policy rather than an informal idea

Implemented the first enforcement layer for that policy.

What improved:
- `src/MM_calibration.py` now exposes explicit `AGENT_EDITABLE_START/END` markers around the initial writable orchestration zones
- a new validator in `services/robocop/calibration_edit_policy.py` checks before/after patches against those markers
- the Hermes calibration toolset now exposes `calibration_validate_agent_edit`

What was validated:
- edits inside a marked `MM_calibration.py` zone are accepted
- edits outside a marked zone are rejected
- edits to `src/equadiff_brodbar.py` are rejected immediately
- the real `src/MM_calibration.py` file exposes the expected zone set:
  - `target_routing`
  - `stage_planning`
  - `fit_penalty_hierarchy`
  - `objective_builders`
  - `diagnostics_reporting`

Why it matters:
- the repo now has an actual technical gate, not just a policy document
- this is the right first step before letting Hermes or any other bounded agent propose live calibration-source patches

Wired that validator into the future autonomous write path.

What improved:
- the Hermes calibration toolset now exposes `calibration_apply_agent_edit`
- that tool reads the current file, runs the editable-zone validator, and writes only if the patch passes policy
- validation is now enforced on the write path itself instead of existing only as a separate preflight check

What was validated:
- a bounded edit inside a marked `MM_calibration.py` zone writes successfully
- a proposed edit to `equadiff_brodbar.py` is rejected before any write occurs

Why it matters:
- future autonomous calibration editing now has a real choke point that is hard to bypass accidentally
- this is a much safer base for any later Hermes patch-selection loop

Built the first guarded patch-proposal loop on top of that write path.

What improved:
- Hermes can now take a proposed `afterText`, pass it through the edit gate, run `py_compile`, and only then launch scientific validation
- the new loop is implemented in `services/robocop/calibration_phase_e.py`
- the Hermes calibration toolset now exposes `calibration_execute_patch_proposal`

What was validated:
- a bounded patch is kept when the mocked scientific decision is `promote`
- the same kind of bounded patch is automatically reverted when the scientific decision is `discard`
- the loop therefore enforces “revert unless explicitly kept” as the safe default

Why it matters:
- this is the first real bridge between bounded source editing and bounded scientific validation
- it gives Hermes a safe path to try calibration-source changes without leaving every failed scientific experiment behind in the working tree

Ran the first real live Phase E smoke test against `src/MM_calibration.py`.

What was tested:
- a tiny diagnostics-only patch was proposed inside the allowed `diagnostics_reporting` editable zone
- the patch only added a harmless report field so the run would exercise the edit loop, not try to improve science yet
- the loop then executed the full guarded flow:
  - edit-gate validation
  - guarded write
  - `py_compile`
  - Phase B scientific validation
  - automatic keep/revert decision

What was validated:
- the edit gate accepted the patch because it stayed inside a marked editable zone
- the patched `src/MM_calibration.py` compiled successfully
- Phase B executed end to end on the patched file and produced a real decision artifact
- the decision was `discard`, so the loop automatically restored `src/MM_calibration.py` to its original content

Why it matters:
- this proves the bounded patch loop is real, not just test scaffolding
- we now have live evidence that a non-promoted source edit does not get stranded in the working tree
- the next source-edit experiment can focus on a real calibration hypothesis rather than plumbing risk

Ran the first real live scientific Phase E patch inside `fit_penalty_hierarchy`.

What was tested:
- a tiny fit-first patch reduced the adenylate pool trajectory penalty term in `_penalty_loss` from `5.0` to `3.0`
- the patch stayed inside the marked `fit_penalty_hierarchy` editable zone in `src/MM_calibration.py`
- the bounded live experiment then executed:
  - edit-gate validation
  - guarded write
  - `py_compile`
  - Phase B calibration execution on a long-horizon phase-2 adenylate seam
  - seed and candidate `main.py` reruns
  - automatic keep/revert

What was validated:
- the patch passed the edit gate and compiled successfully
- the scientific validation loop completed end to end
- the candidate exactly reproduced the seed under the same calibration context:
  - baseline target loss `2.740209`
  - final candidate target loss `2.740209`
  - `absolute_gain = 0.0`
- the pure ODE readout stayed unchanged on the protected signals, so the decision was `discard`
- the patch was automatically reverted and `src/MM_calibration.py` was restored

Why it matters:
- this is the first proof that a real scientific source patch can go through the full bounded live loop safely
- it also shows that the current long-horizon phase-2 adenylate basin is already saturated enough that a tiny fit-first penalty tweak does not open a better candidate
- the next source-edit hypothesis should move to a different seam or a different bounded ranking/selection idea rather than retrying the same saturated basin

Implemented the new fit-only true-ODE calibration regime in `src/MM_calibration.py`.

What changed:
- `rank_loss` now equals `fit_loss`
- regularization and physiological penalties are still computed and reported, but no longer influence ranking
- candidate acceptance is now fit-only instead of being vetoed by monitor regressions after a real fit improvement
- optimization now uses report-level ODE fidelity for the effective optimization path, even though this is slower
- target weighting was strengthened for the metabolites we most want to rescue:
  - `ATP`
  - `ADP`
  - `EGLC`
  - `PYR`
  - `PEP`
  - `LAC`

What was validated:
- `src/MM_calibration.py` compiles after the refactor
- a real fit-only smoke run completed from the current long-horizon seed into `Simulations/brodbar/calibration/fit_only_trueode_smoke/`
- the chosen adenylate seam was already saturated and therefore stayed at `0.0%` improvement
- the resulting pure-fit report now surfaces the unresolved biology directly as top errors:
  - `AMP`
  - `PYR`
  - `ADP`
  - `PEP`
  - `LAC`
  - `EGLC`

Why it matters:
- we now have a calibration regime that truly matches the stated scientific intent: fit the experiment with the real ODE, even if it is slower
- the next search step can now optimize directly against the problematic metabolites instead of losing signal to penalty-weighted ranking

Ran the first longer fit-only true-ODE combined seam from the current long-horizon seed.

What was tested:
- phase 1 combined glucose / lower-glycolysis / outlet seam:
  - `vmax_VEGLC`
  - `km_EGLC`
  - `km_GLC_transport`
  - `vmax_VPGM`
  - `vmax_VENOPGM`
  - `vmax_VDPGM`
  - `vmax_V23DPGP`
  - `vmax_VPK`
  - `vmax_VLDH`
  - `km_PYR`
  - `km_LAC`
  - `km_PEP`
- phase 2 adenylate / purine seam:
  - `vmax_VAK`
  - `vmax_VAK2`
  - `vmax_VAMPD1`
  - `vmax_VIMPH`
- the run used the new fit-only ranking with report-level true-ODE fidelity and the 42-day horizon

What happened:
- the run completed into `Simulations/brodbar/calibration/fit_only_combined_trueode_longrun/`
- baseline loss was `2.6264`
- final loss was `2.6240`
- total improvement was only `0.1%`
- phase 1 mostly rediscovered the already-known glucose / lower-glycolysis / outlet basin and ended on a fit-only tie
- phase 2 produced the only actual gain, improving `glycolysis_energy`, `nucleotide_purine`, `glycolysis`, and `endpoint_nrmse` slightly

What remains unresolved by pure fit:
- `AMP` is still the worst miss
- `PYR` remains a major miss
- `ADP` is still structurally poor
- `PEP` is still materially off
- `ATP` is still only moderately improved
- `EGLC` is still not meaningfully better than the current long-horizon seed

Why it matters:
- this run shows the new fit-only true-ODE regime is working as intended
- the limiting factor is no longer penalty-dominated ranking
- the limiting factor is now the local basin reached by the current long-horizon seed and combined seam choice

Ran a more direct basin-targeted fit-only follow-up from the first fit-only long-run seed.

What was tested:
- phase 1 narrowed the search to the PYR/PEP/LAC plus glucose-outlet seam:
  - `vmax_VEGLC`
  - `km_EGLC`
  - `km_GLC_transport`
  - `vmax_VPK`
  - `vmax_VLDH`
  - `km_PYR`
  - `km_PEP`
  - `km_LAC`
- phase 2 attacked the adenylate basin more directly:
  - `vmax_VAK2`
  - `vmax_VAK_rev`
  - `vmax_VNDPK`
  - `vmax_VNDPK_rev`
  - `vmax_VAMPD1`
  - `vmax_VIMPH`
- the run stayed on the same fit-only true-ODE regime and the same 42-day horizon

What happened:
- the calibration fit improved dramatically from `2.6240` to `1.5317`
- phase 1 simply reproduced the current phase-1 basin on a fit-only tie
- phase 2 opened a new calibration basin and drove almost all of the gain
- the resulting report looked much better on pure fit:
  - `ADP` improved to about `0.769`
  - `ATP` improved to about `0.256`
  - `PEP` improved to about `0.390`
  - `EGLC` stayed strong at about `0.053`

What the pure ODE said afterward:
- `EGLC` really did improve in the long-horizon ODE, ending about `0.418` mM lower than the previous fit-only seed
- but `ATP` finished even lower
- `ADP` still collapsed to zero
- `PYR` worsened materially
- `PEP` dropped sharply
- `LAC` changed only slightly

Why it matters:
- this proves the basin can be moved strongly in pure fit
- but it also proves that a very large fit-only gain can still be the wrong scientific move for the actual long-horizon ODE
- the next useful hypothesis must explicitly preserve the `EGLC` gain while constraining the energy quartet and the pyruvate axis at the same time

Ran the direct stabilization follow-up from that basin-targeted candidate.

What was tested:
- phase 1 reopened only:
  - `vmax_VPK`
  - `vmax_VLDH`
  - `km_PYR`
  - `km_PEP`
  - `km_LAC`
- phase 2 reopened only:
  - `vmax_VAK2`
  - `vmax_VAK_rev`
  - `km_ADP_ATP`
  - `vmax_VNDPK`
  - `vmax_VNDPK_rev`
  - `vmax_VAMPD1`
  - `vmax_VIMPH`
- the improved glucose-outlet seam was intentionally left untouched so the `EGLC` gain would be preserved if the basin could be stabilized

What happened:
- baseline loss started at `1.5317`
- final loss stayed at `1.5317`
- phase 1 reproduced the same retained `VPK/VLDH/km_PYR/km_PEP/km_LAC` values
- phase 2 reproduced the same retained `VAK2/VAK_rev/VNDPK/VAMPD1/VIMPH` values
- protected metrics stayed identical

Why it matters:
- this stabilization pocket is saturated too
- the result confirms that the issue is no longer “we forgot to search locally around the new basin”
- the next useful calibration move has to open a genuinely different coupled hypothesis, not a tighter version of this same stabilization seam

Raised the calibration edit policy to full-file autonomy on `src/MM_calibration.py`.

What changed:
- the edit validator no longer enforces marker-bounded zones inside `MM_calibration.py`
- the whole file is now considered editable by the Hermes calibration edit layer
- `src/equadiff_brodbar.py` remains explicitly frozen
- the guarded write path, compile gate, and scientific validation loop stay mandatory

Why it matters:
- the autonomy layer can now test higher-leverage changes in calibration flow, not just local objective snippets
- this is the right next escalation because the main bottleneck now appears to be basin and orchestration logic, not only isolated scoring fragments
- the scientific safety boundary still exists because the ODE core remains read-only and promotion still depends on the real ODE validation path

Prepared a repo-grounded migration plan for opening `src/equadiff_brodbar.py` safely.

What was clarified:
- the right next step is not a monolithic rewrite of the Brodbar ODE
- the safer path is to keep the Michaelis-Menten scaffold, freeze state topology and metabolite indexing, and introduce complementary kinetic families as neutral-by-default wrappers on selected fluxes
- the first target subset should be the reactions most directly tied to the failing observables:
  - `VEGLC`
  - `VELAC`
  - `VLDH`
  - `VPK`
  - `VENOPGM`

What the plan now recommends:
- first extract flux computation from `dxdt` assembly with zero mathematical change
- then add hybrid-capable flux interfaces with neutral defaults
- only after that extend `MM_calibration.py` so hybrid parameters can be staged MM-first and hybrid-second

Why it matters:
- this gives us a path to change the global mathematical flux description without losing regression safety
- it also keeps the future hybrid migration auditable through the same pure-ODE path in `main.py`

Ran the first real full-file autonomous patch on `src/MM_calibration.py`.

What was tested:
- the patch modified stage-plan parameter resolution so explicit `include_params` can pull valid global parameter bounds from the full `PHASE_MAP`, even when the requested parameter is absent from the phase-local map
- this was aimed directly at the previously observed blind spot where `km_ADP_ATP` was requested in a phase-2 stabilization seam but never actually entered the optimized parameter set

What happened:
- the full-file patch passed the edit gate and `py_compile`
- the bounded scientific validation loop executed a real phase-2 direct adenylate run plus seed/candidate `main.py` reruns
- the resulting `calibration_report.json` confirmed that the patch worked technically:
  - `km_ADP_ATP` appeared in `resolved_stage_plan.phase_params`
  - `km_ADP_ATP` appeared in `selected_param_names`
  - the phase report recorded an optimized value for `km_ADP_ATP`
- despite that technical success, the candidate exactly reproduced the seeded basin in both fit and pure ODE, so Phase B classified it `discard`
- the patch was therefore automatically reverted

Why it matters:
- this is the first proof that the new full-file autonomy can test a real calibration-flow correction, not just a cosmetic or local objective tweak
- it also shows that the `km_ADP_ATP` routing issue was real and is now understood precisely
- scientifically, the run tells us something useful: even after the resolver is corrected, that direct adenylate seam still does not open a better basin from the current seed

Started the first safe hybrid-kinetics opening in `src/equadiff_brodbar.py`.

What changed:
- added neutral-by-default wrapper families for the first recommended glucose/lactate-side fluxes:
  - `VEGLC`
  - `VELAC`
  - `VLDH`
- each wrapper keeps the current Michaelis-Menten behavior as the identity default
- optional `kinetic_family_*` and `hybrid_blend_*` controls were introduced so the mathematical form can evolve later without immediately changing the baseline ODE

What was validated:
- `src/equadiff_brodbar.py` still compiles
- the official Brodbar execution path through `src/main.py --model brodbar --load-params ...` still completes successfully
- `all_metabolites.csv` is still produced on the real ODE path after the wrapper introduction

Why it matters:
- this is the first concrete step from “Michaelis-Menten only” toward a controlled hybrid kinetics migration
- it opens the glucose/lactate-side fluxes we most care about scientifically while keeping the current model behavior intact by default
- the next safe step can focus on exposing these new family switches to calibration rather than rewriting more of the ODE monolith at once

Exposed the first hybrid glucose/lactate flux families to `src/MM_calibration.py`.

What changed:
- phase 1 now includes a dedicated hybrid parameter block for:
  - `VEGLC`
  - `VELAC`
  - `VLDH`
- added a dedicated `hybrid_glucose_lactate` parameter scope
- added a `hybrid_only` optimization strategy
- hybrid parameters are now part of the calibration taxonomy and identifiability bookkeeping
- hybrid wrappers in `equadiff_brodbar.py` now auto-activate when a calibrated `hybrid_blend_*` moves above zero, even without a text family switch

What was validated:
- `src/MM_calibration.py` and `src/equadiff_brodbar.py` both compile
- a real calibration smoke run completed with:
  - `--param-scope hybrid_glucose_lactate`
  - `--optimization-strategy hybrid_only`
- the run selected and optimized 13 hybrid parameters, then wrote:
  - `Simulations/brodbar/calibration/hybrid_flux_exposure_smoke/calibration_report.json`
  - `Simulations/brodbar/calibration/hybrid_flux_exposure_smoke/best_params.json`

Why it matters:
- hybrid families are no longer only latent ODE hooks; they are now first-class calibration parameters
- we can start testing whether complementary kinetics on glucose/lactate-side fluxes open a better basin than pure MM alone
- the next iteration can focus on a meaningful hybrid search budget instead of more plumbing work

Ran the first real hybrid calibration budget on the glucose/lactate seam.

What was tested:
- seed: `fit_only_basin_targeted_longrun`
- target scope: `glycolysis_extracellular`
- param scope: `hybrid_glucose_lactate`
- optimization strategy: `hybrid_only`
- 8 Optuna trials on the 42-day horizon

What happened:
- the hybrid run improved total loss from `1.6164` to `1.5628` (`+3.3%`)
- the best accepted candidate moved several hybrid parameters away from their neutral defaults, especially:
  - `hybrid_blend_VELAC`
  - `hybrid_backpressure_hill_VELAC`
  - `hybrid_km_ELAC`
  - `hybrid_import_hill_VEGLC`
  - `hybrid_reverse_scale_VEGLC`
  - `hybrid_forward_hill_VLDH`
  - `hybrid_reverse_hill_VLDH`
- `ATP`, `ADP`, `PEP`, `LAC`, and `ELAC` improved in the calibration report, while `PYR` and `AMP` remained the dominant misses

What was validated:
- the calibration run completed successfully and wrote:
  - `Simulations/brodbar/calibration/hybrid_flux_glucose_lactate_longrun/calibration_report.json`
  - `Simulations/brodbar/calibration/hybrid_flux_glucose_lactate_longrun/best_params.json`
- the official `src/main.py --model brodbar --load-params ...` Brodbar ODE path also completed successfully with the new hybrid-loaded parameter file

Why it matters:
- this is the first evidence that a neutral hybrid extension on glucose/lactate-side fluxes can open a new calibration basin
- the gain is not huge yet, but it is real and it comes from the new hybrid degrees of freedom rather than another MM-only reparameterization
- the next useful question is no longer “are the hybrid hooks connected?” but “do the true ODE trajectories improve on `ATP/ADP`, `EGLC`, and `PYR/PEP/LAC` enough to justify widening the hybrid search”

Ran the first mixed `vmax/km -> hybrid_only` follow-up from the accepted hybrid glucose/lactate seed.

What was tested:
- stage 1 reopened a narrow MM seam on:
  - `vmax_VEGLC`
  - `km_EGLC`
  - `km_GLC_transport`
  - `vmax_VELAC`
  - `vmax_VLDH`
  - `vmax_VPK`
  - `km_PYR`
  - `km_PEP`
  - `km_LAC`
- stage 2 then reopened the full `hybrid_glucose_lactate` seam under `parameter_classes = ['hybrid']`
- both stages used the same fit-only true-ODE objective and 42-day horizon as the accepted hybrid seed

What happened:
- baseline loss started at `1.5628`
- final loss stayed at `1.5628`
- stage 1 reproduced the current MM glucose/lactate anchor exactly on a fit-only tie
- stage 2 reproduced the current hybrid candidate exactly on a fit-only tie
- the per-metabolite ranking and protected metrics stayed unchanged

Why it matters:
- the accepted hybrid glucose/lactate seed is now clearly a locally stable basin under both its MM anchor seam and its hybrid seam
- repeating `vmax/km -> hybrid_only` from this same seed is unlikely to yield more progress
- the next useful search should change subsystem or broaden the hybrid family set rather than replay this same two-stage opening

Opened the next downstream hybrid family group on `VPK` and `VENOPGM`.

What changed:
- `src/equadiff_brodbar.py` now includes neutral-by-default hybrid wrappers for:
  - `VPK`
  - `VENOPGM`
- `src/MM_calibration.py` now exposes the corresponding hybrid parameters through a dedicated phase-1 scope:
  - `hybrid_downstream_pk_eno`
- the existing transport-side scope remains intact, and a combined scope also exists for future wider runs:
  - `hybrid_glucose_lactate_plus_downstream`

What was validated:
- `src/equadiff_brodbar.py` and `src/MM_calibration.py` compile
- a real one-trial smoke calibration completed successfully into:
  - `Simulations/brodbar/calibration/hybrid_downstream_exposure_smoke/`
- the smoke run selected and optimized the 9 new downstream hybrid parameters
- the official `src/main.py --model brodbar --load-params ...` Brodbar ODE path also completed successfully with the smoke candidate parameter file, which now contains 122 calibrated parameters

Why it matters:
- the downstream hybrid seam is now real, calibrable, and regression-checked on the official ODE path
- the next step can now spend real search budget on `VPK`/`VENOPGM` hybridization instead of more plumbing

Ran the first real budget on `hybrid_downstream_pk_eno`.

What was tested:
- seed: `Simulations/brodbar/calibration/hybrid_flux_glucose_lactate_longrun/best_params.json`
- target scope: `glycolysis_extracellular`
- param scope: `hybrid_downstream_pk_eno`
- optimization strategy: `hybrid_only`
- 8 Optuna trials on the 42-day horizon

What happened:
- total loss improved from `1.5628` to `1.5535` (`+0.6%`)
- the accepted candidate moved several downstream hybrid parameters off their neutral defaults:
  - `hybrid_blend_VPK`
  - `hybrid_pep_hill_VPK`
  - `hybrid_adp_hill_VPK`
  - `hybrid_atp_backpressure_scale_VPK`
  - `hybrid_pyr_backpressure_scale_VPK`
  - `hybrid_blend_VENOPGM`
  - `hybrid_substrate_hill_VENOPGM`
  - `hybrid_backpressure_hill_VENOPGM`
  - `hybrid_backpressure_scale_VENOPGM`
- the biggest report-side improvements were small but real on:
  - `PEP`
  - `B23PG`
  - `glycolysis`

What the pure ODE said afterward:
- official `src/main.py --model brodbar` reruns completed for both the seed and the new downstream-hybrid candidate
- final-state changes were very small:
  - `EGLC` improved slightly
  - `ELAC` improved slightly
  - `LAC` improved slightly
  - `PYR` improved slightly
  - `PEP` fell slightly
  - `ATP` fell slightly
  - `ADP` remained collapsed at zero
- in practice this means the downstream hybrid seam is live and not saturated, but it is only nudging the true ODE so far rather than opening a big new basin

Why it matters:
- this is the first evidence that hybridizing `VPK`/`VENOPGM` can move the model without breaking the official Brodbar ODE path
- however, the true ODE gains are still too small to claim a biological rescue on `ATP/ADP` or the pyruvate axis
- the next useful step should likely combine the successful transport-side hybrid basin with this new downstream hybrid seam in one wider hybrid search
