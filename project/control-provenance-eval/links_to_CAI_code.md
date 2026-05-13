# Links to CAI Code

*Specific files in `/CAI/` that the constitutional-provenance benchmark transfers, extends, or builds on directly.*

## Implementation

- `/CAI/experiment/runner.py` — main experimental loop. Intent-aware logic integrated 2026-04-27 to reduce the text-pattern false positives that surfaced as the 19.7% rescore correction.
- `/CAI/kernel/validator.py` — Surface 1 (action) scorer. Validates whether the model's tool calls satisfy the action grammar of the forbidden task.
- `/CAI/classifier/intent.py` — Surface 2 (text) scorer. Haiku-based classifier that distinguishes refusal from compliance at the text level. Architecture transfers directly to Surface 3 with a different prompt and held-out target model.
- `/CAI/analysis/metrics.py` — `rescore_with_intent_fix()` is the methodological template for retroactive correction when a scoring instrument is found to have producer-bias. Same pattern would apply to any future Surface 3 calibration finding.

## Results

- `/CAI/results/experiment_v4_results.json` — uncorrected v4 results (preserved for forensic reference; do not cite).
- `/CAI/results/experiment_v4_corrected.json` — corrected v4 results (rescored 2026-04-27 via `rescore_with_intent_fix()`). Authoritative.
- `/CAI/results.md` — post-correction summary doc. Concise; the citable artifact.
- `/CAI/status.md` — granular log of runs, regressions, and methodological notes.

## Headline numbers (post-correction)

Residual violation rate (Surface 1 + Surface 2 combined; Surface 3 not yet scored on the v4 set):

| Model | baseline | cai | kernel_only | cai_kernel |
|---|---:|---:|---:|---:|
| Opus | 13.7% | 5.8% | 8.9% | 2.6% |
| Sonnet | 4.2% | 5.3% | 3.2% | 2.1% |

Tool-based violations: 0/760 trials per model under either kernel condition. The strongest finding; survives correction.

Sonnet capability inversion: cai 5.3% > baseline 4.2% (+1.1pp). Direction preserved post-correction; magnitude smaller than the pre-correction estimate (+1.6pp).

Opus dual-governance reduction: 13.7% → 2.6% under cai_kernel. ~81% relative.

## What transfers vs what extends

Transfers without modification:

- Trial structure, kernel infrastructure, intent-aware scoring, rescore mechanism, factorial design.

Requires extension:

- Surface 3 scorer (new). Built by adapting `/CAI/classifier/intent.py` architecture with a held-out target model and the prompt drafted in `../intent_laundering/classifier_prompt.md`.
- Haiku tier (not in v4). Adds a third capability point.
- Frame-type labeling on factorial cells (new).
- Larger n per cell (v4 used n=5; pilot target n≥20).
