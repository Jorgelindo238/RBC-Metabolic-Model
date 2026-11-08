# Reversible B13PG(0)-only initialization screen

## Contract

- Only `B13PG(0)` varied; B23PG(0), all other states, and all kinetic constants were locked.
- The retained `vmax_V6PGD = 9.0` balanced PPP context was used throughout.
- The duplicated `3.584045 mM` value was preserved as an explicit revert branch.
- No optimization, parameter promotion, or initial-state promotion was performed.

## J1 root

- Duplicated-data B13PG(0): `3.58404521 mM`.
- Exact J1 quasi-steady root: `0.000176677669 mM`.
- Root/duplicated ratio: `4.92956e-05`.
- Effective derivative at root: `-6.346e-15 mM/day`.

## J1-J3 screen

| Case | B13PG(0) | J1 derivative | Stock drainage | VPGK ATP | ATP nRMSE | B23PG nRMSE | Guard |
|---|---:|---:|---:|---:|---:|---:|---|
| `duplicated_data_revert` | 3.58405 | -32.464 | 3.5976 | 3.795 | 0.75688 | 0.05626 | revert |
| `qss_0.250x` | 4.41694e-05 | 1.4931 | 0.0037274 | 0.60529 | 0.91674 | 0.12663 | False |
| `qss_0.500x` | 8.83388e-05 | 0.98041 | 0.0026311 | 0.60425 | 0.91682 | 0.12665 | False |
| `qss_1.000x` | 0.000176678 | -6.3455e-15 | 0.0066472 | 0.60803 | 0.91673 | 0.12663 | False |
| `qss_2.000x` | 0.000353355 | -0.63535 | 0.00932 | 0.61061 | 0.91679 | 0.12665 | False |
| `qss_4.000x` | 0.000706711 | -3.4322 | 0.025826 | 0.6266 | 0.91643 | 0.12656 | False |
| `qss_8.000x` | 0.00141342 | -9.4489 | 0.029392 | 0.62978 | 0.91673 | 0.12663 | False |

## J1-J10 transfer

No candidate qualified for J1-J10 transfer.

## Decision

**`no guarded B13PG-only initialization found`**

No root-derived state simultaneously closed the balances, preserved B23PG, and removed the duplicated-stock pulse. B13PG initialization cannot yet be separated safely.

Next: expand the fixed-state B13PG feasibility bounds without changing kinetics.

No kinetic constant or initial condition was promoted.