# Fixed-parameter reaction-consistent threshold sensitivity

## Decision

No registered threshold plateau was established. No threshold is promoted,
selected by fit, or installed as a new default. Lowering the availability
threshold did not rescue the ATP/ADP targets in the completed replays.
The same Vmax, every Km, exact measured and latent J1, network, phase
volumes, transport, pH and source cells were kept fixed throughout.

Protocol: `tasks/fla_reaction_threshold_protocol_2026_11_07.md`.
Campaign: `output/reaction_threshold_sensitivity_2026_11_07/`.
Independent receipt: `output/reaction_threshold_decision_2026_11_07/`.

## Execution and solver validity

The registered thresholds were 1e-3, 1e-4, 1e-5 and 1e-6 mM. Six new
original-rate J1-J15 replays were attempted (three lower thresholds at
strict/ultrastrict settings); the two center replays at 1e-3 were reused
after hash and source checks. The fixed historical control at 1e-3 is
used only for diagnostic biological guards, not numerical selection.

| Threshold (mM) | Strict | Ultrastrict | Paired solver decision |
| ---: | --- | --- | --- |
| 1e-3 | Pass, reused | Pass, reused | Pass |
| 1e-4 | Pass | Pass | Pass |
| 1e-5 | Concentration check failed | Pass within negative tolerance | Not validated |
| 1e-6 | Concentration check failed | Concentration check failed | Not validated |

The three failed replays stop with the inherited error "negative or
nonfinite checked concentration". The helper does not save their failed
states, so these receipts alone cannot identify the offending species or
distinguish a negative value from a nonfinite one. No retry, clipping,
pseudocount, looser negative tolerance or extra ODE simulation was used.

For the five complete replays (three new plus two reused), all 7,910 daily
balances pass, as do the raw/executed quadrature checks. Independent
reconstruction verifies 28,000 quadrature values, 45 native rate checkpoints,
420 diagnostic guard values, 1,100 dated source/prediction pairs and 75
sampled availability rows. There are 115 passing targeted tests.

## Actual ATP/ADP trajectories

The values below are the ultrastrict original-rate predictions at J15.
The 1e-5 values are provisional: no complete strict counterpart exists.

| Threshold (mM) | ATP J15 (mM) | ADP J15 (mM) |
| ---: | ---: | ---: |
| 1e-3 | 0.0000898217 | 0.00000177478 |
| 1e-4 | 0.0000105762 | 0.0000000383872 |
| 1e-5, provisional | 0.00000137984 | 0.00000000152338 |
| 1e-6 | No validated prediction | No validated prediction |

Nominal J15 ATP/ADP remain 1.0138273/0.45063976 mM. The two-sided working
target intervals remain 0.75707-1.27058 and 0.31580-0.58548 mM; they are
engineering intervals, not assay SD. None of the completed predictions
reaches these targets. At the paired-valid 1e-4 threshold, ATP falls about
8.5-fold and ADP about 46-fold relative to 1e-3. Diagnostic guards on late
adenylates, G6P J8, F6P J11 and XAN also fail relative to the unchanged
historical control. Better fitting did not select a threshold.

## Numerical sensitivity versus biological interpretation

The 1e-3 to 1e-4 change fails the inherited state/raw/executed comparison
contract at BOTH solver tolerances. The additional nucleotide and daily
executed-integral tests also fail. The available ultrastrict 1e-4 to 1e-5
comparison fails as well. The final two adjacent pairs therefore cannot
establish a plateau, independently of the failures at low thresholds.

Focused numerical tests were fixed before execution: atol=1e-10 mM and
rtol=1% for ATP/ADP/AMP/GDP/GTP/GMP at J4/J8/J11/J15; atol=1e-8 mM and
rtol=1% for every daily executed reaction integral. The inherited all-state
checks at atol=1e-5 mM/rtol=1% remain in place. No average hides individual
pool/date failures. GDP/GTP are numerical latent states, not observations.

At 1e-4 the PGK J15 availability factor is 0.0003838724, versus
0.0017747815 at 1e-3. ADP falls more rapidly than the threshold, so reducing
the threshold does NOT release the late PGK flux along the new trajectory.
The large same-state raw/executed gap in the previous audit was therefore
not evidence that a smaller gate would restore ATP. No unlimited-ODE
prediction was made.

On J8-J15, executed ATP production/consumption at 1e-4 are
0.00581777/0.00597809 mM (net -0.00016032 mM). The provisional 1e-5
ultrastrict values are 0.00852813/0.00873277 mM (net -0.00020464 mM).
Late ATP balance remains negative in both completed lower-threshold cases.

## Positivity limits and handoff

The inherited negative tolerance is -1e-10 mM. All saved accepted/dense
concentrations at 1e-3 and 1e-4 have minima of zero. The completed 1e-5
ultrastrict replay has a recorded checked minimum of -3.84542e-11 mM,
within that tolerance. Its saved accepted states contain O2=-3.81013e-11
mM near J13.19, and the saved dense grid contains a similarly tiny negative
O2 value. This is not strict mathematical nonnegativity. ATP and ADP remain
positive on the saved supports of that replay. The failed simulations do
not provide enough saved information to make the same claim for them.

Accepted/dense minima are exported separately in
`output/reaction_threshold_validation_2026_11_07/completed_concentration_minima.csv`.
This extraction adds no new simulation and does not identify the unsaved
quadrature minimum's species.

Next task: instrument the failed concentration checks so a successor retains
species, time, minimum, accepted/dense support and solver diagnostics without
accepting failed trajectories. Then assess low-threshold solver resolution
and positivity before any new Vmax calibration. Do not infer from this
audit that the gate alone explains the energy deficit, or tune it to the
observations. No J46 continuation or production promotion occurred.
