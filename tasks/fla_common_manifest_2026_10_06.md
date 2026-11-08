# Common Source, Observation And Cohort Manifest

Date: 2026-10-06. Execution: inventory only, no fusion or biological optimization.

## Deliverables

- Design: `config/fla_common_manifest.json`.
- Reproducible read-only builder and source reconstruction: `scripts/build_fla_common_manifest.py`.
- Sealed output: `output/fla_common_manifest_2026_10_06/`.
- Main report: `decision_report.md`; source/dataset/cohort registry: `registry.json`.
- Tables: `observations.csv`, `samples.csv`, `datasets.csv`, `cohorts.csv`, `relationships.csv`, `resources.csv`.
- Targeted QA: `qa/test_fla_common_manifest.py`; combined JUnit: `output/fla_common_manifest_verification_2026_10_06/qa_results.xml`.

The registry has ten source identities, eight dataset descriptors and seven cohort/risk groups. Bordbar2015, candidate storage publications and the locally labeled Sheet1 dataset are distinct entries. Issaian preprint/published versions share a study identity; atlas PMID/DOI aliases cannot create a second study. Atlas methods, sample data and participant-level overlap are still unavailable to this registry.

## Observational Coverage

| Dataset | Inventoried channels/representations | Numeric values represented | Sample records | Identified donor IDs |
|---|---:|---:|---:|---:|
| Local Sheet1 | 55 | 770 | 14 | 0 |
| Yurkovich JBC | 96 | 11886 | 372 | 0 |
| RBC-GEM S6 priority D/E | 124 (62 proteins x 2 representations) | 229152 | 1848 | 616 |
| Deep Red human F/G | 7598 (3799 proteins x 2 calibrations) | 7598 | 0 | 0 |
| Bardyn control | 98 | 490 | 5 | 0 |
| Bardyn supplemented | 98 | 490 | 5 | 0 |
| Michel | 28 | 140 | 5 | 0 |
| Population atlas | 0; metadata only | 0 | 0 | 0 |

Totals of8097 channel representations and2249 sample records are bookkeeping totals across heterogeneous grains, not counts of independent assays or biological samples. Deep Red rows are summary copy-number estimates without identified donor samples. The S6 inventory is the previously verified62-protein priority subset, not all1827 exported proteins. PTM/interactome, other-species workbook sheets and GEM network files remain resource-level evidence, not automatically quantitative kinetic observations.

## Findings And Consequences

1. Local B13PG/B23PG and P2G/P3G series are exactly identical. Preserve the values and flag analytical pool identity/lineage; do not call them independent metabolite evidence without original-source confirmation. Compartment mapping uses the explicit catalogue, not an E-prefix heuristic: E4P is intracellular.
2. JBC samples have positional replicate blocks and distinct source-cell IDs, not verified donor identities. Preserve source_day and the separately documented source_day+1 coordinate; forbid positional cross-sheet/temperature donor pairing. All11886 exported cells have consistent sample/channel/source-cell keys and complete channel coverage;182 reported zeros are retained.
3. S6 D/E have identical protein/sample keys and one shared representation group per protein; join by source sample ID, never column position. Deep Red F/G share one group per protein as alternative calibrations. Neither pair supplies two independent abundance measurements or active-enzyme concentrations.
4. Bardyn58/61 constant-one channels remain excluded as suspected placeholders, not proved missingness. Michel/Bardyn have previous exploratory exposure and are not certified pristine held-out validation. Existing historical role declarations remain archived; the new manifest adds this stricter qualification.
5. No atlas observations or donor IDs are imported. Its published abstract donor total does not establish imported coverage, storage-time trajectories or independent overlap-free validation. Absence of a relationship edge is not proof of cohort independence.

Training/validation assignment remains unassigned where donor identity and exposure are unresolved. Eventual partitioning must group all repeated days and paired conditions from a donor. No fabricated donor IDs, automatic time shifts, concentration rescaling, Vmax conversion or latent-pool initialization is performed.

## Verification

Builder checks155 distinct upstream sealed files/receipts, then174 total input hashes including model/data and supporting evidence. Inputs remain hash-identical after inventory construction. The output seal contains nine files; the seal itself is not self-hashed. Verification reconstructs all8097 channel records,2249 sample records and dataset/cohort/relationship tables from live source extracts and checks all174 input/nine output hashes.

QA:76 passed,1 skipped across the new29 manifest tests and existing external-manifest/JBC/source-metadata tests. The skipped existing JBC test requires the original supplied files in Downloads; archived byte-preserved originals and source exports remain available and hash-checked. Python3.14/Pydantic startup warning is pre-existing. The full QA suite is not rerun in this source-only pass; no ODE is executed by the new builder or verifier.

Reproduce in a fresh directory:

```powershell
python scripts/build_fla_common_manifest.py --out output/fla_common_manifest_new
python scripts/build_fla_common_manifest.py --verify output/fla_common_manifest_2026_10_06
python -m pytest qa/test_fla_common_manifest.py qa/test_external_validation_manifest.py qa/test_fla_jbc_data.py qa/test_palsson_source_metadata.py -q
```

An existing output directory is never overwritten. Verification is read-only and fails on changed inputs, outputs, source keys or permission-policy flags. This is a registry/preflight artifact, not a production calibration gate migration. Exact55 J1, historical kinetics, reaction-consistent strict reference, OPLAH policy and biological readiness remain unchanged.

## Next Execution

Resolve the observation contracts for local Sheet1 and JBC: pool identity, original concentration denominator, free/total interpretation, source time and donor pairing. Prioritize EGLC/ELAC and ATP-ADP-AMP, explicitly distinguish P2G+P3G and the B13PG/B23PG duplicate-source issue. An unresolved contract must remain blocked rather than receive a guessed normalization. In parallel, obtain atlas source tables/methods and donor/cohort linkage before defining an external holdout. Rebuild augmented FLA constraints and capacity identifiability only after these source decisions; no new optimization is authorized by this inventory.
