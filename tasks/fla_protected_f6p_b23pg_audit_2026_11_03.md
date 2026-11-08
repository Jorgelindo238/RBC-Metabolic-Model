# Fixed-parameter F6P-B23PG executed-flux audit

Date: 2026-11-03. Requested follow-up to the protected nine-pool calibration.

## Decision

The early F6P regression is dominated by loss of PFK consumption before J4,
not increased PPP return. The B23PG regression appears mainly after J4, when
executed DPGM replenishment collapses while phosphatase consumption persists.
PGK's minimum-availability consumer shifts predominantly from ADP to B13PG.
These are exact trajectory accounts, not causal predictions of a kinetic edit.

No network coefficient error is demonstrated in these four pool balances.
No new ODE integration, optimization, source rescaling, initial-state change,
kinetic change, threshold change or biological promotion occurred. Each of the
two previously selected parameter sets is held fixed throughout this audit.

Completed scientific archive:
`output/protected_f6p_b23pg_executed_audit_2026_11_03_v3/`.
Verification and reviewed figure:
`output/protected_f6p_b23pg_validation_2026_11_03/`.

## Scope and source contract

Use archived J1-J10 GLUT-only control and protected-candidate replays, each
strict/ultrastrict. The protected selection has label `control` because that
optimization START won; it is not the unchanged GLUT-only comparator.
Sources are resolved from the sealed November2 execution design and selected
summary, not from a mutable production-default parameter file.

Preserve all770 original Sheet1 concentrations,55 measured J1 entries and all
latent initialization. Preserve native VELAC, clamped pHi7.2, borrowed H0.58,
OPLAH, affinities and reaction_consistent threshold0.001mM. Observe only actual
J1/J4/J8 values; J10 has no assay and J8-J10 is a numerical window only. No
late residual, interpolated experimental point or derived independent teacher
is introduced. Duplicate B13PG/B23PG and P2G/P3G source series are confirmed
across the original table; their two aliases are not independent evidence.

Six windows are examined: J1-J2, J2-J4, J1-J4, J4-J8, J1-J8 and J8-J10.
Overlapping windows are separate views and must not be summed as disjoint data.
Intracellular contributions are in mM on their existing cellular reference
litre; no volume conversion is introduced.

## Exact balances and numerical method

The archived matrix must match these complete supports exactly:

```text
dF6P/dt   = VPGI + VTKL2 + VTAL - VPFK
dB23PG/dt = VDPGM - V23DPGP
dB13PG/dt = VGAPDH - VPGK - VDPGM
dPEP/dt   = VENOPGM - VPK - VPEP_PASE
```

All terms above mean EXECUTED signed rates. Recover accepted-step Gauss4/8
integrals from saved nodes, weights, states and rates. Reconstruct daily and
window budgets without trapezoidal integration or a fresh simulation. Integrate
positive and negative signed pool contributions before netting. For a reaction,
`modifier=executed-raw`; differences between candidates therefore obey
`delta(executed)=delta(raw)+delta(modifier)`.

Allocate absolute execution loss to minimum-availability consuming pools,
reversing consumers for a negative net rate and sharing ties. Product pools
cannot limit a positive rate. This is descriptive numerical accounting along
the actual trajectories, not microscopic forward/reverse exchange, a no-limiter
simulation or a demonstrated causal rescue.

For PFK only, the0.02 capacity factor is checked at14 shared saved states.
The ordered raw-flux comparison is
`I_new-I_control=(0.02-1)*I_control+(I_new-0.02*I_control)`.
The first term holds the control states fixed; the second records the different
state trajectory. No counterfactual ODE is solved and no causal share is inferred.

## F6P: the major excess is established before J4

Signed executed F6P contributions on J1-J4:

| Reaction | GLUT-only, mM | Protected, mM | Protected minus control, mM |
| --- | ---: | ---: | ---: |
| VPGI | +0.170036 | +0.028987 | -0.141050 |
| VTKL2 | +0.381180 | +0.354133 | -0.027047 |
| VTAL | +0.505148 | +0.473237 | -0.031911 |
| VPFK | -1.067734 | -0.116466 | +0.951269 |
| Net | -0.011370 | +0.739892 | +0.751261 |

