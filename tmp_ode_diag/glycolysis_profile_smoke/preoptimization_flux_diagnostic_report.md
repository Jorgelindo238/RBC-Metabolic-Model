# Pre-optimization glycolysis flux diagnostic

## Technical summary

The 46-day Brodbar replay identifies **G6P** as the highest-ranked downstream restriction in the current `vhk_atp` hypothesis. The corresponding single-parameter probe is **`vmax_VPGI`**. This is a diagnostic recommendation, not a promoted calibration result.

Intracellular GLC changes from 1.123 to 1.838 mM while its mean inflow/outflow imbalance is 0.263. The downstream G6P pool has a restriction score of 1.728, an outlet-utilization proxy of 0.281, and a concentration change of 1.917 mM.

## The restriction appears downstream of glucose transport

The transport gate supplies enough glucose to reproduce extracellular depletion, but the internal pathway does not maintain matched throughput. The sequence of time-weighted fluxes below shows where throughput drops between glucose entry, phosphorylation, lower glycolysis, pyruvate production, and lactate export.

| Reaction | Mean flux | Early mean | Late mean | Mean abs flux / Vmax |
| --- | ---: | ---: | ---: | ---: |
| VEGLC | 0.832 | 0.832 | 0.729 | 0.402 |
| VHK | 0.613 | 0.613 | 0.074 | 0.123 |
| VPGI | 0.067 | 0.067 | 0.070 | 0.326 |
| VPFK | 0.560 | 0.560 | 0.060 | 0.220 |
| VPK | 0.298 | 0.298 | 0.042 | 0.418 |
| VLDH | 0.531 | 0.531 | 0.574 | 0.582 |
| VELAC | 0.476 | 0.476 | 0.526 | 0.276 |

## Ranked downstream hypotheses

The restriction score combines positive pool accumulation, mean inflow/outflow imbalance, and utilization of the pool's modeled outlet capacity. GLC itself is excluded from the downstream lever choice because `vmax_VHK` is already fixed at its tested global ceiling in the reference candidate.

| Pool | Single lever | Score | Imbalance fraction | Outlet utilization | Delta concentration |
| --- | --- | ---: | ---: | ---: | ---: |
| G6P | vmax_VPGI | 1.728 | 0.719 | 0.281 | 1.917 |
| P3G | vmax_VPGM | 1.592 | 0.607 | 0.842 | 1.832 |
| F6P | vmax_VPFK | 1.099 | 0.656 | 0.220 | 0.816 |
| PYR | vmax_VLDH | 0.750 | 0.577 | 0.455 | 2.979 |
| GA3P | vmax_VGAPDH | 0.698 | 0.688 | 0.043 | 5.491 |
| NADH | vmax_VLDH | 0.239 | 0.345 | 0.582 | 0.899 |

## Scope and definitions

- Dataset and horizon: Brodbar, day 1 through day 5.
- Reference hypothesis: `vhk_atp` (`VEGLC` depletion gate with `vmax_VHK = 5.0` and lowered `km_ATP_HK`).
- Flux source: native `FluxTracker` replay of `equadiff_brodbar`, with `curve_fit_strength = 0.0`.
- Flux units: mM per model-time unit. The Brodbar replay time axis is interpreted as days; legacy ODE comments still contain hour labels.
- Restriction score: descriptive ranking only. It does not prove parameter identifiability or causal control.

## Methodology and robustness checks

Each saved parameter set was reinjected into the pure ODE and solved on the same 46-day grid. Fluxes were then recomputed from every solved state by the same ODE function used during integration. For each glycolytic pool, signed reaction contributions were reconciled against the ODE derivative.

The largest mean absolute balance residual was `0.002441`. Small residuals validate the bookkeeping; residuals near depleted pools can also reflect the model's non-negativity damping.

Selected kinetic factors in the reference replay:

- VHK ATP factor, late mean: `0.015`.
- VPGI G6P factor, late mean: `0.341`.
- VPK PEP factor, late mean: `0.113`.
- VPK ATP-inhibition factor, late mean: `0.999`.
- VLDH NADH/NAD factor, late mean: `0.671`.

## Limitations and uncertainty

The score is based on one simulated trajectory and local kinetic occupancy. It does not account for correlated parameter changes, formal control coefficients, or uncertainty in intracellular Brodbar measurements. A high score can therefore indicate a missing reaction, incorrect stoichiometry, or cofactor coupling rather than only an underestimated Vmax.

## Recommended next step

Run a narrow, reversible sensitivity probe on **`vmax_VPGI` only**, while keeping the mild `VEGLC` feedback structure and `VHK/km_ATP_HK` fixed. Preserve hard guards on the `EGLC` endpoint and slope, `VEGLC` teacher flux, and the `GLC`, `LAC`, `ELAC`, `VELAC`, and `VLDH` trajectories. Do not promote the result until a full Brodbar-panel replay passes.

## Further questions

- Does the selected lever reduce GLC without merely transferring accumulation to the next glycolytic pool?
- Does ATP recovery explain any improvement in VHK throughput?
- Is the intracellular LAC deficit caused by VLDH redox drive, excessive VELAC export, or a missing lactate-retention mechanism?
