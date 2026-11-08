# Executed distinct-phase-volume transport branch

Date: 2026-10-06. User explicitly rejects applying uFBA normalization and authorizes selecting working keys and normalization, borrowing measured Yurkovich hematocrit geometry and executing reversible transport diagnostics before fitting.

## Selected normalization

- Intracellular states: mmol per litre packed cells.
- Extracellular states: mmol per litre supernatant, not total bag volume.
- Geometry: Vi/Vb=H and Ve/Vb=1-H; no single-cell volume or guessed water fraction.
- No numerical concentration rescaling, original workbook overwrite, uFBA preprocessing, time-origin transfer or new measured initialization.
- H*Ci and (1-H)*Ce are derived quantity ledgers per unit bag volume only, not bag-normalized training observations. Computing conserved amounts is not adopting uFBA.
- This is an explicit user-selected working coordinate interpretation. The exact source extraction/normalization formula remains unverified; choosing an interpretation does not supply missing assay provenance or make total extractable material a measured free catalytic pool.

The final branch is `src/rbc_distinct_volume_transport.py`, controlled by `config/fla_distinct_volume_transport.json`. Historical forwarding is unchanged and bit-identical with either legacy or reaction-consistent positivity. The new modes require explicit constant hematocrit and clamped-pH diagnostic semantics. Neither the platform/API nor archived calibration defaults are migrated.

## Selected keys and pairing uncertainty

Stable source trajectory keys are `JBC2017::{sheet}::T{temperature}::B{block}` and sample keys append exact source time. There are372 source samples and36 trajectories. These identify observed worksheet trajectories, not confirmed biological donors.

Ordinal candidate-unit keys `JBC2017::P01/P02/P03` are explicitly hypotheses. The primary working cross-sheet pairing is endo block1->assay block1,2->2,3->3. Its status is not source-verified. All six permutations are retained rather than selecting a mapping by the most favorable ATP or model fit. Complete baseline vectors do not establish a universal cross-sheet/cross-temperature donor key; exact exo baseline reuse across temperatures is not sufficient identification evidence.

The4 C pilot has144 paired records:24 sampling records under each of six pairings. Their576 glucose/lactate concentration representations correspond to96 distinct source values, not576 independent observations. Each record carries both source trajectory keys, original cell locators, matched assay Hct locator, phase concentration, amount ledger and pairing status. Original numeric values and reported times are unchanged. Source day0 is stored separately from its documented storage day1. Files: `output/distinct_phase_transport_2026_10_06/source_preparation/`.

No actual donor ID is invented. Until source linkage is confirmed, all anonymous JBC units share the conservative validation split key `JBC2017_unknown_linkage_all_units`. Temperature/solution can define condition-level matched groups, but rows, days or tentative P01 labels cannot be split into supposedly independent donor training/test sets. Clinical donor covariates are not inferred from row order. This preparation remains conditional diagnostic data, not silently admitted biological training data.

## Geometry and complete reaction accounting

For a positive cell-normalized export j, dCi/dt=-j and dCe/dt=H/(1-H)*j at constant geometry. For glucose import the signs reverse. In the full historical113-pool registry, let D be the diagonal matrix of phase-volume fractions and Vr the diagonal matrix of the declared rate-reference fractions. The concentration matrix is A=D^-1*S*Vr; thus D*A=S*Vr. Quantity changes are computed from executed rates, not raw rates or independently clipped derivatives.

All27 external pools use the explicit registry; E4P remains intracellular. All native intracellular and membrane rates are conditionally interpreted per cell litre/day. VEGSH_deg and VEGSSG_deg remain per supernatant litre/day, preserving their physical first-order derivatives rather than multiplying them by H/(1-H). VECYT is cell-normalized membrane transport from the explicitly buffered CYT pool, not fluid degradation. The remaining CYT chemostat is an acknowledged open amount boundary, not a claimed closed biochemical network. Existing historical biochemical omissions are not repaired by volume scaling.

