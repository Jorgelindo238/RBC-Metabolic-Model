# Adenylate kinase forward/reverse ratio diagnostic at the working center: protocol

Registered on 2026-11-11 before any integration of its arms. This file is
hash-frozen into the archive at launch; status and outcome are reported
only in `tasks/fla_ak_ratio_results_2026_11_11.md` and at the top of
`fla_progress_log.md`. Config: `config/fla_ak_ratio_2026_11_11.json`.
Fresh archive: `output/ak_ratio_2026_11_11/`.

Follow-up to `tasks/fla_ribose_stock_results_2026_11_10.md` (post hoc
observation and option 1 of its next-step list). Preparation authorized by
the user on 2026-11-11; launch needs a separate authorization.

## Single hypothesis

At the retained working center (absolute attempt 76), the coded adenylate
kinase forward/reverse capacity ratio Vf/Vr = 10.766, which has never moved
because both capacities share one factor in every search, accounts for part
of the early ATP/ADP loss and AMP accumulation.

Fixed kinetics. Not a calibration, not a correction of measured data, not a
thermodynamic or biological claim about stored red cells.

## What is known before launch

Read from sealed evidence and the coded law, no arm integrated:

- Coded law (`src/equadiff_brodbar.py`, line 1524):
  `VAK = Vf*mm(ADP,K_ADP) - Vr*mm(AMP,K_AMP)*mm(ATP,K_ATP)`, positive in
  the direction 2 ADP -> ATP + AMP. It is a difference of saturating terms
  with no Haldane constraint.
- Working center: vmax_VAK 2.135939, vmax_VAK_rev 0.198395, ratio 10.766;
  both at factor 1.098063 against the frozen base (1.945189, 0.180677).
- Registered design group `AK` = [vmax_VAK, vmax_VAK_rev], factor bounds
  [0.05, 2.0], one shared factor. NDPK is grouped the same way and is not
  touched here.
- At the frozen J1 state the raw coded rate at the working center is
  +1.4904 mM/day. The ratio that zeroes the coded law at that state,
  derived from the executable rate function (linearity in both capacities
  checked, not assumed), is 0.6669045865. It is identical on the native and
  compiled backends.
- Post hoc table of 2026-11-10: at the observed adenylates of J1, J4, J8,
  J11, J15 the zeroing ratio is 0.667, 0.673, 0.659, 0.698, 0.716.
- Sealed control, J1-J4 executed: AK +1.1208 mM (2 ADP -> ATP + AMP), gross
  ATP consumption 5.6560, production 4.7470, net -0.9090; AMP about 2.50 mM
  at J4.
- AK conserves the adenylate phosphoryl stock E_A = 2 ATP + ADP and total
  adenylates. A ratio change adds or removes no inventory; it can only
  change the ATP/ADP/AMP partition and what AMP- and ADP-dependent
  reactions then do. In the control AK is a gross ATP producer, so lowering
  its forward capacity removes an ATP source while sparing ADP and AMP
  formation. The sign of the net effect is not assumed.
- Precedent of 2026-11-04: a common forward/reverse AK x0.5 factor was a
  strong J1-J4 lever and was rejected on G6P/F6P/PEP and other guards. That
  test kept the ratio at its coded value.
- Lesson from the guanylate and RIB(0) diagnostics: about 1 mM of early ATP
  demand removed was matched by an equal fall in production. Compensation
  criteria are registered here.

## Arms

Only vmax_VAK and vmax_VAK_rev differ from the working center. Values are
derived by rule at launch and must reproduce the registered ratio to 1e-9
relative; each factor against the frozen base must stay inside the
unchanged [0.05, 2.0] box, otherwise the launch is refused.

| Arm | Role | Rule | vmax_VAK | vmax_VAK_rev | Vf/Vr | Factors vs base (f, r) |
| --- | --- | --- | --- | --- | --- | --- |
| control (sealed, not reintegrated) | control | working center | 2.135939 | 0.198395 | 10.766 | 1.0981, 1.0981 |
| balanced_forward_lowered | hypothesis | reverse at center, forward lowered to the balancing ratio | 0.132310 | 0.198395 | 0.6669 | 0.0680, 1.0981 |
| balanced_reverse_upper_bound | capacity | same ratio at the highest reverse capacity the box allows | 0.240989 | 0.361354 | 0.6669 | 0.1239, 2.0000 |
| intermediate_ratio | monotonicity | reverse at center, ratio at the geometric mean of 10.766 and 0.6669 | 0.531608 | 0.198395 | 2.6795 | 0.2733, 1.0981 |

The capacity arm separates the ratio from the absolute capacity: same
ratio, both capacities 1.82 times higher. The intermediate arm exists only
to see whether the response is monotone. No value is a physiological bound
or prior. Six J1-J15 integrations: three arms, strict and ultrastrict.

The balancing ratio is defined at the frozen J1 state only. The trajectory
then moves, so no arm is expected to keep AK at zero net flux.

## Search design

