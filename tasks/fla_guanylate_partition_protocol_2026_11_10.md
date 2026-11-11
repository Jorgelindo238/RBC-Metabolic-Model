# Latent guanylate partition diagnostic at the working center: protocol

Registered before launch on 2026-11-10 after explicit user authorization.
This file is hash-frozen into the archive; outcome and status are reported
only in `tasks/fla_guanylate_partition_results_2026_11_10.md`. Config:
`config/fla_guanylate_partition_2026_11_10.json`. Fresh archive:
`output/guanylate_partition_2026_11_10/`.

Follow-up to `tasks/fla_atp_attribution_results_2026_11_10.md` and to the
read-only J1 provenance audit of 2026-11-10.

## Single hypothesis

At the retained working center (absolute attempt 76), part of the early
ATP/ADP loss is due to the initial PARTITION of the latent guanylates
(GDP = GTP = 1 mM, a generic software default), and not to the phosphoryl
INVENTORY that a different partition would add.

This is a fixed-kinetics diagnostic of an unmeasured convention. It is not
a calibration, not a correction of measured data, not a biological claim.

## Reasoning corrections carried into this protocol

- The 0.834 mM GTP gain and 1.082 mM ADSS use found earlier are an
  accounting split of net NDPK flux, not a predicted ATP recovery.
- The factor 1.8 is phosphoryl-equivalent demand over supply on J1-J4.
- The Vmax search found a local guard-limited point, not global
  infeasibility.
- The coded law is
  `VNDPK = Vf*mm(GDP,K_GDP)*mm(ATP,K_ATP) - Vr*mm(GTP,K_GTP)*mm(ADP,K_ADP)`
  (`src/equadiff_brodbar.py`, line 1532). Its zero is NOT GTP/GDP = ATP/ADP
  and is not asserted to be a thermodynamic equilibrium: the law is a
  difference of independently saturating terms with no Haldane constraint.
  Common scaling of both Vmax leaves the zero surface unchanged.
- One zero-flux condition does not determine two unknown pools. A second,
  declared convention is required, and it is unmeasured too.
- With E_G = GDP + 2*GTP, precharging GTP at fixed total adds
  delta_E_G = delta_GTP of unmeasured phosphoryl stock. An ATP saving in
  that arm can be a pure inventory effect.

## Arms

All arms use the working-center Vmax, the frozen J1 vector and the same
network. Only GDP(0) and GTP(0) differ. The zero is solved on the actual
executable right-hand side at day 1 (raw VNDPK = 0, brentq), not from a
transcribed formula. Values below were computed from J1 states only, before
any integration; the runner recomputes and must reproduce them to 1e-9 mM.

| Arm | Second convention | GDP(0) mM | GTP(0) mM | Total mM | delta_E_G(0) mM |
| --- | --- | --- | --- | --- | --- |
| control | current default | 1.0 | 1.0 | 2.0 | 0 |
| A_fixed_total | GDP + GTP = 2 | 0.067476269 | 1.932523731 | 2.0 | +0.932523731 |
| B_fixed_phosphoryl | GDP + 2 GTP = 3 | 0.062506793 | 1.468746604 | 1.531253396 | 0 |

Raw VNDPK at day 1 is 6.634037606 mM/day in the control and zero in A and
B. The zero holds at day 1 only; ATP and ADP then move. ADSS raw rate at
day 1 rises from 0.258282 to 0.307789 mM/day in arm A because GTP is higher.

Arm A is the inventory-confounded arm. Arm B is the inventory-matched arm
and carries the hypothesis. Neither total is measured; no physiological
bound is claimed for either.

## Frozen contract

Unchanged and hash-verified against `output/vmax_requalification_2026_11_09/`:
all 55 Sheet1 J1 values including the ambiguous B13PG row, HYPX and IMP,
every other latent state, the working-center Vmax, every Km, network
gem_corrected -> redox_gssg_abc, hematocrit 0.58, clamped pH, availability
threshold 1e-3 mM, rejection tolerance -1e-10 mM, guard reference (old
historical full control per profile) and reserve. Recipe: SciPy 1.17.1,
Radau, bounded fine Jacobian, strict (1e-8/1e-12) and ultrastrict
(1e-9/1e-13), max_step 0.05 day, compiled backend.

Four new J1-J15 integrations: arms A and B, two profiles. The control is
the sealed requalification working-center control and is not reintegrated.
No retry, no clipping, no parameter or bound change, no optimization, no
automatic follow-up calibration, no J46, no promotion, no default change.

## Outputs per arm and profile

- ATP, ADP, AMP, GMP, GDP, GTP, ADESUC at J1, J4, J8, J11, J15.
- All original dated guards with reserve (PEP, G6P, F6P, AMP point caps,
  canonical MSE, zero-band, adenylate log guards, dated gain), and the
  absolute J15 gap with ATP and ADP sides reported separately.
- Executed integrals on J1-J4, J4-J8, J8-J15 for NDPK, ADSS, ADSL, AMPD1,
  AK, AK2, PRPPASe, RKa, HK, PFK, PGK, PK; gross ATP production and
  consumption; ADESUC change.
- Phosphoryl-equivalent stocks E_A = 2 ATP + ADP and E_G = GDP + 2 GTP at
  each date, and E_A + E_G.
- Daily executed balances, quadrature convergence, native/compiled rate
  projection checkpoints, and the strict/ultrastrict paired comparison.

## Decision rules, fixed before results

Control values come from the sealed control scored by the same code:
worst-profile absolute gap G0 and J15 ATP, ADP per profile.

For each arm, `improves` means: both profiles numerically valid, paired
comparison passes, every original reserved guard passes in both profiles,
worst-profile gap strictly below G0, and J15 ATP and J15 ADP each not below
the control in both profiles.

Classification, in order:

1. `numerical_failure`: arm B fails a numerical gate or the paired
   comparison. No interpretation.
2. `partition_effect_supported`: arm B improves.
3. `inventory_effect_only`: arm B does not improve and arm A improves.
4. `no_supported_effect`: neither improves.

Flags reported whatever the class:

- `early_only` (per arm): J4 ATP above the control but the arm does not
  improve. An early ATP rise alone is not a positive result.
- `guard_failure` (per arm): list of failed guards.
- `compensation` (per arm): with dN the reduction of net executed NDPK on
  J1-J4 versus control and dC the reduction of gross ATP consumption on
  J1-J4, flagged when dN > 0 and dC < 0.5 * dN. The 0.5 is an engineering
  convention fixed here.
- `absolute_J15_targets_reached` (per arm): reported separately; expected
  false.

Whatever the class: the working center and its J1 convention are retained,
nothing is promoted, and no calibration is launched. A supported class only
authorizes proposing a later protocol to the user.

## Limits stated in advance

Two arms cannot map the guanylate plane; they test one partition under two
declared conventions. GDP, GTP and ADESUC remain unobserved, so no arm can
be validated against data for those pools. Results hold for this parameter
set, network and positivity policy.

## Verification and closeout

Independent verifier: recomputes both zeros on the right-hand side, checks
that only GDP(0) and GTP(0) differ from the frozen J1 vector, re-verifies
each replay (supports, balances, quadrature, native checkpoints), rescored
guards and gaps, recomputes the executed integrals with a separate code
path, and re-derives the classification and flags. Seal every folder;
manifest last. Targeted tests pass before the archive is created. The full
repository suite is not run.

Files written before launch: `src/fla_guanylate_partition.py`,
`scripts/run_guanylate_partition.py`,
`scripts/verify_guanylate_partition.py`,
`qa/test_fla_guanylate_partition.py`.
