# Experiment Log

Concise run history for the refusal-capability entanglement pilot.

## Question

Does steering against an extracted refusal direction preserve general capability, or does capability degrade as refusal behavior changes?

## Run Observations

| Run | Version | Mode | Observation |
|---|---|---|---|
| 1 | initial Experiment B | full | Steering scale was too small. Refusal rate did not move from baseline. Capability stayed near baseline. |
| 2 | B2 / v0.2-style | full | Showed an apparent refusal/capability tradeoff, but later code review found activation and intervention confounds. |
| 3 | v0.3 | calibration | Larger magnitudes reduced refusal but caused invalid behavior/incoherence. Capability skipped. |
| 4 | v0.3.3 | calibration | Answer-start intervention fixes removed collapse, but tested magnitudes were too conservative. |
| 5 | v0.3.4 | calibration | Clean refusal transition found with zero incoherence; refusal reduction reached `0.28`. Capability still skipped because run mode was calibration. |
| 6 | v0.3.5 | full | Full capability run completed. Refusal reduction reached `0.42`; capability declined with refusal reduction, especially on MMLU and ARC. |

## Current Interpretation

- H3 null is rejected: a non-null refusal direction was extracted and validated.
- H1 separability is not supported under the pinned `>50%` refusal-change criterion. There is partial low/mid-magnitude separability, for example `0.28` refusal reduction with normalized capability `0.915`.
- H2 has strong statistical support under the pinned beta/p-value criterion: slope `-0.8089`, p-value `3.96e-05`.
- The v0.3.5 script reports H2 as `not_supported` because it also requires a `0.50` refusal-change range; Run 6 reached `0.42`.
- Main caveat: high-sigma capability degradation is concentrated in multiple-choice benchmarks and shows answer-label bias. GSM8K remains stable.

## Next Work

1. Manually label `manual_refusal_labeling.csv` into true refusal, benign warning/reframe, and unsafe compliance.
2. Add answer-label randomization or answer-text scoring for MMLU and ARC to test whether degradation is mostly `A/B/C/D` token bias.
3. Add at least one non-multiple-choice knowledge/reasoning benchmark.
4. Optionally probe higher magnitudes only if the strict `>50%` refusal-reduction threshold remains important.

## Source Pointers

- Original spec: `docs/pinned_experiment_spec.md`
- Main code: `code/experiment_b_refusal_capability_entanglement_v0_3.py`
- Main notebook: `code/experiment_b_refusal_capability_entanglement_v0_3.5.ipynb`
- Final run summaries: `findings/run6_v0.3.5_full/summaries/`
- Final run plots: `findings/run6_v0.3.5_full/plots/`
- Full final run archive: `findings/run6_v0.3.5_full/archive/`
