# Hybrid Kinetics Migration Plan

## Objective

Improve calibration fit quality by evolving the Brodbar ODE from a pure Michaelis-Menten implementation toward a hybrid flux description, while preserving:

- the current metabolite/state topology
- the current Brodbar state indexing
- the current ODE integration and reporting workflow
- backward compatibility with the existing pure Michaelis-Menten baseline

The key idea is:

- keep Michaelis-Menten as the base kinetic scaffold
- allow selected reactions to gain complementary kinetic terms
- calibrate those complementary terms gradually instead of rewriting the whole model at once

## Why This Needs a Structural Plan

Today the calibration and ODE layers are tightly coupled:

- [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py) owns parameter ranges, objective construction, stage planning, and solver calls
- [equadiff_brodbar.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py) owns:
  - the metabolite map
  - parameter loading
  - flux formulas
  - `dxdt` assembly
- [main.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py) runs the exact Brodbar ODE and exports the pure trajectory artifact at [all_metabolites.csv](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/Simulations/brodbar/metabolites/all_metabolites.csv)

Right now the main scientific bottleneck is not just parameter tuning. It is that the same kinetic family is being stretched to fit behaviors that may need:

- reversible transport asymmetry
- allosteric gating
- product inhibition
- redox-driven directionality
- coupled energy-state modulation

## Current Anchors in the Codebase

These are the seams we should treat as anchors during the migration:

