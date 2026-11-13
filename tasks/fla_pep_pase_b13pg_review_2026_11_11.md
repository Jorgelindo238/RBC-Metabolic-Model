# Read-only review: VPEP_PASE and the B13PG/B23PG convention

Date 2026-11-11. Chosen by the user ("Revue PEP_PASE/B13PG") after
`tasks/fla_ak_arm_attribution_results_2026_11_11.md`. Read-only: no
integration, no archive, no parameter, state, bound or code change. Sources
read: `src/equadiff_brodbar.py`, the frozen design and working center in
`output/vmax_requalification_2026_11_09/`, Sheet1 of
`src/Data_Bordbar_et_al_exp.xlsx`, the pinned RBC-GEM 1.2.0 JSON and
`comparison_v2/network_comparison.json` in
`output/rbc_gem_network_audit_2026_10_06/`, `fla_progress_log.md`, and the
two sealed archives of today. One evaluation of the coded rate laws at the
frozen J1 state was made (rates only, as in the AK dry derivation).

Nothing here is a registered result or a biological claim. Statements
marked "outside the repository" come from general biochemistry and were not
checked against a source in this review.

## 1. VPEP_PASE

Facts:

- Law (`equadiff_brodbar.py`, line 1600):
  `VPEP_PASE = vmax_VPEP_PASE * mm(PEP, km_PEP)`, PEP -> PYR, no ADP, no
  ATP, no pH or regulatory term. Code comment: "non-specific phosphatase,
  ADP-independent". Present since the first repository import
  (commit f32626b2, 2026-04-17).
- It shares `km_PEP` with pyruvate kinase. PK is
  `vmax_VPK * f_pH * f_F16BP * 1/(1+ATP/ki_ATP) * 1/(1+PYR/ki_PYR) *
  mm(PEP, km_PEP) * mm(ADP/ATP, km_ADP_ATP)`.
- RBC-GEM: `VPEP_PASE` is one of the 13 ODE reactions with status
  `no_single_reaction_match`. In RBC-GEM 1.2.0 the cytosolic consumers of
  PEP are PYK (PKM or PKLR), reverse ENO, and three NANS sialic-acid
  synthases; PEPCK produces it. There is no PEP -> pyruvate + Pi reaction.
  VPK, VPGK, VGAPDH, VDPGM and V23DPGP are all `projected_equivalent`.
- Values:

| Parameter | Code default | Frozen base | Working center | Search box (factor on base) |
| --- | --- | --- | --- | --- |
| vmax_VPEP_PASE | 0.1 | 8.3562 | 7.6598 | PEPase [0.1, 3.0] -> 0.836 to 25.07 |
| vmax_VPK | 0.9363 | 0.5321 | 0.6566 | PK [0.25, 4.0] -> 0.133 to 2.128 |
| km_PEP (shared) | 0.175 | 1.0375 | 1.0375 | not searched |

- The phosphatase capacity is 11.7 times the PK capacity at the working
  center and 84 times its code default. Inside the registered boxes the
  phosphatase cannot go below 0.836, which is still 1.27 times PK at the
  center; the highest reachable PK/phosphatase capacity ratio is 2.55.
- Observed PEP is 0.220 mM at J1 and 0.052 at J15, well below km_PEP, so
  both reactions are first order in PEP. Raw rates at frozen J1: PK 0.900,
  VPEP_PASE 1.339 mM/day (PK share 40%, with the F16BP activation and
  ADP/ATP = 1.25). The share then depends only on the PK modifiers.
- Executed shares: 75%/95%/100% of PEP outflow on the three windows in the
  control, 64%/73%/84% in the balanced AK arm with PK not ADP-gated.
- History: 2026 summer profile found 93.3% of PEP drainage through it; a
  x0.1 probe was "the most mechanistically coherent response" but
  insufficient; a downward-only pass (0.772) and a coupled PEPase/PK pass
  (4.444) were both not promoted. The 2026-10-27 joint calibration found
  PEP "the active constraint". In the current design it has its own group.
- Provenance of the frozen base 8.3562 was not traced: the value appears
  in no file under `config/`, `src/`, `scripts/` or `Simulations/`.

Reading: the reaction is a model device without an RBC-GEM counterpart,
it carries most of the PEP at every date, and it is the route by which the
model reproduces the PEP level while forming little ATP. Lowering it has
been tried three times and was limited by PEP guards each time; none of
those trials had ADP available after J4.

## 2. B13PG(0) and the DPGM / 23DPGP pair

Facts:

- Sheet1 rows 10 (B13PG) and 11 (B23PG) are identical at all 14 dates
  (3.584 at J1, 0.600 at J15); rows 49/50 (P2G/P3G) likewise. The frozen
  design records `independent_B13PG_observation: false` and
  `preserve_all_J1_values: true`. Frozen B13PG(0) = B23PG(0) = 3.5840 mM.