The registered grouped design is retained. The pair is not ungrouped in any
search: each arm is a literal parameter vector replayed at fixed kinetics.
Because the shared replay routine rebuilds parameters from grouped log
factors, each arm is replayed with its own literal vector as base and all
14 log factors at zero; the launch checks that this reproduces the arm
vector exactly. Whether a later search may ungroup AK is a separate user
decision that this protocol does not take.

## Frozen contract

Unchanged and hash-verified against `output/vmax_requalification_2026_11_09/`:
all 55 Sheet1 J1 values including the ambiguous B13PG row, every latent
state (GDP, GTP, RIB, R5P, PRPP, ADESUC at their frozen values), every
working-center Vmax other than the two AK capacities, every Km, network
gem_corrected -> redox_gssg_abc, hematocrit 0.58, clamped pH, availability
threshold 1e-3 mM, rejection tolerance -1e-10 mM, guard reference (old
historical full control per profile) and reserve. Recipe: SciPy 1.17.1,
Radau, bounded fine Jacobian, strict (1e-8/1e-12) and ultrastrict
(1e-9/1e-13), max_step 0.05 day, compiled backend.

No retry, clipping, bound change, optimization, follow-up calibration, J46
run, promotion or default change.

## Outputs per arm and profile

- ATP, ADP, AMP, IMP, ADESUC, GTP, GDP, R5P, PRPP, B23PG, PEP, G6P, F6P at
  J1, J4, J8, J11, J15.
- All original dated guards with reserve and the absolute J15 gap, ATP and
  ADP sides separately.
- Executed integrals on J1-J4, J4-J8, J8-J15 for AK, AK2, AMPD1, ADSS,
  ADSL, NDPK, PRPPASe, RKa, HK, PFK, PGK, PK, HGPRT1; gross ATP production
  and consumption.
- Phosphoryl stocks E_A = 2 ATP + ADP and E_G = GDP + 2 GTP.
- Daily executed balances, quadrature convergence, native/compiled rate
  checkpoints, strict/ultrastrict paired comparison.

## Decision rules, fixed before results

`improves` (per arm, identical to the guanylate and RIB(0) protocols): both
profiles numerically valid, paired comparison passes, every original
reserved guard passes in both profiles, worst-profile absolute gap strictly
below the sealed control's, and J15 ATP and J15 ADP each not below the
control in both profiles.

Classification, in order:

1. `numerical_failure`: a numerical gate or the paired comparison fails on
   the hypothesis arm.
2. `ak_ratio_effect_supported`: the hypothesis arm improves.
3. `capacity_dependent_effect_only`: the hypothesis arm does not improve
   but the capacity arm does.
4. `no_supported_effect`: otherwise. The intermediate arm alone never
   changes the class.

Flags reported for each arm whatever the class, with dAK, dC, dP the J1-J4
reductions versus control of executed signed AK, gross ATP consumption and
gross ATP production (ultrastrict):

- `early_only`: J4 ATP above control in both profiles but the arm does not
  improve.
- `failed_guards`: list.
- `ak_flux_reduced`: dAK > 0.
- `consumption_compensation`: dAK > 0 and dC >= 0.5 * dAK (demand fell with
  the removed AK production).
- `net_ATP_change_mM`: dC - dP, the change of the J1-J4 net ATP balance.
- `absolute_J15_targets_reached`: expected false.
- `monotone_response` (campaign level): the intermediate arm's worst-profile
  gap lies between the control's and the hypothesis arm's.

The 0.5 fraction is an engineering convention fixed here. An early ATP rise
alone is not a positive result. Whatever the class: working center, grouped
search design and J1 conventions retained, nothing promoted, no calibration
launched. A supported class only authorizes proposing a later protocol to
the user.

## Limits stated in advance

Three points do not map a response surface. The balancing ratio is a
property of the coded law at one state and of the assumption that Sheet1
ATP/ADP/AMP are free enzyme substrate; the observation contract is
unresolved (J1 energy charge 0.53 with ADP above ATP). The law has no
Haldane constraint, so "balanced" is not a statement about equilibrium.
The hypothesis arm puts the forward factor at 0.068, near the lower bound
0.05, and the capacity arm puts the reverse factor on the upper bound 2.0.
AK2 and NDPK are unchanged and may absorb the change. Results hold for this
parameter set, network and positivity policy.

## Verification and closeout

Independent verifier, which does not import the decision module: re-derives
the balancing ratio from the native rate law, checks that only the two AK
capacities differ from the working center, follow their registered rules,
stay inside the box and that no Km changed, that the balanced arms zero the
native law at frozen J1, that every measured J1 value is intact, re-verifies
each replay, rescores guards and gaps, recomputes the J1-J4 integrals by a
separate code path, and re-derives classification and flags. Seal every
folder; manifest last. Targeted tests pass before the archive is created.
The full repository suite is not run.

Files written before launch: `src/fla_ak_ratio.py`,
`scripts/run_ak_ratio.py`, `scripts/verify_ak_ratio.py`,
`qa/test_fla_ak_ratio.py`.
