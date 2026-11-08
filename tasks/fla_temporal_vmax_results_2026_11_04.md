# Multi-date Vmax calibration: Bordbar J4/J8/J11/J15

## Comparison and decision

The candidate is numerically admissible under the registered temporal guards.
It is not a biological calibration and is not promoted to the working defaults.
The same-network control is the fixed half-step reference in the opt-in
`redox_gssg_abc` RBC-GEM context. No new network corrections were introduced.
All Km, non-target parameters, Sheet1 J1 values, latent initialization, OPLAH,
transport, geometry, and positivity settings were locked.

The 14 groups cover 17 Vmax. Actual observations at J4/J8/J11/J15 enter a
minimax objective: the largest same-date ratio of candidate to reference mean
squared log error over ATP, ADP and AMP. J1 initializes the free ODE and does
not enter the loss. J46 was neither fitted nor replayed; the four dates are
fitting dates, not independent validation. No flux teacher, reinitialization,
or ATP injection was used.

PEP, G6P, F6P and AMP each have an absolute residual cap at each fit date:
`sqrt(reference_error^2 + 0.01*(band^2 + reference_error^2))`, with a
numerical allowance for zero-band points. The band is 5% of the median
across J1/J4/J8/J11/J15 plus 20% of the nominal observation at that date.
These are engineering guards, not measurement uncertainties. The inherited
canonical metabolite and individual adenylate guards remain in force, with
alias handling described in the protocol.

## Search and original-rate replay

Four bounded finite-difference rounds and backtracking produced 80 actual
J1-J15 fit attempts: 71 numerically valid and nine rejected for negative or
nonfinite checked states. Trial 78 was selected. The final full step had a
better numerical objective (0.96037 versus 0.97185) but violated the PEP J15
cap, F6P J8/J15 caps and B23PG/SER trajectory guards. The half step still
violated PEP J15. The quarter step was accepted. The first campaign attempt
stopped at baseline JSON serialization; its partial archive is preserved.
The successful successor changed only serialization and its regression test.

Matched strict and ultrastrict original-rate free replays of the reference
and candidate passed all guards, with gain above 0.1% at each date. The
ultrastrict results below use the same measurement support as the objective.

| Day | Adenylate log-error reduction | ATP nominal (mM) | ATP reference (mM) | ATP candidate (mM) |
| --- | ---: | ---: | ---: | ---: |
| J4 | 2.816% | 1.079765 | 0.02366774 | 0.02433763 |
| J8 | 3.148% | 1.272527 | 0.00032000 | 0.00033693 |
| J11 | 2.900% | 1.302859 | 0.00014419 | 0.00015129 |
| J15 | 3.078% | 1.013827 | 0.00008342 | 0.00008751 |

ATP and ADP still collapse. At J15, candidate ADP is 0.000001233 mM versus
0.450640 nominal, and AMP is 1.865333 mM versus 0.258136 nominal. Executed
J8-J15 ATP production/consumption are 0.00555241/0.00580183 mM, leaving a
net deficit of 0.00024942 mM (reference deficit 0.00023658 mM).
The dated objective prevents an early gain from hiding a relative regression
at another fit date; relative improvement alone does not imply acceptable
absolute ATP/ADP. This local search does not establish global infeasibility.

## Verification and artifacts

- `output/temporal_vmax_2026_11_04_v2/`: frozen search, four original replays,
  76,964 passing cross-tolerance checks, and 440 rows for all 55 representations.
- `output/temporal_vmax_decision_2026_11_04/`: absolute Vmax export, signed
  executed ATP/H budgets, and independent verification of 71 fit scores,
  32 critical caps, 6,328 balances, 22,400 quadratures, and 36 rate checkpoints.
- `output/temporal_vmax_validation_2026_11_04/`: 82 passing targeted tests,
  source snapshot of the aborted baseline, and closeout hashes.

Before allocating a larger budget to Vmax alone, test whether an explicit
absolute late ATP/ADP target can be approached inside these guard limits.
Keep that feasibility test separate from the present relative improvement
and retain the fixed same-network control.
