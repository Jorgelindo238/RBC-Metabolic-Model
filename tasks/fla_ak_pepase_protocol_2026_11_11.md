# AK ratio x PEP phosphatase capacity diagnostic at the working center: protocol

Registered on 2026-11-11 before any integration of its arms. This file is
hash-frozen into the archive at launch; status and outcome are reported
only in `tasks/fla_ak_pepase_results_2026_11_11.md` and at the top of
`fla_progress_log.md`. Config: `config/fla_ak_pepase_2026_11_11.json`.
Fresh archive: `output/ak_pepase_2026_11_11/`.

Follow-up to `tasks/fla_ak_arm_attribution_results_2026_11_11.md` and
`tasks/fla_pep_pase_b13pg_review_2026_11_11.md` (option 1 of its next-step
list). Preparation authorized by the user on 2026-11-11 ("Oui, prépare");
launch needs a separate authorization.

## Single hypothesis

At the retained working center, once the adenylate kinase ratio is balanced
so that ADP stays available, the capacity of the ADP-independent PEP
phosphatase (VPEP_PASE, PEP -> PYR without ATP) is what keeps pyruvate
kinase from converting PEP into ATP: lowering it to the bottom of its
registered box raises the PK share of PEP outflow and the late ATP and ADP
levels beyond the balanced-AK arm alone.

Fixed kinetics, Vmax only, inside the registered boxes. Not a calibration,
not a correction of measured data, not a biological claim.

## What is known before launch

From sealed evidence, the coded laws and the two documents above; no arm
integrated:

- VPEP_PASE has no RBC-GEM counterpart. Working center 7.6598, frozen base
  8.3562, registered PEPase box [0.1, 3.0] on base; PK at the center 0.6566.
  Both laws share km_PEP 1.0375 and are first order in PEP at observed
  levels (0.22 mM at J1, 0.05 at J15).
- Sealed control, PEP outflow through VPEP_PASE: 75%, 95%, 100% on J1-J4,
  J4-J8, J8-J15. Sealed balanced-AK arm (`balanced_forward_lowered`, Vf/Vr
  0.667): 64%, 73%, 84%, with PK not ADP-gated before J8; gap 7.5002, ATP
  J15 4.4e-3 mM, ADP J15 1.7e-4 mM, 23 failed guards including point PEP at
  J4, J8, J15 and MSE PEP.
- Modelled PEP is already below the observation in both sealed
  trajectories at J4 (0.113 and 0.092 against 0.158). Lowering the
  phosphatase is expected to raise PEP; whether that helps or breaks the
  PEP guards is not assumed.
- In the balanced-AK arm sustained ATP production after day 2 is bounded by
  B13PG supply (GAPDH 0.22 mM/day until J8). A higher PK share cannot add
  more than the PEP flux: ENOPGM throughput is 1.18, 0.94 and 0.49 mM/day
  on the three windows, most of it fed by the 2,3-BPG return.
- Three earlier downward trials of this capacity (x0.1 probe, 0.772,
  coupled with PK) were not promoted and were limited by PEP guards; none
  had ADP available after J4.

## Arms

Only vmax_VAK, vmax_VAK_rev and vmax_VPEP_PASE differ from the working
center. Values are derived by rule at launch; the launch is refused if the
sealed AK arm is not exactly the working center with its forward AK
capacity at the registered balancing ratio (0.6669045865, 1e-9 relative),
or if a phosphatase factor leaves its unchanged box.

| Arm | Role | vmax_VAK | vmax_VAK_rev | vmax_VPEP_PASE | PEPase factor on base |
| --- | --- | --- | --- | --- | --- |
| control (sealed, not reintegrated) | control | 2.135939 | 0.198395 | 7.659774 | 0.9167 |
| ak_only = `balanced_forward_lowered` of `output/ak_ratio_2026_11_11/` (sealed, not reintegrated) | reference | 0.132310 | 0.198395 | 7.659774 | 0.9167 |
| pepase_floor_only | single factor | 2.135939 | 0.198395 | 0.835624 | 0.1000 |
| ak_balanced_pepase_floor | hypothesis | 0.132310 | 0.198395 | 0.835624 | 0.1000 |
| ak_balanced_pepase_intermediate | monotonicity | 0.132310 | 0.198395 | 2.529959 | 0.3028 |

With the two sealed trajectories this is a 2 x 2 factorial plus one
intermediate point (geometric mean of the center and the floor, a numerical
probe without physiological meaning). Six J1-J15 integrations: three arms,
strict and ultrastrict. At the floor the phosphatase capacity is 0.109
times its center value and still 1.27 times the PK capacity.

## Search design

The registered grouped design is retained. No search is run and AK is not
ungrouped in any search: each arm is a literal parameter vector replayed at
fixed kinetics with all 14 log factors at zero, as in the AK diagnostic;
the launch checks that the replay routine reproduces each vector exactly.

