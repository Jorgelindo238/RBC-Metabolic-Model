# Diagnostic ATP/ADP/redox controls before FLA optimization

- Generated: 2026-08-05T02:38:26.149484+00:00
- Replay horizon: 2 days
- Reference candidate: `mild_seed`
- Diagnostic only: no Optuna optimization, parameter promotion, or overwrite.

## Method

The saved parameter sets were replayed through the native ODE and `FluxTracker`. The factors below are reconstructed from the same terms used in `equadiff_brodbar`: substrate occupancy, ATP substrate occupancy, ADP/ATP drive, PK ATP inhibition, PK product inhibition, and LDH NADH/NAD drive. The late window is days 40-46.

The ATP balance is decomposed as:

`dATP/dt = (VPGK + VPK + VAK) - (VHK + VPFK + VAK2 + VGLNS + VGLUCYS + VGSS + VSAM + VRKa + VPRPPASe + VGMPS + VGMPK + VNDPK + VOPLAH)`. 

## Reference findings

- ATP endpoint: `0.0311229` mM; late mean: `nan` mM.
- NADH endpoint: `1.91744` mM; late mean: `nan` mM.
- Strongest late control limitation by factor score: `km_ATP_HK` with factor `nan` and suggested direction `do not open km_ATP_HK`.

| Parameter | Native factor | Late factor | Endpoint factor | Suggested direction |
|---|---|---:|---:|---|
| `km_ATP_HK` | `VHK_ATP_occupancy` | nan | 0.34101 | do not open km_ATP_HK |
| `km_ATP_PFK` | `VPFK_ATP_occupancy` | nan | 0.485169 | do not open km_ATP_PFK |
| `ki_ATP_PK` | `VPK_ATP_inhibition` | nan | 0.982339 | do not open |
| `km_NADH_NAD` | `VLDH_NADH_NAD_drive` | nan | 0.716612 | do not open km_NADH_NAD |

## Decision before optimization

A factor below 0.25 is treated as a strong local restriction. The next FLA pass should open only the highest-ranked biologically interpretable lever from the reference table, while keeping the alternative controls fixed. If the top result is an ATP occupancy factor, the pass must retain PEP/G6P and ATP guards because increasing ATP affinity can increase ATP demand before it restores throughput. If the LDH redox factor is also low, it is recorded as a coupled diagnostic risk rather than opened simultaneously.

Required non-inferiority guards for the next pass: `EGLC`, `GLC`, `LAC`, `ELAC`, `ATP`, `PEP`, `G6P`, `VEGLC`, `VELAC`, `VLDH`, plus the full 55-metabolite Brodbar panel.

## Artifacts

- `energy_redox_control_profile.png`
- `energy_redox_late_controls.png`
- `energy_redox_timeseries.csv`
- `energy_redox_summary.csv`
- `energy_redox_control_ranking.csv`
