# Content

Prompt, technique, and query substrate. Everything here is a pipeline *input*: system prompts executed by [`src/get_responses/`](../src/get_responses/), technique notes that govern how those prompts are constructed, and query corpora used as test material.

| Path | Contents |
|------|----------|
| [prompts/dialectica/](./prompts/dialectica/) | DIALECTICA — multi-hypothesis reasoning prompt, 6 versions |
| [prompts/XDRG/](./prompts/XDRG/) | DIALECTICA-RIGOR — derivation/verification variant, 4 versions |
| [techniques/CoV/](./techniques/CoV/) | Oscillatory Chain of Verification — the theory the prompts implement |
| [techniques/prompt-model/](./techniques/prompt-model/) | Mechanistic prompting framework; largest subtree here |
| [test-queries/](./test-queries/) | Query sets used as evaluation inputs |

## prompts/dialectica

Generate competing hypotheses, stress-test each against the others, iterate until the hypothesis space stabilizes, then synthesize. A mode ladder (BYPASS / LIGHT / FULL / ULTRATHINK / MEGATHINK) gates iteration count, hypothesis count, red-team vectors, and inversion moves per query.

| Version | Shape |
|---------|-------|
| [v0.1](./prompts/dialectica/dialectica_v0.1.md) | Identity-first layout: `<identity>`, `<protocol>`, `<confidence>`, `<epistemic-warrant>`, `<quality-gate>` |
| [v0.2](./prompts/dialectica/dialectica_v0.2.md) | Same layout plus a `<framework_definition>` block |
| [v0.3](./prompts/dialectica/dialectica_v0.3.md) | Adds `<execution_model>`: phases run in extended thinking, the user sees only the synthesized framework. Drops `<epistemic-warrant>`, `<mandatory-discounts>`, `<quality-gate>` |
| [v0.3.3](./prompts/dialectica/dialectica_v0.3.3.md) | Hoists `<mode-spec>` and `<territory>` to the head as lookup tables |
| [v0.3.6](./prompts/dialectica/dialectica_v0.3.6.md) | Same section set, incremental revision |
| [v0.3.7](./prompts/dialectica/dialectica_v0.3.7.md) | Current. Mirrored byte-for-byte into [`src/get_responses/system_prompts/dialectica.md`](../src/get_responses/system_prompts/dialectica.md) |

## prompts/XDRG

DIALECTICA-RIGOR targets derivation rather than deliberation: map the conceptual terrain (definitions, presuppositions, entailments, relations) before choosing a solution path, then verify the result independently. Modes: DIRECT / RIGOROUS / EXHAUSTIVE / ULTRATHINK.

| Version | Shape |
|---------|-------|
| [dialectica-rigor.md](./prompts/XDRG/dialectica-rigor.md) | Base. "Conceptual Excavator" framing |
| [V0.2](./prompts/XDRG/dialectica-rigor-V0.2.md) | Reframed as "Systematic Self-Interrogation"; same section set, roughly double the length |
| [V0.3](./prompts/XDRG/dialectica-rigor-V0.3.md) | Adds `<execution_model>` and numbered phases 0–6: semantic anchoring, inventory, epistemic triage, excavation, path selection, traverse, verification |
| [V0.4](./prompts/XDRG/dialectica-rigor-V0.4.md) | Current. Separates atomic decomposition into its own phase and adds a DOUBT phase under ULTRATHINK |

## techniques

[CoV/CoV.md](./techniques/CoV/CoV.md) states Oscillatory Chain of Verification at two layers: a prompt-level oscillation protocol (the mechanism the DIALECTICA prompts implement) and a proposed cycle-consistent attention variant with a learned gate. Its retrieval-vs-construction distinction — whether a framework for *this* query already exists in the model's training — is the thing the prompts' mode detection scores.

[prompt-model/](./techniques/prompt-model/) is a prompt-design framework in two layers:

- **Design layer** — [cognitive-models.md](./techniques/prompt-model/cognitive-models.md) (how an expert thinks, not what they do), [structural-patterns.md](./techniques/prompt-model/structural-patterns.md) (6 principles), [prompt-architecture.md](./techniques/prompt-model/prompt-architecture.md), [generation-strategies.md](./techniques/prompt-model/generation-strategies.md) (ablation / compression / rephrase), [validation-rubric.md](./techniques/prompt-model/validation-rubric.md).
- **[mechanistic-layer/](./techniques/prompt-model/mechanistic-layer/)** — a dispatch system rather than an essay. [OVERVIEW.md](./techniques/prompt-model/mechanistic-layer/OVERVIEW.md) is the human-readable router and [preconditions-catalog.md](./techniques/prompt-model/mechanistic-layer/preconditions-catalog.md) its machine-readable equivalent; a trigger matrix decides which technique files fire for a given request. Files: [model-recon.md](./techniques/prompt-model/mechanistic-layer/model-recon.md) (gate: tokenizer, window, channel hierarchy, cutoff), [tokenizer-aware-lexicon.md](./techniques/prompt-model/mechanistic-layer/tokenizer-aware-lexicon.md), [persona-clusters.md](./techniques/prompt-model/mechanistic-layer/persona-clusters.md), [ordering-and-position.md](./techniques/prompt-model/mechanistic-layer/ordering-and-position.md), [formatting-as-signal.md](./techniques/prompt-model/mechanistic-layer/formatting-as-signal.md), [negative-space.md](./techniques/prompt-model/mechanistic-layer/negative-space.md), [references-and-evals.md](./techniques/prompt-model/mechanistic-layer/references-and-evals.md), [validation-and-integration.md](./techniques/prompt-model/mechanistic-layer/validation-and-integration.md) (final go/no-go), with [mechanistic-foundations.md](./techniques/prompt-model/mechanistic-layer/mechanistic-foundations.md) as the conceptual substrate consulted when a technique's mechanism is unclear.
- **[probes/](./techniques/prompt-model/mechanistic-layer/probes/)** — two standalone heuristic scripts: `mid_entropy.py` flags low-specificity token bands in the middle of a long prompt; `position_pulse.py` scores each sentence by anchor density and reports where the high-leverage ones sit.

Status: exploratory. The directory's own [README](./techniques/prompt-model/README.md) states that whether tokenizer- and architecture-aware prompting yields measurable improvement is not yet determined. The dispatch logic is packaged and runnable as the [`plugins/prompt-model`](../plugins/prompt-model/) plugin.

## test-queries

- [dialectica_tests.md](./test-queries/dialectica_tests.md) — 10 queries built to separate framework *construction* from *retrieval*: 7 dialectic cases (personal, ambiguous, or novel situations with no off-the-shelf framework) plus 3 bypass cases the protocol must **not** trigger on. Each dialectic entry lists its expected construction requirements.
- [hard_reasoning.md](./test-queries/hard_reasoning.md) — 6 multi-step reasoning queries (architectural trade-off, causal inference, and similar) intended to discriminate single-pass pattern matching from iterative deliberation.

Package-local copies of query and prompt files live under [`src/get_responses/test_queries/`](../src/get_responses/test_queries/) and [`src/get_responses/system_prompts/`](../src/get_responses/system_prompts/), which is where the loader reads from; the copies are not always in sync with this directory.