Applying this geometry to historical kinetic inputs is a diagnostic unit hypothesis: their effective source calibration is not thereby verified. It is kept separate from the existing opt-in C4/folate/redox adapter. This pass does not claim an already validated combination of every structural correction.

## Fixed reversible GLUT/MCT hypothesis

Glucose import uses kG*(Ge-Gi)/(1+Ge/Ke+Gi/Ki), with equal-activity equilibrium under the declared accessible-concentration approximation. The capacities obey Vf/Ke=Vr/Ki=kG. Native seed Km_i=3.4913742400037897 and Km_e=23.50088375077599 remain fixed; kG=seedVmaxVEGLC/Km_e=0.08796558869207803 day^-1. This replaces the old gate family in the named reversible hypothesis only, not by fitting or reusing a teacher curve.

Lactate export uses kL*(Li*10^(pHref-pHi)-Le*10^(pHref-pHe))/(1+Li/Ki+Le/Ke). The driving term has proton/lactate equilibrium Li/Le=10^(pHi-pHe), permits both signs and vanishes at equal activities. Native Km_LAC=2.704214706510881 is retained on both faces under an explicit symmetry hypothesis; kL=seedVmaxVELAC/Km_LAC=0.637848035897014 day^-1. This is a reduced diagnostic law, not the complete proton-first ordered carrier or a measured storage-temperature mechanism. The other GEM lactate routes are not activated, so VELAC remains an effective single-route hypothesis, not an identified MCT1-specific experimental flux. No new Km, kcat, active-fraction prior or independent carrier capacity is derived from proteomics.

The reduced laws conditionally treat their phase-state coordinates as comparable accessible concentrations. A packed-cell total is not automatically a free intracellular-water activity; the cell-water fraction remains unset rather than measured as1. Consequently, these mathematical equilibrium tests validate the declared reduced coordinates, not physiological free-pool/activity equality in actual stored cells. An independently supported accessible-pool/water/partition observation mapping must precede calling either law thermodynamically validated for the experimental assays.

All comparison cases clamp pHi to its exact initial value and set the new carrier's pHe=7.2 as an explicit diagnostic control, not a Yurkovich measurement at4 C. For the MCT hypothesis, executed proton export per litre bag/day is H*executedVELAC. Maintaining fixed pH implies compensating buffer-reservoir exchange. The proton ledger is saved, but neither the pH nor acid/base, Hb/CO2, oxygen or ATP-dependent ion regulation is predicted. A free pH replay requires a separate buffer/acid-base contract and measurements at the proper temperature. No ATP stoichiometry is added to GLUT/MCT.

## Executed design and interpretation

Run an uninterrupted free J1-J4 concentration ODE, without observation forcing, resets, fitting or selecting a best case. Preserve the exact frozen114-coordinate initial state and all historical kinetic inputs. The two conductances are deterministically tied to the frozen seed, not optimized. The reaction-consistent availability threshold remains0.001 mM; BDF strict1e-7/1e-9 and ultrastrict1e-8/1e-10 are compared separately from predictive errors.

The three geometry scenarios are original4 C assay Hct at source day0: assay!D3=0.580, assay!D11=0.574 and assay!D19=0.632. They imply Vi/Ve=1.380952,1.347418 and1.717391. These are borrowed geometry scenarios, not matched Bordbar donor metadata or a pooled imputed Hct estimate. Hct is held constant in each replay; later sampling/lysis/swelling-driven volume changes are not inferred or suppressed into a teacher.

Seven cases, each under two tolerances, comprise a common-coordinate native-transport clamped control and native/reversible transport at each of the three Hct values. Concentration budgets, native/executed rate integrals, proton export, dense/accepted minima and strict/ultrastrict agreement are recorded for all113 pools and100 reactions. The common-coordinate clamped control is not the preceding free-pH historical run; exact historical forwarding is tested separately. Results and numerical conclusions are recorded in `fixed_context_v2/summary.json`, with the final endpoint report alongside it.

