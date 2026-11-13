# Purine/ribose/ATP audit: results and handoff

Completed 2026-11-11 following the glucose-carbon audit. Post hoc,
read-only accounting on five sealed cases, strict and ultrastrict, J1-J15.
No ODE integration, calibration, changed initial state, changed kinetic
constant, network correction or promotion. Historical archives untouched.

## Main result

The apparent nucleoside carbon input is largely an adenosine-to-inosine
flow, partly supplied by an unmeasured extracellular adenosine stock. Most
of the resulting pentose supply accumulates in R5P rather than demonstrably
feeding glycolysis. Increased ATP availability also sustains PRPP synthesis
and ADSS demand, while ADESUC accumulates. This is not evidence that the
whole purine nucleotide cycle completes at the ADSS rate.

The examined reactions agree with the pinned GEM after explicit projection
of unmodeled currency species. The audit does NOT identify a missing ATP
coefficient that would justify editing the ODE. Directionality, phosphate
availability and initial pool provenance remain distinct unresolved issues.

## Sources and units

- Reuse the ten trajectories and source hashes of
  `output/glucose_carbon_audit_2026_11_11/`; check hashes again before analysis.
- All cases must have `numerical_pass=true`; use saved executed rates and
  order-eight quadrature, not raw enzyme rates or a new replay.
- H=0.58; Vi=0.58 and Ve=0.42 L/L bag, fixed borrowed geometry, not a
  matched Bordbar donor measurement. Intracellular and extracellular mM
  are converted separately to mmol/L bag.
- Windows J1-J4, J4-J8, J8-J11, J11-J15 and J1-J15. Levels at all five dates.
- GEM 1.3.0 from commit `43fd381d9eb8a8a4079629012362312960e1c009`:
  `output/rbc_gem_network_audit_2026_10_06/github/1.3.0/model/RBC-GEM.json`.
  Its hash matches the saved download receipt, which records Git-blob
  verification. No remote update is mixed into this comparison.

## 1. Initial inventory and local source terms

Control J1-J15, ultrastrict, mmol/L bag:

| Inosine account | Amount |
| --- | ---: |
| Initial intracellular INO | 0.001749 |
| ADA production from ADO | +1.614411 |
| IMP nucleotidase production | +0.196395 |
| Net extracellular INO export | -0.001942 |
| PNPase consumption toward HYPX + R1P | -1.809633 |
| Intracellular INO change | -0.000770 |

There is net INO export, not a net extracellular INO supply.

The upstream ADO account is equally important:

| Adenosine account | Amount |
| --- | ---: |
| Initial intracellular ADO | 0.580000 |
| Net ADO import from extracellular stock | +0.419900 |
| AHCY production from SAH | +0.673815 |
| ADA consumption | -1.614411 |
| Adenosine kinase consumption | -0.059208 |
| Intracellular ADO change | -0.579903 |

Extracellular ADO starts at 0.420000 mmol/L bag (1 mM in its own phase)
and is almost exhausted. ADO, EADO, RIB, R1P, PRPP, ADESUC, GTP, GDP and
R5P are absent from the archived observation channels. This establishes
their lack of direct measurement in THIS calibration panel, not absence
from all published experiments. Several start at exactly 1 mM; the current
loader has a generic 1 mM fallback, but matching a value to that fallback
alone is not a complete provenance reconstruction for each archived state.
R5P starts at 1.6111 mM, not 1 mM; do not overwrite it with a generic value.

AHCY supply may mix initial SAH/ADOMET and ongoing methionine-cycle turnover.
It is not classified here as exclusively initial carbon or de novo carbon.
Likewise, the net imported ADO amount cannot be assigned molecule-by-molecule
to later INO, lactate or ATP without an additional source-tracing model.

## 2. Pentose supply is predominantly retained in R5P

Control J1-J15, mmol/L bag:

| R5P account | Amount |
| --- | ---: |
| Initial R5P | 0.934433 |
| R1P -> R5P | +2.325310 |
| Free ribose phosphorylation | +0.579976 |
| RU5P -> R5P | +0.643064 |
| PRPPASe withdrawal | -0.456334 |
| Net TKL1 withdrawal | -0.293663 |
| R5P accumulation | +2.798354 |

About 79% of the summed positive source extents into R5P appears as net
R5P accumulation. This is an inventory/throughput ratio, not a traced
fraction. R5P reaches about 6.436 mM at J15. The previous +9.048 mmol carbon/L
bag attributed to PNPase is entry into an OPEN subsystem; it must not be
equated to carbon delivery to lactate.

Free RIB begins at 0.580 mmol/L bag and is essentially consumed by J4,
costing 0.580 mmol ATP/L bag. Initial ATP is 0.541 mmol/L bag. This compares
inventory to a cumulative expense, not an impossibility proof: ATP is also
regenerated during the interval.

## 3. Initial PRPP and continued synthesis both feed salvage

Control J1-J15:

    PRPP consumed by HGPRT1 + HGPRT2 = 0.860247 + 0.176074 = 1.036321
    PRPP newly synthesized          = 0.456334
    PRPP inventory decrease        = 0.579987

Thus more than half the net salvage PRPP withdrawal is balanced by depletion
of the initial PRPP inventory. This is a balance decomposition, not a unique
molecular routing. IMP also receives 0.957027 mmol/L bag from AMP deamination;
HGPRT alone is not the full supply to ADSS.