- Laws: `VPGK = f_pH * vmax_VPGK * mm(B13PG, km_B13PG) * mm(ADP/ATP,
  km_ADP_ATP)`; `VDPGM = f_pH * vmax_VDPGM * mm(B13PG, km_B13PG)`;
  `V23DPGP = f_pH * vmax_V23DPGP * mm(B23PG, km_B23PG)`. PGK and DPGM share
  one `km_B13PG`.
- Values: km_B13PG 0.00284 mM (code default 1.013); vmax_VPGK 19.588
  (base 39.177, PGK factor on its lower bound 0.5); vmax_VDPGM 4.4916 and
  vmax_V23DPGP 0.7409, both outside every search group; km_B23PG absent
  from the frozen parameters, so the code default 1.013 applies.
- Raw rates at frozen J1 (mM/day): GAPDH 1.750, PGK 16.146, DPGM 4.488,
  23DPGP 0.578. Drain of B13PG 20.6 against supply 1.75: the 3.584 mM stock
  lasts a few hours, after which B13PG sits at the 1e-3 availability gate,
  below km_B13PG.
- Executed J1-J4 in the control: inflow = stock 3.584 + GAPDH 0.681;
  outflow = PGK 2.711 + DPGM 1.554. In the balanced AK arm: PGK 2.989 +
  DPGM 1.276. So about 84% of the J1-J4 B13PG throughput, and most of the
  2.7-3.0 mM ATP made by PGK, is the initial stock. From day 2 PGK makes
  0.09 mM/day.
- B23PG: observed decline 0.559 mM over J1-J4. Executed 23DPGP is 1.78 mM
  over J1-J4, so holding the observed B23PG needs about 1.2 mM of DPGM in
  three days; GAPDH supplies 0.68 in total and PGK competes for it.
- RBC-GEM: DPGM (BPGM or PGAM1, reversible) and DPGase (BPGM) match.
  Reactions absent from the executed ODE: ACYP (1,3-BPG -> 3PG without
  ATP; coded as an optional branch, inactive, no kinetics), DPG3P (MINPP1,
  2,3-BPG -> 2PG), HB23DPGB (2,3-BPG binding to deoxyhemoglobin) and the
  PGM2L1 bisphosphate synthases.
- History, 2026-08-11: the duplicated stock was already identified as the
  source of the early PGK ATP pulse. The J1 quasi-steady root was
  B13PG(0) = 1.77e-4 mM; replacing the stock by it cut J1-J3 PGK ATP from
  3.795 to 0.608 mM and failed the B23PG guard (93% of DPGM supply came
  from the stock), so the duplicated value was retained as the revert
  branch. `vmax_VDPGM` was then tripled to 4.4916 inside the QSS-B13PG
  context as a diagnostic anchor, with the decision "do not promote".
- The frozen base of the current campaigns contains that 4.4916 together
  with the duplicated 3.584 stock. How the two came to be combined was not
  traced in this review.

Outside the repository: in red cells 1,3-bisphosphoglycerate is usually
reported at sub-micromolar levels and 2,3-bisphosphoglycerate at several
millimolar; the two are isomers that untargeted mass spectrometry does not
separate. That is consistent with the August root (1.8e-4 mM) and with the
duplicated row being 2,3-BPG, but it was not verified here.

Reading: the J1 state holds 3.58 mM of an acyl phosphate that the model
turns into 2.7-3.0 mM of ATP within one day, and the same stock is what
keeps modelled B23PG near its observed curve. The early ATP dynamics that
all diagnostics since 2026-11-10 describe (NDPK, ribokinase, PRPPASe
absorbing a burst, then collapse) start from this pulse. This does not
show that the pulse causes the collapse: in August, removing it made ATP
fall earlier.

## 3. What this changes for the next step

- Both routes were known individually. What is new today is the sealed
  evidence that, once ADP stays available (balanced AK ratio), ATP
  production is still bounded by them: GAPDH supply 0.22 mM/day until J8
  and the PK share of PEP at most 36%.
- VPEP_PASE can be tested inside the registered box and inside "Vmax
  only". B13PG(0) cannot: changing it touches a Sheet1 J1 value, which the
  user decided to keep, and the August screen already showed the B23PG
  cost.
- vmax_VDPGM and vmax_V23DPGP have never been in a search group of the
  current design.

## Next step: a decision for the user, nothing launched

1. Fixed-kinetics diagnostic inside the registered boxes: balanced AK
   ratio crossed with VPEP_PASE at its lower bound (and PK unchanged),
   literal vectors as in the AK diagnostic, same guards, compensation
   criteria registered. Four to six integrations. Tests whether the PK
   share and late ATP rise once ADP is available, and what PEP does.
2. Registered Vmax-only search with AK ungrouped (design change).
3. Reopen the B13PG(0) convention as a reversible latent diagnostic in the
   current context, B23PG(0) and all other Sheet1 values untouched. This
   revisits a standing user decision and the August rejection.
4. Observation contract for Sheet1 ATP/ADP/AMP.
