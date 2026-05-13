# Project Artifacts

Three connected research projects, each instrumenting the gap between the form of model behavior and the underlying operation it claims to report. Two pre-pilot (methodology + seed-example analysis); one completed pilot run.

## Projects

| Project | Subdirectory | Focus | Status |
|---|---|---|---|
| Control provenance | [control-provenance-eval/](./control-provenance-eval/) | Cross-frame benchmark of which governance frame supplies the constraint when Claude refuses, complies, or takes action under pressure | Pre-pilot: methodology + seed-example analysis |
| Intent laundering | [intent_laundering/](./intent_laundering/) | Request-layer and refusal-layer detection of intent-laundering and refusal-rationale leakage | Pre-pilot: methodology + draft classifier + seed-example analysis |
| Refusal/capability geometry | [refusal-capability-entanglement/](./refusal-capability-entanglement/) | Activation-steering pilot testing whether refusal direction is geometrically separable from capability in Llama-3.1-8B-Instruct | Run 6 (v0.3.5_full) complete |

## Shared Artifacts

- [example_1_no_context.md](./example_1_no_context.md), [example_2_with_context.md](./example_2_with_context.md) — seed conversations grounding the control-provenance and intent-laundering projects. Verbatim model output with explicit `<user>` / `<assistant>` turn boundaries.
- [intent_laundering/classifier_prompt.md](./intent_laundering/classifier_prompt.md) — refusal-leakage classifier; used as the Surface 3 scorer in `control-provenance-eval/` and as the secondary measurement classifier in `intent_laundering/`.
- [/CAI/](../CAI/) — constitutional kernel experiment; the reference implementation for the constitutional-provenance benchmark (pointers in [control-provenance-eval/links_to_CAI_code.md](./control-provenance-eval/links_to_CAI_code.md)).

## Directory Structure

- **control-provenance-eval/** — Cross-frame provenance benchmark
  - [README.md](./control-provenance-eval/README.md) — scope, status, files
  - [methodology.md](./control-provenance-eval/methodology.md) — three scoring surfaces, factorial structure, geometric dual
  - [links_to_CAI_code.md](./control-provenance-eval/links_to_CAI_code.md) — pointers to /CAI/ implementation
  - [results_summary.md](./control-provenance-eval/results_summary.md) — hand-scored seed-example analysis
- **intent_laundering/** — Intent-laundering and refusal-leakage detection
  - [README.md](./intent_laundering/README.md) — scope, three coupled measurements, status
  - [classifier_prompt.md](./intent_laundering/classifier_prompt.md) — refusal-leakage classifier draft
  - [pilot_results.md](./intent_laundering/pilot_results.md) — preliminary observations from seed examples
  - [examples.jsonl](./intent_laundering/examples.jsonl) — schema-shaped scoring records
- **refusal-capability-entanglement/** — Activation-steering pilot
  - [README.md](./refusal-capability-entanglement/README.md) — pilot summary and current result
  - [LOG.md](./refusal-capability-entanglement/LOG.md) — run-by-run history
  - [docs/pinned_experiment_spec.md](./refusal-capability-entanglement/docs/pinned_experiment_spec.md) — pre-registered specification
  - [code/](./refusal-capability-entanglement/code/) — Python source and Jupyter notebook
  - [findings/run6_v0.3.5_full/](./refusal-capability-entanglement/findings/run6_v0.3.5_full/) — final-run summaries, plots, audit, archive
- [example_1_no_context.md](./example_1_no_context.md), [example_2_with_context.md](./example_2_with_context.md) — Seed conversations