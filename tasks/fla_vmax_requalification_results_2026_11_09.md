# Historical-threshold Vmax requalification

Status: Steps 1-3 completed and independently verified. Campaign executed
2026-11-09; documentation and validation closeout resumed 2026-11-10 after
interruption. No optimization or production promotion. Do not overwrite or
rerun this campaign.

Campaign: `output/vmax_requalification_2026_11_09/`.
Protocol: `tasks/fla_vmax_requalification_protocol_2026_11_09.md`.

## Scope And Frozen Contract

The registry freezes sixteen distinct actual parameter sets: nine rejected
temporal attempts, five absolute-target attempts and two PGK/NDPK profile
points. Original log vectors, parameters, source occurrences and errors are
retained. Sources have identical observations, J1, Km, baseline parameters,
families, groups, boxes and network. No metabolic-only reject is added.

Availability stays 1e-3 mM. The optional recipe is Radau in SciPy 1.17.1,
rtol 1e-8/1e-9, atol 1e-12/1e-13 mM, max_step 0.05 day and bounded fine
finite-difference floors 1e-15/1e-16 mM. It has not become a production
default. Every replay preserves its literal archived Vmax vector; all Km,
initial states, volumes, transport choices and nontarget parameters stay
fixed. No threshold selection by fit, clipping, state repair, new parameter
proposal, J46 run or new optimization was performed.

## Step 1: Control Certification

Eight control integrations: fixed reference and last admitted
working center, full/joint backends, strict/ultrastrict profiles. The old
historical full controls remain the primary metabolic guard references;
caps are not recalculated from the new solver. All numerical,
historical-control, backend and original working-center guard certificates
passed before Step 2. The runner required an independent control receipt.

Step 1 passed all eight numerical runs, all historical/backend/profile
comparisons and the working center's original guards. Independent certificate:
`output/vmax_requalification_control_decision_2026_11_09/`:12,656 daily
balances, 44,800 quadrature values and 72 native projection checkpoints.

## Step 2: Requalification Of Old Numerical Rejects

All 32 candidate replays completed and passed the numerical gates: sixteen
existing vectors, strict and ultrastrict profiles, certified compiled
backend. Native raw/executed rate checks passed in every replay. All sixteen
paired-profile comparisons passed. The eight controls plus these 32 replays
are the complete forty-integration campaign; no fit-based retries were added.

All saved accepted, dense and order-4/order-8 quadrature concentration
supports are finite and nonnegative in this campaign. The recorded global
minimum is 0 mM (EINO at J1). Across all retained supports and forty replays,
the minima are ATP 8.34204322e-5 mM, ADP 9.37553020e-7 mM and AMP
0.738912901 mM. The policy remains -1e-10 mM; this support-based evidence
does not prove exact continuous-time positivity or a threshold plateau.

## Step 3: Independent Metabolic Decision

Independent receipt: `output/vmax_requalification_decision_2026_11_09/`.
The verifier reconstructed source vectors, original guard caps, safety
reserves, absolute windows, numerical comparisons and final classifications.

| Check | Result |
| --- | --- |
| Numerically valid records | 40/40 |
| Daily executed balances | 63,280/63,280 |
| Reconstructed quadrature values | 224,000 |
| Native/compiled projection checkpoints | 360 |
| Reconstructed candidate guard values | 2,688 |
| Paired candidate comparisons | 16/16 |
| Candidate numerical failures | 0/16 |
| Candidates passing original relative guards and reserve | 9/16 |
| Candidates failing metabolic guards | 7/16 |
| Candidates reaching both absolute J15 targets | 0/16 |

The nine admitted candidates, in registered order of merit, are:
candidate_13, candidate_14, candidate_12, candidate_11, candidate_10,
candidate_07, candidate_09, candidate_05, candidate_03. Admission is relative
to the historical fixed reference, not superiority over the working center.

The seven metabolic rejects are candidate_01, candidate_02, candidate_04,
candidate_06, candidate_08, candidate_15 and candidate_16. Failures include
F6P at J4/J11 (four candidates), G6P at J8 (three), PEP at J4 (two), and
additional channel/date guards detailed in `requalification.csv`. The
PGK/NDPK profile points both fail metabolic guards, despite numerical recovery.
No guard was relaxed to accept them.

`all55_by_day.csv` contains 8,800 model/observation comparison rows
(55 channels x four measured dates x forty replays), not 8,800 independent
experimental measurements. Existing aliases retain their scoring status.

## Comparison With The Working Center

No admitted recovered candidate improves either the worst-profile absolute
ATP/ADP objective or the worst dated adenylate error ratio of the working
center. Keep that center unchanged; the first recovered candidate is not
a new best model.

| Quantity | Working center | Best recovered: candidate_13 |
| --- | --- | --- |
| Original occurrence | Absolute-target attempt 76 | Absolute-target attempt 78 |
| ATP J15, ultrastrict, mM | 8.98216559e-5 | 9.09463419e-5 |
| ADP J15, ultrastrict, mM | 1.77478152e-6 | 1.63433594e-6 |
| Worst-profile absolute log-window gap, lower is better | 12.08918013 | 12.17162089 |
| Worst dated adenylate error ratio, lower is better | 0.93446340 | 0.96323536 |

Candidate_13 raises J15 ATP by 1.2521% but lowers ADP by 7.9134% relative
to the center. Its joint objective is worse. The inherited absolute J15
windows remain ATP [0.75707361, 1.27058099] mM and ADP
[0.315797812, 0.585481701] mM. These windows use the existing observation
contract; this pass neither resolves observation-pool definitions nor adds
independent biological validation. Numerical recovery has not rescued ATP.

For each pool, the absolute score is the maximum of log(lower/prediction)
and log(prediction/upper), then maximized across pools and solver profiles.
Both windows pass only when that maximum is <= 0. No pseudocount is used.
The separate dated ratio retains the original squared-log adenylate metric.

## Artifacts And Closeout

- Campaign and immutable evidence: `output/vmax_requalification_2026_11_09/`.
- Control receipt: `output/vmax_requalification_control_decision_2026_11_09/`.
- Complete receipt and classification table:
  `output/vmax_requalification_decision_2026_11_09/verification.json` and
  `output/vmax_requalification_decision_2026_11_09/requalification.csv`.
- Literal replayed capacities:
  `output/vmax_requalification_decision_2026_11_09/replayed_Vmax.csv`.
- Working-center comparison, QA and closure certificate:
  `output/vmax_requalification_validation_2026_11_09/`.

198 targeted tests passed with no failures, errors or skips. The validation
closeout verifies live pinned input hashes, the complete archive manifest,
both receipt seals, the eight/32 trace counts, the center comparison and
the unchanged scope flags. The full repository test suite was not run.

## Recommended Successor, Not Executed

Resume Vmax-only calibration in a fresh successor using this qualified
optional numerical recipe and the unchanged working center as an explicit
comparator. Keep Km, J1, observations, network, availability threshold and
original bounds fixed initially. Use the absolute ATP/ADP objective under
the same J4/J8/J11/J15 guards, including PEP/G6P/F6P/AMP, and retain the
executed-flux audits. Recompute search sensitivities with the corrected
engine rather than reusing sensitivity decisions that treated these sixteen
vectors as numerical failures. Do not promote a relative-error improvement
as absolute ATP rescue, and do not expand bounds before evaluating this
corrected-search successor. No new optimization has been launched here.