## 4. ATP and guanylate demand

J1-J15, ultrastrict, mmol/L bag:

| Quantity | Control | AK only | AK + PEPase floor |
| --- | ---: | ---: | ---: |
| ATP -> ADP via ribokinase | 0.5800 | 0.5800 | 0.5800 |
| ATP -> AMP via PRPPASe | 0.4563 | 0.8054 | 1.0139 |
| Net ATP -> ADP via NDPK | 1.2386 | 1.9131 | 1.9650 |
| GTP -> GDP via ADSS | 1.1694 | 1.3676 | 1.5317 |
| GTP inventory increase | 0.0692 | 0.5454 | 0.4332 |
| ADSL extent toward AMP | 0.3942 | 0.3947 | 0.3954 |
| ADESUC accumulation | 0.7751 | 0.9729 | 1.1363 |

Exact identities checked separately:

    integral(NDPK) = integral(ADSS) + delta(GTP)
    delta(ADESUC) = integral(ADSS) - integral(ADSL)

ADSS does not consume ATP directly: do NOT add its GTP cost to the NDPK
ATP cost as another ATP molecule. PRPPASe consumes one ATP molecule but
two phosphoryl-bond equivalents in the bookkeeping convention ATP=2,
ADP=1, AMP=0. These equivalents are not thermodynamic free energies.

The three net ATP expenses RK+PRPPS+NDPK total 2.2749, 3.2984 and 3.5588
mmol/L bag. Control spends 2.1368 of its 2.2749 already on J1-J4.
On J1-J4, NDPK=1.1115 splits into ADSS=0.6276 and GTP charging=0.4839.
Later, some GTP storage is consumed, explaining why J1-J15 charging is
smaller. Aggregating only J15 would conceal this early demand.

The coupled arm's ADSL extent barely changes while ADSS and PRPPASe grow.
This supports a demand/retention diagnosis, not a successful completed
purine cycle or a demonstrated ATP rescue from suppressing one reaction.

## 5. Comparison with pinned RBC-GEM

All 12 tested projections match the archived executed matrix after undoing
phase scaling. Eleven match single reactions; GMP breakdown matches the
sum NTDGMP + PUNP3 with its guanosine intermediate canceled.

| ODE | GEM | Remaining qualification |
| --- | --- | --- |
| VPNPase1 | PUNP5 | GEM reversible; ODE forward-only; Pi omitted |
| VRKb | PPM | GEM reversible; ODE forward-only |
| VRKa | RBK | Forward projection agrees |
| VPRPPASe | PRPPS | ATP -> AMP agrees; proton omitted |
| VHGPRT1 / VHGPRT2 | HXPRT / GUAPRT | Forward projection agrees; PPi omitted |
| Vnucleo2 | NTDIMP | Forward projection agrees; H2O/Pi omitted |
| VADSS | ADSS | GTP cost agrees; H/Pi omitted |
| VADSL | ADSL1 | GEM reversible; ODE forward-only |
| VNDPK | NDPK1 | GEM forward-bounded; native ODE signed/reversible |
| VEINO | INSt | Reversible transport projection agrees |
| Vnucleo_GMP | NTDGMP + PUNP3 | Lumped path, not a single enzyme capacity |

No Pi/PPi states are reconstructed by this comparison. Agreement after
omission is not a phosphate mass-balance proof. Do not blindly transfer
GEM bounds into kinetic directionality or introduce reverse rate constants
without an explicit thermodynamic/observation contract.

## Validation

- 1,000 pool/window balances: maximum error 7.462e-11 mmol/L bag.
- 400 identities with explicitly written reaction sums: maximum error
  7.428e-11, independent of the matrix-derived ledger coefficients.
- Separate verifier: 4,500 signed ledger rows, 1,000 pool closures,
  150 INO/GTP/ADESUC linkages, 1,000 source levels (exact agreement).
- 68 targeted tests pass, including 12 new tests. Full repository suite
  not run. Source manifests and runner/verifier hashes are retained.
- No ultimate carbon lineage, physiological validation, new source workbook
  interpretation, calibration or production promotion is claimed.

Artifacts: `output/purine_ribose_audit_2026_11_11/` and
`output/purine_ribose_verification_2026_11_11/`. Code:
`scripts/audit_purine_ribose.py`, `scripts/verify_purine_ribose_audit.py`.

## Next gate

Prioritize an explicit latent-inventory contract for ADO/EADO and RIB/PRPP:
record measured versus convention-derived values, available source bounds,
and which stocks can be varied in a reversible sensitivity experiment.
Measured J1 values remain immutable. In particular, do not silently set
unmeasured extracellular ADO to zero and call that a biological correction.

Then distinguish an initial-stock sensitivity from a Vmax-only demand-side
experiment. Predeclare both the early J1-J4 ATP expense and J15 ATP/ADP
targets, original 55-pool guards and PEP/G6P/F6P/AMP datewise constraints.
The November 10 search already included PRPPASe sensitivity: merely widening
the same search is not a new mechanistic test. Any ADSS/ADSL intervention
must account for GTP storage and ADESUC retention, not just ATP gain.

This audit supplies the quantities needed to register that test, but does
not authorize arbitrary latent pools, new Km, a wider box or reaction deletion.
Keep the existing center, all measured J1 values, OPLAH and historical
comparators. No additional simulation has been launched.
