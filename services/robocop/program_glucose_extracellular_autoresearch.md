# Glucose Extracellular Autoresearch Program

## Goal
Learn a CPU-friendly student kinetics for `VEGLC` that tracks the teacher flux derived from experimental `EGLC`, then keep it only if the replayed ODE improves the extracellular glucose curve over the promoted hybrid seed.

## Scope
- Primary target: `EGLC`
- Primary reaction: `VEGLC`
- Fixed seed:
  - `C:\Users\Jorgelindo\Desktop\Mario_RBC_up\Simulations\brodbar\calibration\hybrid_teacher_flux_global_seed_promoted\best_params.json`
- CPU only

## Loop
1. Build an `EGLC` teacher-flux dataset from experimental data.
2. Override `VEGLC` with the teacher flux in the ODE to recover aligned states and teacher reaction flux.
3. Fit a small family catalog on CPU with a fixed budget per family.
4. Replay only executable student candidates in the full ODE.
5. Keep a candidate only if the replayed `EGLC` curve beats the promoted seed on ODE `EGLC nRMSE`.

## Candidate families
- `mm_bidirectional`
- `hybrid_asymmetric_transport`
- `transport_depletion_gate`

## Ranking
1. `EGLC` ODE nRMSE against experiment
2. `EGLC` final absolute error against experiment
3. teacher-flux nRMSE

## Hard rejection rules
- Reject if replayed `EGLC` ODE nRMSE is worse than the promoted seed
- Reject if final `EGLC` absolute error is worse than the promoted seed
- Reject if the candidate is not executable in the ODE

## Current entry point
- `C:\Users\Jorgelindo\Desktop\Mario_RBC_up\src\teacher_flux_autoresearch_glucose.py`
