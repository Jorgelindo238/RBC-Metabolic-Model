# Fixed VSAM/PGK interaction screen

## Registered design

User-authorized small screen, no optimizer or production promotion. Use the
sealed J15 normalized reference and the two individually audited downward
levers from `output/coverage_adenylate_sensitivity_2026_11_03/`. Keep the full
114-state J1 vector (55 exact measured concentrations), every other kinetic
parameter, Hct0.58, pH7.2, native VELAC, GLUT law, OPLAH and reaction-consistent
threshold0.001mM. No active new branches, source changes, forcing or resets.

Five points: baseline, each separate full log decrease, both full decreases,
and both half decreases. A full decrease is -log(1.05), a half decrease is
-log(1.05)/2. Reuse six archived original strict/ultrastrict control replays.
Run both joint points under both profiles (four original integrations and two
fast-parity integrations), regardless of observed fit. No interpolation or
late-data selection. Use measured J4/J8/J11/J15 from Sheet1; J1 stays exact.

Report all55 nominal channels, including labeled B13PG/P2G aliases, separately;
do not aggregate aliases as extra evidence. The per-channel working MSE uses
`0.05*median(four observed values)+0.2*observed value` at each date, extending
the parent engineering scales. All55 scales must be positive, including ECYS
and EINO at nominal zeros; no invented detection limit. The channel allowance
is `baseline MSE+0.01*(1+baseline MSE)`. Preserve raw RMSE changes as descriptive
results, not significance tests or a claim of zero regression.

For ATP/ADP/AMP, require mean squared log error gain >=0.1% of baseline, no
individual log MSE worsening beyond1% (plus parent1e-8 numerical allowance),
and no individual time-point absolute log error increase beyond log(1.01).
Total adenylates and energy charge are derived diagnostics. Joint admission
requires numerical passes, all55 and adenylate guards, and incremental gain
>=0.1% of baseline loss over the best admissible control in EACH profile.
The reference is the best of baseline and qualifying individual levers at the
same tolerance. The old13 caps remain historical diagnostics only. None of
these criteria are assay SD, statistical tests or physiological thresholds.

Compare full-step interaction by the exact four-corner contrast
`joint - VSAM-only - PGK-only + baseline`. Reconstruct all113 daily balances,
quadrature and numerical agreement; verify raw/executed fluxes at live RHS
checkpoints. Report signed ATP/ADP/AMP budgets and all100 reaction integrals.
The half-step point probes a smaller joint move, not a second matched factorial.
No J46 screening, general parameter identification or biological validation.

## Execution

- [x] Register five points and all55 admission before any joint results.
- [x] Pass30 focused/parent tests and freeze the successor sources.
- [x] Execute both original joint audit pairs and reconstruct the comparison.
- [x] Verify the archived results, record the decision and update handoff.

Design `config/fla_vsam_pgk_screen.json`; runner
`scripts/run_vsam_pgk_screen.py`; archive `output/vsam_pgk_screen_2026_11_04/`.

## Outcome

Both joint settings pass strict and ultrastrict numerical checks. Only the
half-step combination passes the registered admission at both tolerances.
The following values are from matched ultrastrict original ODE replays:

| Case | vmax_VSAM | vmax_VPGK | Mean log-adenylate gain | Admission issue |
|---|---:|---:|---:|---|
| Baseline |0.2|40.144328|0%|Reference|
| VSAM down |0.190476|40.144328|0.5385%|AMP working MSE|
| PGK down |0.2|38.232693|0.2229%|ADP at J4|
| Joint full |0.190476|38.232693|0.7586%|AMP working MSE|
| Joint half |0.195180|39.176852|0.3830%|Pass|

The newly registered constraints are stronger than the previous single-lever
admission. Both singles fail, so the baseline is the best admissible control
in both profiles. The half-step does not outperform the raw VSAM-only gain;
it is the admissible compromise. AMP working MSE is527.238092 at baseline,
532.554080 for VSAM-only,532.720744 for full joint, and530.003726 for half
joint; the allowed ceiling is532.520473. PGK-only ADP J4 falls from0.00429147
to0.00424496mM, beyond the pointwise allowance; the half-step joint rises to
0.00437411mM. These thresholds are engineering margins, not experimental
significance. Half-step raw RMSE rises in15/55 strict and16/55 ultrastrict
channels. In ultrastrict the largest rises are AMP+0.00475232mM and
B23PG+0.000895025mM. No all-channel improvement claim.

The full-step four-corner mean log-MSE contrast is+0.00189572 strict and
+0.00190458 ultrastrict: near-additive reduction, slightly below the sum of
single effects (about0.00290 percentage points of baseline loss in ultrastrict).
No evidence here for a synergistic ATP rescue. ATP J15 baseline/half-step is
8.335252e-5/8.390680e-5mM versus nominal1.0138273mM; ADP6.143240e-7/
6.415299e-7 versus nominal0.450640mM; AMP1.923917/1.928673 versus nominal
0.258136mM. Energy charge is4.348215e-5/4.366934e-5 versus nominal0.719346.

Half-step VSAM ATP consumption falls by0.00488179mM integrated over J1-J15,
but PGK production falls0.00603051mM and net NDPK consumption increases0.00226087mM.
Other responses compensate: total executed ATP production/consumption change
from4.91101443/5.84392331 to4.91147703/5.84438537mM. The ATP increment relative
to the baseline terminal state is only5.54276e-7mM. The aggregate log gain is
not physiological recovery or evidence of unique kinetic constants.

Four new original replays, two fast-parity replays, six reused original
controls. All6328 new daily balances,5600 raw and5600 executed quadrature
comparisons and76338 cross-tolerance checks pass. Checked minima0mM;
70 live rate checkpoints across all ten case/profile pairs. All55 original
J1 observations and the entire latent initialization are exact. All source
cells and historical archives are unchanged. No J46 replay, optimizer,
new active branch or production promotion.

Tables: `all55_metrics.csv` (550 case/profile/channel rows), `flux_integrals.csv`
(1000 case/profile/reaction rows in native reaction coordinates), and
`summary.json` (timewise profiles, signed budgets and interaction). Receipt
and QA: `output/vsam_pgk_screen_validation_2026_11_04/`.
The separate verifier rebuilt all550 channel rows and1000 reaction rows from
the sealed original replay arrays. `conditional_replay_candidate.json` is a
two-parameter override for a future explicit replay only.

## Next decision

Retain only the half-step as a conditional comparator, not fitted production
constants. Before widening any search, compare its free J46 replay against the
same baseline and all55 measurements, including late glucose/lactate, ATP/ADP/AMP
and executed ATP budgets. J46 has already been exposed historically, so it is
not independent validation. Structural coverage and adenylate/pool reconciliation
remain open; a local improvement below0.4% does not justify broad optimization.
