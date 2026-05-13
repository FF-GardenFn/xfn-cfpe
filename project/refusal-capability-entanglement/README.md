# Refusal-Capability Entanglement

Pilot study of whether an open-weights LLM refusal direction is geometrically separable from general capability, or whether anti-refusal steering also degrades benchmark performance.

This directory contains: code, notebook, pinned spec, selected final-run outputs, plots, and a concise run log.

## Contents

```text
code/
  experiment_b_refusal_capability_entanglement_v0_3.py
  experiment_b_refusal_capability_entanglement_v0_3.5.ipynb

docs/
  pinned_experiment_spec.md

findings/
  README.md
  run6_v0.3.5_full/
    summaries/
    plots/
    audit/
    archive/

LOG.md
README.md
```

## Current Result

Run 6, `v0.3.5_full`, is the main result.

- Model: `meta-llama/Llama-3.1-8B-Instruct`
- Chosen layer: `16`
- Baseline coherent refusal rate: `1.00`
- Max valid refusal reduction: `0.42`
- Baseline mean capability: `0.765`
- Minimum normalized capability: `0.588`
- Regression slope of capability on refusal reduction: `-0.8089`
- Regression p-value: `3.96e-05`
- Bootstrap slope CI: `[-1.0947, -0.4204]`

Interpretation: the extracted refusal direction is real and behaviorally active. Low and moderate steering show partial separability, but stronger steering creates a clear tradeoff in measured capability. The high-sigma capability degradation is concentrated in MMLU and ARC multiple-choice behavior, while GSM8K remains stable — consistent with answer-label-bias on the MCQ readout pathway rather than reasoning damage. Manual audit of degenerate MCQ outputs is the next interpretive step.

## How To Use

Open the notebook in `code/` for Colab-style execution. The Python source is split with `#%%` cells so it can be converted to a notebook.

Primary final-run artifacts are in:

`findings/run6_v0.3.5_full/`

The full zipped run is preserved in:

`findings/run6_v0.3.5_full/archive/`

## Notes

This package intentionally does not duplicate every extracted raw row-level log. The archive zip is included for exact recovery, while the extracted project copy keeps only the files needed for quick review and next-step analysis.
