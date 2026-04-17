# Shared Contracts Boundary

This package mirrors the stable Python-side interfaces and the draft Supabase product model without reimplementing scientific logic.

Current responsibility areas:

- calibration job inputs
- completed run manifests
- run registry records
- `calibration_runs` row projection
- draft Supabase SQL for product/workspace/session foundations, including durable active-workspace preference

For the RoBoCop product plane, this package is the contract-first seam between:

- bounded Python execution and artifact persistence
- Supabase-backed product identity and workspace context
- future Next.js and service consumers that need stable row and session contracts
