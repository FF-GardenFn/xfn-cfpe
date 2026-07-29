# prompt-model

A prompt-design framework built on one bet: prompts are inputs to a *mechanism* — a tokenizer, an attention stack, a post-trained instruction surface — and prompt engineering improves when it reasons about that mechanism instead of cargo-culting phrasings. Whether tokenizer- and architecture-aware prompting yields measurable improvement over strong baselines is an open empirical question; the framework is built to make that question testable, not to presume the answer.

## Two layers plus probes

| Layer | Files | Role |
|-------|-------|------|
| Design | [cognitive-models.md](./cognitive-models.md), [structural-patterns.md](./structural-patterns.md), [prompt-architecture.md](./prompt-architecture.md), [generation-strategies.md](./generation-strategies.md), [validation-rubric.md](./validation-rubric.md) | How an expert *thinks* (not what they do), six structural principles, architecture and variant-generation strategy, scoring rubric |
| [mechanistic-layer/](./mechanistic-layer/) | [OVERVIEW.md](./mechanistic-layer/OVERVIEW.md) (human router), [preconditions-catalog.md](./mechanistic-layer/preconditions-catalog.md) (machine dispatch), 8 technique files, [mechanistic-foundations.md](./mechanistic-layer/mechanistic-foundations.md) | A dispatch system, not an essay: a trigger matrix decides which technique files fire for a given request; every technique carries a `## Procedure` and preconditions |
| [mechanistic-layer/probes/](./mechanistic-layer/probes/) | `mid_entropy.py`, `position_pulse.py` | Standalone heuristics: low-specificity token bands in long prompts; anchor-density per sentence |

Entry point: **`mechanistic-layer/OVERVIEW.md`** — run `model-recon.md` first (tokenizer, context window, channel hierarchy, cutoff), then walk the trigger matrix.

## Epistemic discipline

Technique files label their claims **documented / inferred / speculative**, and [references-and-evals.md](./mechanistic-layer/references-and-evals.md) plus [validation-and-integration.md](./mechanistic-layer/validation-and-integration.md) define the go/no-go check applied before a generated prompt ships. Pending augmentations and preregistered probes are tracked in [mechanistic-layer/TODO.md](./mechanistic-layer/TODO.md).

## Where it's used

- Packaged and runnable as the [`plugins/prompt-model`](../../../plugins/prompt-model/) plugin (`/write-prompt`): intake/dispatch, then translation into a fixed output contract.
- The directory map with per-file descriptions lives in [`content/README.md`](../../README.md).
- The design-layer documents are the stated foundation of the template-writer spec in [`documentation/designs/template-writer/`](../../../documentation/designs/template-writer/).