At J4, F6P is0.808970 versus control0.057709 and nominal0.088255mM. PPP return
VTKL2+VTAL actually falls0.886328 ->0.827370mM; PGI input falls as well. The
dominant positive accounting difference is therefore reduced PFK consumption.
PFK raw and executed integrals agree on J1-J4 in both cases: the positivity
limiter is not responsible for this early PFK loss.

The shared investment factor reduces VPFK Vmax2.549430647 ->0.050988613mM/day
along with VHK. At fixed control states this accounts for-1.046380mM raw PFK
flux; the different protected states restore+0.095111mM, leaving-0.951269mM.
The higher F6P/ATP states partly offset the capacity change, so the actual flux
ratio is not simply0.02. This algebra does not isolate the causal effect of PFK
from the other jointly changed parameters.

On J4-J8, the pattern changes: executed PFK rises0.044164 ->0.131434mM despite
its smaller capacity. The control loses0.034426mM raw PFK to ATP availability;
the protected case does not. F6P consequently decreases slightly0.808970 ->
0.791198mM, while the control increases0.057709 ->0.440514. The protected J8
excess is largely inherited from its pre-J4 accumulation, not continued faster
accumulation throughout J4-J8. Both predictions remain above nominal0.081876.

## B23PG: replenishment, not a large phosphatase increase

At J4 the protected B23PG absolute error is slightly better:3.169663 versus
nominal3.025404mM, compared with control2.861690. At J8 it is worse:1.249613
versus nominal2.014146, compared with control1.467902. A single monotone
"always worse" explanation would be incorrect.

J4-J8 positive reaction integrals:

| Reaction | GLUT-only, mM | Protected, mM |
| --- | ---: | ---: |
| VGAPDH executed | 0.703791 | 0.687450 |
| VPGK executed | 0.128753 | 0.621674 |
| VDPGM raw | 1.750715 | 0.631014 |
| VDPGM executed | 0.574717 | 0.065738 |
| V23DPGP executed | 1.968504 | 1.985787 |

The B23PG net change is-1.393787 ->-1.920049mM. Its-0.526262mM difference is
the sum of-0.508979mM less DPGM replenishment and-0.017283mM extra phosphatase
consumption. DPGM and phosphatase kinetic constants are unchanged between cases.

The B13PG balance shows almost unchanged GAPDH input, more PGK withdrawal and
less DPGM withdrawal. At J8, model B13PG is0.000129517 versus control0.000452839mM.
For PGK,91.27% of the control's J4-J8 absolute execution loss is allocated to
ADP and8.73% to B13PG; in the protected case it is allocated entirely to B13PG.
Thus this trajectory moves the limiting pool rather than eliminating scarcity.
This is not an independent measurement of B13PG: its source channel is exactly
duplicated from B23PG and cannot supply a second independent teacher.

DPGM retains32.83% ->10.42% of its raw integral, with B13PG the sole minimum
consumer. However, its ABSOLUTE numerical loss decreases1.175998 ->0.565276mM.
The exact difference is
`-0.508979 = -1.119700 + 0.610721mM` (raw change plus modifier change).
Do not claim that an increased absolute limiter loss explains the regression.
Most of the decline is already present in the raw substrate-dependent rate;
the modifier difference partially offsets it.

The implemented local law is
`VDPGM_executed = f_pH*Vmax*B13PG/(Km_B13PG+B13PG)*min(B13PG/0.001,1)`.
Here Km_B13PG remains0.002839235mM. Below the availability threshold, the
same small substrate enters both the kinetic saturation and numerical factor.
This helps explain the strong substrate sensitivity but does not authorize
fitting/removing the numerical threshold or changing the measured J1 source.

## PEP: aggregate protection hides a J8 regression

