# Findings Directory

This directory keeps a compact copy of the final run plus the full archive for exact recovery.

## Included

`run6_v0.3.5_full/summaries/`

- Final configuration and metadata.
- Baseline refusal and capability summaries.
- Calibration, steering, and capability sweep summaries.
- Candidate selection and validity metadata.
- Projection validation and PCA-overlap summaries.
- Prompt splits and benchmark subset metadata.

These files are small and sufficient for most analysis without rerunning the model.

`run6_v0.3.5_full/plots/`

- Calibration curve.
- Tradeoff curve.
- Capability by benchmark.
- PCA overlap.
- Projection validation.

These make the result reviewable without opening the notebook.

`run6_v0.3.5_full/audit/`

- `manual_refusal_labeling.csv`

This file is included because refusal classification is the main interpretive caveat. It is small enough to keep in the project and is the next manual-labeling target.

`run6_v0.3.5_full/archive/`

- Full zipped `v0.3.5_full` run.

This preserves the raw row-level logs, per-condition CSVs, and generated artifacts without duplicating a 68 MB extracted run tree in the clean project copy.

## Not Extracted In The Project Copy

The following files exist inside `run6_v0.3.5_full/archive/` (zipped) but are not extracted into the project copy:

- `benchmark_rows.jsonl`
- `benchmark_generations.jsonl`
- per-condition `benchmark_rows_*.csv`
- per-condition `refusal_generations_*.csv`
- `manual_benchmark_labeling.csv`
- `refusal_direction_artifacts.pt`

Reason: these are useful for deep audit or rerun-from-vector work, but they are bulky or redundant for a clean review artifact. They are recoverable from the archive zip.
