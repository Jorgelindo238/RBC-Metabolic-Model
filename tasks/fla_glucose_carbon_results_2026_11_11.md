# Glucose and open-subsystem carbon audit

Date: 2026-11-11. Successor to the AK/PEPase diagnostic. Read-only analysis
of archived trajectories, not a preregistered intervention. No new ODE,
optimization, initial-state change, parameter change or model promotion.
The prior `no_supported_effect` conclusion is retained within its tested box.

## Evidence and method

Five cases (control, AK only and three AK/PEPase arms), strict and
ultrastrict. Source manifests of the November 9 requalification and November
11 AK and AK/PEPase campaigns verified: 251, 43 and 43 entries. The original
AK/PEPase verifier receipt is linked to the archive manifest; its own seal
is checked by the new independent verifier. The original six-run verifier
was not rerun; its reported 9,492 balances are historical verification.

Use only saved executed rates, order-eight accepted-step quadrature,
saved concentration matrix and exact J1/J4/J8/J11/J15 states. No raw-rate
substitution. Windows: J1-J4, J4-J8, J8-J11, J11-J15 and J1-J15.

Archived geometry is H = 0.58, Vi = 0.58 and Ve = 0.42 L per L of bag.
This is explicitly borrowed geometry, NOT matched Bordbar donor evidence.
Volumes are constant; no water-fraction or sampling correction is inferred.

For concentrations c, amounts per L of bag are n = diag(V)c. For the
archived concentration matrix A and executed rates v:

    delta(n) = diag(V) A integral(v dt)
    n_glucose = 0.58 GLC + 0.42 EGLC
    n_lactate = 0.58 LAC + 0.42 ELAC
    delta(n_glucose) = -0.58 integral(VHK dt)
    delta(n_lactate) =  0.58 integral(VLDH dt)

VEGLC and VELAC cancel in amount coordinates, not in the unweighted sum of
intracellular and extracellular mM. All reported flux amounts below are
mmol per L of bag, not mmol per L of cells.

## Glucose and lactate

J1-J15, ultrastrict:

| Quantity | Control | AK only | AK + PEPase floor |
| --- | ---: | ---: | ---: |
| Glucose imported | 1.6591 | 1.7033 | 1.7075 |
| Glucose phosphorylated by HK | 0.1446 | 0.4198 | 0.3754 |
| Lactate net formation by LDH | 3.8998 | 3.9581 | 3.9525 |
| Lactate exported | 3.9476 | 3.9953 | 3.9974 |
| PGK ATP-producing extent | 1.6675 | 2.9035 | 2.1552 |
| PK ATP-producing extent | 0.6249 | 1.6946 | 3.1444 |

Conditional conversion of the observed concentrations with the SAME geometry
gives total glucose disappearance 2.1971 and net lactate accumulation 7.1281
mmol/L bag. These are inventory differences, not measured intracellular
fluxes or a biological constraint validated for a matched donor. In contrast,
the control's total glucose disappearance is only 0.1446 mmol/L bag.

Control GLC rises from 1.1233 to 3.7345 mM, against observed 1.1803 at J15.
Only about 8.7% of the imported glucose amount is matched by HK extent
(24.6% AK only, 22.0% coupled arm). This ratio is bookkeeping, not a traced
fraction of imported molecules: initial glucose is mixed with entering glucose.

## Carbon: the binary source explanation is incomplete

The declared open subsystem contains glucose, glycolytic and PPP pools,
RIB/R1P/PRPP, lactate and extracellular glucose/lactate/pyruvate. Carbon
counts are explicit in `scripts/audit_glucose_carbon.py`. Its inventory is
sum(C_i V_i c_i); each boundary contribution is C^T diag(V) A_j integral(v_j).
No whole-network elemental conservation claim is made.

Carbon inventory excluding GLC/EGLC/LAC/ELAC/EPYR:

| mmol carbon / L bag | J1 | J4 | J8 | J11 | J15 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Control | 40.871 | 37.077 | 37.010 | 36.661 | 34.100 |
| AK only | 40.871 | 37.135 | 36.822 | 36.502 | 34.062 |
| AK + PEPase floor | 40.871 | 37.170 | 35.550 | 35.405 | 33.022 |

There is net stock depletion, but substantial carbon also crosses the
subsystem boundary. Control J1-J15, mmol carbon/L bag:

- VPNPase1 contributes +9.0482 through the nucleoside/ribose branch.
- Vnucleo_GMP contributes +0.4882.
- VALATA and VME contribute +1.4275 and +0.2655 toward pyruvate.
- VHGPRT1 and VHGPRT2 remove -4.3012 and -0.8804 toward nucleotide salvage.
- V6PGD removes -1.1564 from the tracked carbon subsystem; VPHGDH -0.2745.

These are boundary extents, not traced carbon lineages. In particular,
nucleosides can come from initial pools, extracellular import or recycling.
Their ultimate source is not resolved by this audit. The earlier statement
that lactate comes primarily from B13PG/B23PG/GA3P/pentose initial stocks
is too specific: the data establish low HK throughput and depletion of a
declared inventory, not that exact source attribution.

The preserved B13PG/B23PG and P2G/P3G observation aliases still inflate the
uncertainty of the modeled stock inventory. No duplicated state was deleted,
rescaled or relabeled as an independent biological measurement.

## Verification and limits

- 300 amount/subsystem closure checks pass; maximum residual 3.8223e-10.
- Alternative summation of quadrature agrees within 1.4034e-13.
- Seven new focused tests pass (geometry, transport cancellation, signed
  windows, tamper detection). Combined with AK ratio, AK attribution and
  AK/PEPase tests: 56 tests pass. Full repository suite not run.
- Independent verifier reconstructs four-pool identities without the matrix
  and recomputes displayed flux integrals: 200 identities pass (maximum
  error 1.3298e-11), 400 integrals agree within 1.7320e-14. Receipt also
  pins the runner and verifier source hashes.
- No exact lactate-origin fraction or ATP-origin fraction is identifiable
  here. ATP-producing reaction extents are not ATP carbon-source attribution.
- No new physiology, fit success or admissibility is inferred from closure.

Artifacts: `output/glucose_carbon_audit_2026_11_11/` contains levels,
balances, fluxes, carbon stocks and reaction-boundary tables, summary and
manifest. Verification: `output/glucose_carbon_verification_2026_11_11/`.
Both are new outputs; older sealed archives are untouched.

## Next execution

Audit the coupled ribose/nucleoside/salvage budget at fixed parameters:
VPNPase1 -> R1P/R5P -> PRPPASe -> PRPP -> HGPRT/IMP -> ADSS/ADESUC.
Separate initial inventory, extracellular nucleoside import and internal
recycling, and account for ATP-to-AMP demand and guanylate charging.
Cross-check the reaction definitions against the pinned RBC-GEM evidence
before proposing any correction. This follows the newly quantified boundary
flux, rather than another isolated ATP-production capacity change.

In parallel, retain the unresolved ATP/ADP/AMP observation contract and
matched volume provenance as explicit biological gates. Do not promote a
new initial state, remove OPLAH, widen Vmax bounds, or reopen Km based on
this post hoc audit. No further execution is launched by this document.