## Frozen contract

Unchanged and hash-verified against `output/vmax_requalification_2026_11_09/`
and `output/ak_ratio_2026_11_11/`: all 55 Sheet1 J1 values including the
duplicated B13PG row, every latent state, every working-center Vmax other
than the three registered capacities (PK included), every Km, network,
hematocrit 0.58, clamped pH, availability threshold 1e-3 mM, rejection
tolerance -1e-10 mM, guard reference and reserve. Recipe: SciPy 1.17.1,
Radau, bounded fine Jacobian, strict (1e-8/1e-12) and ultrastrict
(1e-9/1e-13), max_step 0.05 day, compiled backend.

No retry, clipping, bound change, optimization, follow-up calibration, J46
run, promotion or default change.

## Outputs per arm and profile

- ATP, ADP, AMP, IMP, ADESUC, GTP, GDP, R5P, PRPP, B23PG, PEP, PYR, G6P,
  F6P at J1, J4, J8, J11, J15.
- All original dated guards with reserve and the absolute J15 gap.
- Executed integrals on J1-J4, J4-J8, J8-J15 for AK, AK2, AMPD1, ADSS,
  ADSL, NDPK, PRPPASe, RKa, HK, PFK, GAPDH, PGK, DPGM, 23DPGP, ENOPGM, PK,
  VPEP_PASE, HGPRT1; gross ATP production and consumption.
- Phosphoryl stocks E_A = 2 ATP + ADP and E_G = GDP + 2 GTP.
- The same tables recomputed for the two sealed trajectories.
- Daily executed balances, quadrature convergence, native/compiled rate
  checkpoints, strict/ultrastrict paired comparison.

## Decision rules, fixed before results

`improves` (per arm, identical to the three previous protocols, always
against the sealed control): both profiles numerically valid, paired
comparison passes, every original reserved guard passes in both profiles,
worst-profile absolute gap strictly below the control's, and J15 ATP and
J15 ADP each not below the control in both profiles.

Classification, in order:

1. `numerical_failure`: a numerical gate or the paired comparison fails on
   the hypothesis arm.
2. `combined_effect_supported`: the hypothesis arm improves.
3. `pepase_alone_effect_only`: the hypothesis arm does not improve but the
   single-factor arm does.
4. `no_supported_effect`: otherwise. The intermediate arm alone never
   changes the class.

Flags reported for each new arm whatever the class. The "reference" of an
arm is the sealed trajectory with the same AK capacities: the control for
`pepase_floor_only`, `ak_only` for the two combined arms.

- `early_only`: J4 ATP above control in both profiles but the arm does not
  improve.
- `failed_guards`: list; `pep_guard_failed`: any failed guard on PEP.
- `beyond_reference`: worst-profile gap strictly below the reference's and
  J15 ATP and ADP each not below the reference in both profiles. Guards are
  not required for this flag; it does not count as an improvement.
- `pk_share_J1_J4`, `pk_share_J1_J15`: PK / (PK + VPEP_PASE) executed
  integrals (ultrastrict); `pk_share_raised`: J1-J15 share above the
  reference's.
- `net_ATP_change_mM`: J1-J4 net ATP balance minus the control's.
- `absolute_J15_targets_reached`: expected false.
- `monotone_response` (campaign level): the intermediate arm's
  worst-profile gap lies between `ak_only`'s and the hypothesis arm's.

An early ATP rise alone, or `beyond_reference` alone, is not a positive
result. Whatever the class: working center, grouped search design and J1
conventions retained, nothing promoted, no calibration launched. A
supported class only authorizes proposing a later protocol to the user.

## Limits stated in advance

Two capacities at two levels do not map a response surface. The floor is a
bound of an exploratory box, not a physiological value; the reaction itself
has no RBC-GEM counterpart, so no value of its capacity is validated. PK
capacity, its regulators and km_PEP are unchanged. B13PG supply and the
duplicated B13PG initial stock are unchanged and may bound the effect. The
balanced AK ratio rests on the unresolved observation contract. Results
hold for this parameter set, network and positivity policy.

## Verification and closeout

Independent verifier, which imports neither decision module: checks that
the sealed AK arm is the working center with only its forward AK capacity
changed and sits at the balancing ratio re-derived from the native law,
that only the three registered capacities differ in each arm, follow their
rules and stay inside the box, that no Km changed and every measured J1
value is intact; re-verifies each replay; rescores guards and gaps for the
new arms and both sealed trajectories; recomputes PK, phosphatase and gross
ATP integrals by a separate code path; re-derives classification and flags.
Seal every folder; manifest last. Targeted tests pass before the archive is
created. The full repository suite is not run.

Files written before launch: `src/fla_ak_pepase.py`,
`scripts/run_ak_pepase.py`, `scripts/verify_ak_pepase.py`,
`qa/test_fla_ak_pepase.py`.