Full QA:1076 passed, two source-dependent skips and six existing Optuna warnings. The Python3.14/Pydantic startup warning is unchanged. Thirty new tests cover historical forwarding, asymmetric reversible equilibria, pH driving/sign, full matrix quantity weighting, external-only rate bases, zero-boundary availability, absent inputs, sample keys and all pairing alternatives. Existing common-source and transport-audit archives still verify without changed inputs.

The preliminary `fixed_context/` branch was explicitly interrupted after reviewing the VECYT rate basis; its outputs remain preserved and are excluded from conclusions. The corrected final branch is `fixed_context_v2/`. The bundled Python supports workbook extraction but lacks pytest/scipy; the installed project Python executes tests and scientific replays. No dependencies or certificate policies were modified.

## Next priorities

Final numerical results: all14 replays pass13146/13146 quadrature and240191/240191 cross-tolerance comparisons. Minimum checked concentration is0 mM. Ultrastrict ATP J4 is0.0007510432991 mM for the clamped common-coordinate control,0.0007558684489-0.0007613387033 with native transports at distinct volumes, and0.0007016819763-0.0007033733348 with reversible carriers. None restores the nominal Sheet1 J4 ATP1.079765. Other source uncertainties and the pH clamp prevent interpreting these cases as independent physiological calibration.

The reversible equal-pH law gives negative integrated VELAC: net lactate import. Native-volume cases increase nominal ELAC J4 to5.4883-6.0029 mM versus the common-coordinate5.0051; reversible equal-pH cases yield2.6974-2.8156, versus nominal Sheet1 ELAC6.9959375. This is a conditional direction/gradient result, not a fitted kinetic winner or a rejection of biological MCT. The generated directionality screen records144 conditional inequalities: positive reduced-MCT export requires pHi-pHe<log10(LAC/ELAC). Yurkovich source-day0 bounds span-0.732948 to-0.253806 across all pairings; no one is selected or interpreted as measured pH. Free activity/pool and assay normalization uncertainty can affect their physical meaning. This makes a supported pH/accessible-pool contract the next priority.

The complete endpoint/integral table, inspected six-panel figure and explanation are `fixed_endpoints.csv`, `fixed_trajectories.png`, `conditional_mct_directionality_bounds.csv` and `fixed_results.md` in the new archive. The figure uses nominal unchanged Sheet1 points with their unverified basis clearly labeled; it is not a Yurkovich prediction. Verification reopens original source cells and reproduces all144 conditional log-ratio inequalities.

First use the completed fixed-volume/reversible sensitivity results to determine whether transport geometry changes the energy partition appreciably, without selecting favorable Hct or anonymous pairings. Then implement a supported free acid/base observation/mechanism contract and test its interaction with reversible MCT, reconcile active redox pools and source normalization, and obtain donor linkage before donor-level validation. Future biological fitting requires an identifiable restricted parameter block and uninterrupted whole-network safeguards; numerical convergence alone is not calibration success. The measured Hct and phase ledger do not justify latent NAD(H) concentrations, an artificial ATP source or a readiness override.

## Reproduction

```powershell
python scripts/prepare_yurkovich_phase_keys.py --out output/distinct_phase_source_new
python scripts/run_distinct_volume_transport.py --data output/distinct_phase_source_new --out output/distinct_phase_replay_new
python scripts/verify_distinct_volume_transport.py output/distinct_phase_transport_2026_10_06
python -m pytest qa -q
```

Verifier reopens numeric workbook cells, reconstructs paired ledgers, checks saved113-pool budgets and quadrature/convergence, and reevaluates seven stored states per replay using the executable adapter. Its live RHS checks use the same kernel and are not an independent implementation of all biological kinetics. Native quadrature integrands are not separately reconstructed where only their integrals are stored.