PEP J4 improves0.118845 ->0.147371mM against nominal0.158125. At J8 it worsens
0.091597 ->0.131777 against nominal0.093922. The absolute J8 error increases
0.00232514 ->0.03785554mM despite a nearly unchanged two-point training RMSE.

On J4-J8 the signed contribution differences are ENOPGM+0.067888,
PEP phosphatase+1.065433 (less consumption) and PK-1.121667 (more consumption).
These nearly compensate in the PEP balance. The lower capacity factors for PK
and PEP phosphatase therefore do not imply lower fluxes for both along different
trajectories. Pool RMSE alone can trade improvement at J4 against failure at J8.

## Proposed broader guard contract, not activated

`proposed_guard_contract.json` extends the nine training RMSE guards with F6P
and B23PG and adds pointwise absolute-error guards for PEP at both J4 and J8.
Use only actual J4/J8 values, the same GLUT-only reference and the unchanged
engineering allowance1e-5mM+1e-4*reference_error, with25% available during fitting.
The current protected candidate fails F6P/B23PG RMSE and PEP at J8; the unchanged
control passes by construction. Aliases B13PG/P2G are excluded from the future
likelihood. Eleven channels would provide22 source residuals, not22 independent
assays;44 other source representations remain audit-only.

This proposal is not wired into calibration, used to reselect the parent,
presented as assay precision, or claimed to establish biological accuracy.
The next execution should implement and test this broader contract before
screening the SAME six-coordinate box for feasible improvement. Keep RIB(0),
redox initialization, threshold, OPLAH and additional kinetic coordinates closed.
If that restricted screen finds only the control, a later explicitly declared
VHK/VPFK decoupling hypothesis can be considered; this audit neither runs it
nor proves that no feasible improvement exists in the current box.

## Verification and retained evidence

- [x] Reverify the November2 archive:4705 checks, including770 source values.
- [x] Preserve55 input hashes and all old scientific archives.
- [x] Pass312 quadrature reconstruction, window balance and profile checks.
- [x] Pass912/912 per-consumer Gauss4/8 allocation-resolution checks.
- [x] Export192 pool budgets,888 signed reaction rows and1824 allocation rows.
- [x] Pass8508 independently recomputed hash/budget/guard/alias checks; no new ODE solver.
- [x] Full final QA1337 passed/two existing skips/six existing Optuna warnings in117.55seconds.
- [x] Inspect the figure and preserve a presentation-only readable successor with shared scales.

Maximum window closure residual across all eight context pools/profiles is
1.80159e-6mM, within the unchanged parent absolute-plus-relative contract.
Allocation labels are numerical trajectory attributions, not physiological
enzyme control coefficients. Existing Python3.14/Pydantic startup warning remains.

The initial two analysis attempts are retained as partial directories. The
first incorrectly compared dense initial interpolation bitwise (maximum
roundoff1.11e-16mM); the second encountered a local parameter/path variable-name
collision before fixed-state rate checking. Actual initial vectors/accepted
states are unchanged. The completed `_v3` checks them exactly and tests the
separate dense-rounding and parameter-mapping boundaries. Neither failed attempt
ran a new simulation or changed a scientific source. No earlier archive is repaired
in place.

![Executed-flux attribution](../output/protected_f6p_b23pg_validation_2026_11_03/figures/f6p_b23pg_pep_attribution_readable.png)

The figure's two contribution panels share their scale within each pool.
Markers are original nominal concentrations without invented uncertainty bars.
The initial figure remains in the scientific archive; presentation-only code
and figure have a separate manifest in the validation directory.

## Reproduction

```powershell
python scripts/audit_protected_f6p_b23pg.py --out output/protected_f6p_b23pg_fresh
python scripts/verify_protected_f6p_b23pg.py --archive output/protected_f6p_b23pg_fresh --receipt output/protected_f6p_b23pg_validation_fresh/verification.json
python scripts/plot_protected_f6p_b23pg.py --archive output/protected_f6p_b23pg_fresh --out output/protected_f6p_b23pg_validation_fresh/figures
```
