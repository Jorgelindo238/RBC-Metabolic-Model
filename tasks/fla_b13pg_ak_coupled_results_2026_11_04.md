# B13PG supply and AK partition: fixed factorial result

## Pool evidence before simulation

Reopened the original workbook read-only and matched all770 Sheet1 cells and
14 times to the archived observations. Rows10/11 (B13PG/B23PG) and49/50
(P2G/P3G) are exact duplicates. B13PG and P2G are not independent targets.
B23PG and P3G retain their existing nominal guards, not validated physical
identities. All55 J1 values are unchanged, including the ambiguous B13PG
3.58404521mM. This shared starting stock is a limitation of the test.
The workbook does not resolve the assay denominator or free/total forms of
ATP, ADP or AMP. No new binding or observation operator was introduced.

The [Yurkovich temperature dataset](https://pubmed.ncbi.nlm.nih.gov/29030425/)
remains separate: the archived ATP endo/exo and free/total conflict and unknown
cross-sheet pairing do not support a quantitative ATP anchor. No data fusion,
source rescaling or external calibration was performed.

## ODE result

On the half-step VSAM/PGK background, six new free original J1-J4 replays
compare GAPDH capacity x1.5, both AK capacities x0.5, and the combination
against two archived reference prefixes. The original PGK capacity and all
other parameters are fixed; neighboring reaction rates respond freely to the
state. The common AK factor preserves its forward/reverse capacity ratio.
Neither factor is a fitted or assay-supported capacity estimate.

Matched ultrastrict J4 endpoints (nominal mM coordinates):

| Case | ATP | ADP | AMP | Mean log-error gain | Other guard failures |
|---|---:|---:|---:|---:|---:|
| Reference |0.023747|0.004374|2.516200|0%|0|
| GAPDH up |0.027343|0.004601|2.510107|3.43%|8|
| AK down |0.051630|0.034800|2.454924|50.66%|6|
| Coupled |0.056615|0.033320|2.448857|51.21%|8|
| Nominal source |1.079765|1.073256|0.539208|NA|NA|

The coupled case meets the directional mechanism criteria in both profiles.
J2-J4 executed GAPDH increases0.243383 ->0.330641mM and PGK0.202344 ->0.287589mM.
Thus the extra PGK flux persists after J2, not only in the initial-stock window;
this is not an isotope attribution of the carbon source. Net VAK J1-J4 falls
1.064255 ->0.938474mM but stays forward; ADP is higher at J4. The fall in net VAK
is concentrated before J2; its later integrated flux actually rises. Neither
direct energetic production nor forced reversal is implied by slowing AK.

H=ATP+0.5*ADP rises at J4 from0.025934 to0.073275mM, still far below nominal
1.616392mM. The J1-J4 H difference is+0.047341mM: PGK and PK contributions rise
by0.102098 and0.076437mM, while increased PRPPASe, NDPK and other demands offset
most of that gain. The four-corner log-MSE contrast is+0.452886 (subadditive
error reduction in this design, not a statistical synergy test). AK-only
accounts for most of the improvement; the combination gains another0.55
percentage points of baseline log error over AK-only and retains slightly
less ADP than AK-only. No active single is admissible, so the admissible
control in the registered selection is the baseline.

## Rejection and checks

All three perturbed cases exceed off-target guards. The combined case worsens
J4 G6P0.244145 ->0.259547 (nominal0.092541), F6P0.081700 ->0.058184
(nominal0.088255) and PEP0.113284 ->0.102115 (nominal0.158125). It also
worsens P3G1.742149 ->1.932679 against nominal0.247764 and exceeds GLN, GLU,
INO and SER guards. Removing the P3G identity assumption does not reverse the
decision. Relative score gain is not joint adenylate recovery.

All six original replays and three fast/full parity checks pass, with checked
minimum0mM and103839 cross-tolerance comparisons. Reconstructed2712 daily
balances and4800 raw/executed quadrature comparisons across all eight
case/profile pairs, including reused controls. Verified440 J4 source comparison
rows;21 targeted tests pass. No optimizer, promoted
parameter, new reaction, J46 extension or source change.

Keep the mechanism as a diagnostic observation only. A further targeted
test should first explain the downstream P3G/PEP imbalance and the extra ATP
demands, while retaining source identity caveats, rather than increasing the
same two perturbations or opening a broad calibration.

Original archive `output/b13pg_ak_coupled_2026_11_04/`; comparison and complete
signed flux ledgers `output/b13pg_ak_coupled_comparison_2026_11_04/`;
source receipt `output/b13pg_ak_source_2026_11_04/`.