- Parameter registry and phase grouping in [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
  - `PHASE_MAP`
  - `get_phase_params_filtered(...)`
- Solver path in [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
  - current `solve_ivp(...)` call into the Brodbar ODE
- State identity in [equadiff_brodbar.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
  - `BRODBAR_METABOLITE_MAP`
- Flux definitions in [equadiff_brodbar.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
  - glycolysis and outlet fluxes around `VHK`, `VENOPGM`, `VPK`, `VLDH`
- Extracellular state updates in [equadiff_brodbar.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
  - `dxdt[85] = -VEGLC`
  - `dxdt[87] = VELAC`
- Pure ODE export in [main.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py)
  - `all_metabolites.csv`

## Non-Negotiable Guardrails

### Must stay frozen first

During the first migration waves, do not change:

- metabolite indexing
- dimensionality of the state vector
- `BRODBAR_METABOLITE_MAP`
- `dxdt` topology and sign conventions unless explicitly justified and isolated

### Must remain possible at every step

At every intermediate step, we must still be able to:

- run [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
- run [main.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py)
- export [all_metabolites.csv](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/Simulations/brodbar/metabolites/all_metabolites.csv)
- compare seed vs candidate on:
  - `ATP`
  - `ADP`
  - `EGLC`
  - `ELAC`
  - `PYR`
  - `PEP`
  - `LAC`

### Backward compatibility rule

Every hybrid kinetic addition must have a neutral setting that exactly reproduces the current MM behavior.

Examples:

- multiplicative modifier defaulting to `1.0`
- blending coefficient defaulting to `1.0` on the MM branch
- inhibition constant defaulting to “effectively off”

## Recommended Hybrid Kinetic Strategy

Do not replace Michaelis-Menten globally.

Use this pattern instead:

`V_hybrid = V_MM * M_complementary(...)`

Where:

- `V_MM` is the current Michaelis-Menten core
- `M_complementary(...)` is a bounded modifier that defaults to `1`

This is safer than full replacement because it preserves:

- current flux scaling intuition
- current `vmax/km` interpretation
- easier backward compatibility
- easier calibration staging

## Complementary Kinetic Families to Add

### 1. Product inhibition overlays

Best for:

- `VENOPGM`
- possibly `VPK`

Form:

- MM core multiplied by a product inhibition term

Use when:

- `PEP` or `PYR` overshoot suggests that downstream accumulation should damp upstream flux

### 2. Hill / allosteric gating overlays

Best for:

- `VHK`
- `VPFK`
- `VPK`

Form:

- MM core multiplied by a Hill activation or inhibition factor

Use when:

- ATP/ADP sensitivity is too weak
- feedforward or ultrasensitive transitions are missing

### 3. Reversible convenience kinetics

Best for:

- `VLDH`
- `VEGLC`
- `VELAC`
- possibly `VAK`, `VNDPK`

Form:

- a reversible saturable flux that includes forward and backward driving terms

Use when:

- current unidirectional or weakly asymmetric MM terms cannot capture observed late-horizon behavior

### 4. State-coupled modulation

Best for:

- `VAK`
- `VNDPK`
- `VPK`
- `VLDH`

Form:

- MM or reversible core multiplied by a bounded function of:
  - energy charge
  - redox ratio
  - pH

Use when:

- the calibration needs fluxes to react more strongly to system-wide state rather than only local substrate concentration

## Reactions to Prioritize First

Do not open the whole network at once.

Start with the reactions most tightly linked to the currently failing observables:

### Tier 1

- `VEGLC`
- `VELAC`
- `VLDH`
- `VPK`
- `VENOPGM`

Why:

- these directly touch `EGLC`, `ELAC`, `PYR`, `PEP`, `LAC`

### Tier 2

- `VHK`
- `VPFK`
- `VAK`
- `VAK2`
- `VNDPK`
- `VNDPK_rev`

Why:

- these are the next logical levers for `ATP/ADP` collapse and upstream glucose commitment

### Tier 3

- PPP and redox reactions
- broader nucleotide salvage

Why:

- important later, but too wide for the first hybrid migration wave

## Safe Refactor Plan

### Phase 0. Freeze the current truth

Before opening hybrid kinetics:

- lock a baseline seed and artifact bundle
- keep a reference run for:
  - current best calibration report
  - current pure ODE `all_metabolites.csv`
  - current flux PDF / metabolite PDF

This is the rollback truth.

### Phase 1. Structural refactor with zero mathematical change

Goal:

- separate flux construction from `dxdt` assembly without changing the equations

Actions:

- extract a `compute_brodbar_fluxes(...)` layer from [equadiff_brodbar.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- keep `dxdt` assembly exactly the same
- keep all current formulas and defaults exactly the same

Deliverable:

- `equadiff_brodbar.py` becomes:
  - parameter unpacking
  - flux computation call
  - `dxdt` assembly

Success condition:

- pure ODE outputs are numerically unchanged within a tight tolerance

### Phase 2. Introduce kinetic family switches with neutral defaults

Goal:

- make selected fluxes configurable without changing default behavior

Actions:

- introduce a per-flux kinetic family registry
- each selected flux gets:
  - family name
  - complementary parameters
  - neutral defaults

Example:

- `VLDH`
  - family: `mm_reversible_convenience`
  - defaults chosen so it reduces to current behavior

Deliverable:

- hybrid-ready flux kernels, still defaulting to current MM behavior

Success condition:

- with neutral defaults, the model reproduces the old trajectories

### Phase 3. Open calibration support for hybrid parameters

Goal:

- let [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py) calibrate the new hybrid terms in a controlled way

Actions:

- add new parameter classes:
  - `hybrid_gate`
  - `reversible_drive`
  - `allosteric_shape`
- keep them separate from classic `vmax/km`
- extend `PHASE_MAP` and stage-plan routing to support hybrid families
- calibrate base MM parameters first, hybrid parameters second

Success condition:

- hybrid parameters enter stage plans explicitly and are auditable in reports

### Phase 4. Open only one hybrid subsystem at a time

Goal:

- avoid a global identifiability explosion

Recommended order:

1. extracellular transport + lactate outlet
2. lower glycolysis outlet
3. adenylate coupling

Success condition:

- each subsystem can be validated independently against pure ODE behavior

### Phase 5. Only then consider broader hybrid combinations

Goal:

- compose subsystems only after single-subsystem wins are proven

Success condition:

- a coalition outperforms the seed in both calibration fit and pure ODE validation

## What Must Change in MM_calibration.py

If we want hybrid kinetics to work, [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py) cannot stay only a `vmax/km` optimizer.

It needs to grow in these directions:

### 1. Parameter family awareness

It should distinguish:

- base MM structure parameters
- hybrid modulation parameters
- subsystem-specific hybrid switches

### 2. Stage sequencing

Recommended order:

- stage A: stabilize core MM
- stage B: open one complementary kinetic family
- stage C: refine combined local basin

### 3. Report transparency

Calibration reports should explicitly show:

- which kinetic family each tested reaction used
- which hybrid parameters were active
- which parameters remained at neutral defaults

### 4. Basin-aware ranking

We should keep fit-first ranking, but add explicit reporting for:

- “fit improved but pure ODE worsened”
- “hybrid parameters moved but observables stayed unchanged”
- “hybrid family opened a new basin”

## What Must Change in equadiff_brodbar.py

Not all at once.

### First

- separate flux formulas from `dxdt` assembly

### Then

- wrap selected fluxes in a hybrid-capable interface

### Only later

- allow true family changes on selected reactions

The safest architecture is:

- `compute_flux_<reaction>(state, params, kinetic_family, hybrid_terms)`
- `compute_brodbar_fluxes(...)`
- assemble `dxdt` from the flux dictionary

This keeps the state map and stoichiometric topology stable while letting the flux law evolve.

## Validation Matrix

Every migration step should pass all of these:

### Regression

- neutral hybrid defaults reproduce the old model within tolerance

### Numerical stability

- no solver blow-up
- no NaN trajectories
- no catastrophic stiffness increase without explanation

### Biological targets

- `ATP/ADP` should improve or at minimum not collapse harder
- `EGLC` should steepen or stay improved
- `PYR/PEP/LAC` should become more coherent, not just redistributed

### Interpretability

- each new hybrid parameter must have a biological meaning
- avoid free-form correction factors with no mechanistic story

## First Concrete Experimental Program

If we start tomorrow, the safest first hybrid campaign is:

### Wave 1: transport + outlet

Open only:

- `VEGLC`
- `VELAC`
- `VLDH`

Candidate hybrid forms:

- reversible transport for `VEGLC` / `VELAC`
- reversible convenience kinetics for `VLDH`

Target observables:

- `EGLC`
- `ELAC`
- `PYR`
- `LAC`

### Wave 2: lower glycolysis outlet

Open only:

- `VENOPGM`
- `VPK`

Candidate hybrid forms:

- product inhibition overlay
- Hill/allosteric modulation

Target observables:

- `PEP`
- `PYR`
- `ATP`

### Wave 3: adenylate coupling

Open only:

- `VAK`
- `VAK2`
- `VNDPK`

Candidate hybrid forms:

- reversible / energy-charge-coupled kinetics

Target observables:

- `ATP`
- `ADP`
- `AMP`
- `IMP`

## Promotion Rule

Do not promote a hybrid kinetic change just because:

- calibration fit improves
- one metabolite improves dramatically
- the hybrid parameters move a lot

Promote only if:

1. calibration fit improves
2. pure ODE improves on the protected metabolites
3. the improvement survives rerun
4. the hybrid terms still have a clear mechanistic interpretation

## Recommendation

The best next move is not to rewrite [equadiff_brodbar.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py) directly in-place.

The best next move is:

1. do a zero-math refactor that extracts flux computation from `dxdt`
2. introduce neutral hybrid-capable flux wrappers for a tiny Tier-1 subset
3. extend [MM_calibration.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py) so it can stage MM-first, hybrid-second calibration
4. validate every step through the pure ODE path in [main.py](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py)

That gives us the best chance of opening a truly better parameter basin without breaking the model’s scientific backbone.
