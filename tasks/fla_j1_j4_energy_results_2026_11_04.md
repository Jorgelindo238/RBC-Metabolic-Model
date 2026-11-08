# J1-J4 energy feasibility with neighboring fluxes fixed

Executed the [registered protocol](fla_j1_j4_energy_protocol_2026_11_04.md) on
the two original VSAM/PGK half-step archives. All55 nominal J1 concentrations
and the latent initial vector are bit-exact in the accepted initial state.
The dense interpolant differed from that state by at most1.11e-16mM; the first
audit stopped on an overly strict interpolant check, then used the verified
accepted J1 vector in the calculation. No parent replay was edited.

## Gap and PGK availability

For H=ATP+0.5*ADP, nominal J1-to-J4 change is+0.0987002mM and executed
change is-1.4917583mM. The J4 H gap is1.5904584mM. All figures refer to
the nominal observation coordinates, not assay-confirmed energy units.
In ultrastrict, the PGK raw-minus-executed contribution to H is1.0508791mM;
the availability factor reconstructed from archived states attributes all
of that difference to B13PG at J1-J4. This difference is not a recoverable
ATP reserve. With other extents fixed, additional PGK can consume at most
0.000134751mM B13PG by J4, the residual model stock. ADP and B13PG identities
are distinct; the source B13PG alias is not an independent fit target.

## Conditional feasibility

Ultrastrict results (strict agrees):

| Opened directional extent group | Highest J4 H, mM | Minimum joint ATP/ADP/AMP band multiplier |
|---|---:|---:|
| None |0.0259340|16.038182|
| PGK increase under archived raw envelope |0.0260014|16.038182|
| NDPK/PRPPASe reductions |0.1935441|14.696201|
| Both mechanisms |0.1935441|14.696201|
| Both, no PGK raw ceiling |0.1935441|14.696201|

The H maxima are identical with and without the additional50 off-target
working guards. The joint fits enforce these guards and daily nonnegative
stocks. None reaches unit working bands. The nominal J4 H is1.6163924mM;
only10.54% of the gap can be covered, even by the optimistic combined case.
All other extents stay at their archived executed values. Glucose/lactate
amount balances are preserved, not newly fitted to the nominal targets.

For cumulative deviations p=PGK increase, n=NDPK reduction, r=PRPPASe
reduction, the actual matrix gives `delta_ADP=-p-n`, `delta_B13PG=-p`,
`delta_PRPP=-r`, `delta_AMP=-r`, and `delta_H=0.5*(p+n)+r`. The total
adenylate correction is zero. Hence J4 ADP cannot exceed the reference
0.00437411mM against nominal1.073256mM. Nonnegative PRPP limits r to0.1654231mM;
nonnegative ADP limits p+n to0.00437411mM. These constraints give exactly the
optimistic H bound above. AMP cannot fall below2.3507772mM against nominal
0.5392080mM; this independently explains the optimal14.696201 working-band
multiplier. Even reversing the sign of the PGK/NDPK perturbations does not
increase ATP+ADP beyond0.1935441mM with PRPP supply fixed, versus nominal
2.1530203mM. VAK has zero direct coefficient in both H and total adenylates;
changing it could still affect other rates indirectly in a free ODE.

This is a conditional rejection of the proposed extent changes with the
other fluxes fixed, not global kinetic infeasibility. In particular, latent
PRPP/B13PG stocks are model-dependent. The screen does not authorize relaxing
positivity, reducing PRPPASe to an LP boundary, or adding an ATP source.

## Separate Yurkovich 4C check

Verified the hashes of the archived primary workbook/PDF and the previously
independently verified extracts. Checked72 records: eight original times for
three channels in each of three sheet-specific blocks. J1-to-J4 changes:

| Channel | Block1 | Block2 | Block3 |
|---|---:|---:|---:|
| ATP, `assay!C` |+0.02986268|+0.13776375|+0.31229539|
| ADP, `endo!G` |+0.288620|+0.455840|+0.549388|
| AMP, `endo!H` |-0.016381|-0.030910|+0.020650|

The measured signals do not show the simulated early ATP/ADP collapse in
these separate traces. That is a descriptive cross-check, not numerical
validation of Sheet1. ATP endo/exo and free/total semantics remain unresolved;
cross-sheet donor pairing is unknown. No joint ATP/ADP/AMP charge, normalization
transfer, rescaling, donor assignment or calibration import was performed.

## Checks and disposition

Reconstructed678 daily pool balances and1200 raw/executed cross-order checks.
The 30 LPs pass primal/dual verification (maximum gap1.78e-15); both profiles
agree on rejection. Separate rerun reproduces the summary and all600 daily
reaction rows. Sixteen targeted tests pass. No new ODE, refit or model change.

No single lever is admitted for a free replay. A subsequent test must allow
a justified change outside these frozen extents, e.g. coupled upstream
B13PG supply and adenylate partition, with a source-backed observation
contract. Do not interpret latent stocks as measured or open a broad search.

Archive: `output/j1_j4_energy_feasibility_2026_11_04/`; receipts:
`output/j1_j4_energy_feasibility_validation_2026_11_04/`.
