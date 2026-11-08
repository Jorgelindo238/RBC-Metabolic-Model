# Fixed VSAM/PGK half-step: J46 replay result

The sealed half-step was replayed continuously from exact J1 to J46 with
VSAM0.19518001458970666 and PGK39.17685218740367. Every other parameter,
latent initial state, configured GLUT law, native VELAC, pH, geometry and
reaction-availability threshold was unchanged. The two new original ODE
profiles were compared with the corresponding archived J46 reference profiles.
No reset, forcing, refit, new active reaction or default change.

## Observation comparison

| Window | Strict log-adenylate error reduction | Ultrastrict reduction | Registered guards |
|---|---:|---:|---|
| J4-J15 |0.382957%|0.382965%|Pass both|
| J18-J46 |0.259635%|0.259646%|Pass both|
| J4-J46 |0.290448%|0.290459%|Pass both|

All55 working MSE guards and individual/timewise adenylate guards pass.
This is relative to an inaccurate reference, not absolute accuracy. Twenty
of55 raw RMSEs rise in the late ultrastrict window, within the registered
engineering allowance; largest increases are AMP0.00422777mM and
B23PG0.000187271mM. The early-derived absolute scales were not refit on late
observations. All source times are genuine archived samples, not interpolated
targets. J46 was previously exposed; it is not independent validation.

Ultrastrict J46 endpoints in nominal mM coordinates:

| Pool | Reference | Half-step | Observed |
|---|---:|---:|---:|
| ATP |1.774790e-5|1.782852e-5|0.469757|
| ADP |1.184431e-6|1.208792e-6|0.165503|
| AMP |1.035814|1.039734|0.221310|
| EGLC |16.922500|16.922214|12.915000|
| GLC |6.968671|6.968436|0.826365|
| LAC |0.147005|0.147001|6.462934|
| ELAC |20.584531|20.586572|28.363716|

The ATP endpoint gain is only8.06e-8mM. The glucose/lactate mismatch and the
energy deficit persist. Energy charge at J46 changes from1.770567e-5 to
1.772817e-5; AMP moves further from its nominal observation.

## Executed fluxes

Over J15-J46, reference ATP production/consumption is
0.00110428452/0.00116988906mM, versus0.00111699085/0.00118306922mM with the
half-step. The late net balance becomes more negative by about4.74e-7mM.
Thus most of the5.54e-7mM ATP advantage at J15 is lost by J46; the small
terminal gain does not represent sustained energetic restoration. The signed
budgets retain each reaction, including the late increase in net PGK output
and increase in net NDPK demand, rather than assuming Vmax changes are flux
changes of the same sign. Complete ATP/ADP/AMP budgets are in `comparison.json`.

## Checks and disposition

Both numerical profiles and the cross-tolerance comparison pass. New replays:
10170 daily executed balances,9000 raw and9000 executed quadrature comparisons,
46403 cross-tolerance comparisons. The verifier re-evaluates36 live original
rate checkpoints across both cases and profiles. Minimum checked concentration
is0mM. All55 observed J1 values and the full latent J1 vector remain exact.
Thirty-four targeted tests pass. The external comparison preserves330
pool/window/profile comparisons and1540 source-time rows.

Retain the half-step as a conditional comparator only. Its late error gain
is robust to the two tested solver tolerances but too small to justify a wider
search on this evidence. Do not promote as a new default or biological fit.

Archives: `output/vsam_pgk_j46_2026_11_04/` (original replays),
`output/vsam_pgk_j46_comparison_2026_11_04/` (comparison and verification),
`output/vsam_pgk_j46_qa_2026_11_04/` (targeted tests and closeout).
