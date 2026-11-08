# Fixed reversible VTKL2/VTAL directionality diagnostic

## Contract

- Generated: 2026-08-10T15:03:18.354483+00:00
- Horizon: `5` days.
- Seed kinetic constants held exactly fixed.
- Fixed probes: VTKL2 reversible, VTAL reversible, and both reversible.
- Reverse scale: `1.0`; hybrid blend: `1.0`; no fitted equilibrium constant.
- Diagnostic only: no optimization or parameter promotion.

## Candidate rate laws

```text
VTKL2 = vmax * [sat(E4P) sat(X5P) - sat(F6P) sat(GA3P)]
VTAL  = vmax * [sat(GA3P) sat(S7P) - sat(F6P) sat(E4P)]
```

These are reversible saturation-difference probes, not Haldane-consistent thermodynamic rate laws.

## Brodbar metrics

| Case | GLC nRMSE | G6P nRMSE | F6P nRMSE | F16BP nRMSE | ATP nRMSE | PEP nRMSE | Max closure |
|---|---:|---:|---:|---:|---:|---:|---:|
| `seed_irreversible` | 0.0770835 | 16.6236 | 6.58533 | 0.379285 | 0.757769 | 0.117155 | 3.553e-15 |
| `reversible_VTKL2` | 0.147584 | 17.5715 | 3.74086 | 0.315743 | 0.757322 | 0.154569 | 3.553e-15 |
| `reversible_VTAL` | 0.0871798 | 16.758 | 5.22294 | 0.383797 | 0.757757 | 0.117106 | 3.553e-15 |
| `reversible_both` | 0.170348 | 17.8744 | 4.07738 | 0.318202 | 0.757319 | 0.154922 | 1.776e-15 |

## Directionality and guards

- `reversible_VTKL2`: F6P nRMSE change `+43.2%` improvement; VTKL2/VTAL negative-time fractions `67.9%` / `0.0%`; guards `G6P nRMSE guard; GLC endpoint guard; GLC nRMSE guard; PEP endpoint guard; PEP nRMSE guard`.
- `reversible_VTAL`: F6P nRMSE change `+20.7%` improvement; VTKL2/VTAL negative-time fractions `0.0%` / `0.0%`; guards `none`.
- `reversible_both`: F6P nRMSE change `+38.1%` improvement; VTKL2/VTAL negative-time fractions `66.7%` / `0.0%`; guards `G6P nRMSE guard; GLC endpoint guard; GLC nRMSE guard; PEP endpoint guard; PEP nRMSE guard`.

## Decision

**`advance reversible_VTAL to a bounded fixed-blend sensitivity screen before optimization`**

reversible_VTAL improves F6P by 20.7% while passing every transfer and closure guard. The formulation remains diagnostic and is not promoted.

The irreversible seed remains the default and can be restored by omitting the kinetic-family toggles or setting both hybrid blends to zero.

No kinetic parameter file was created by this diagnostic.