# Intent Laundering

*Working directory for the intent-laundering project: how control over goals and means becomes hidden through abstraction or multi-turn structure, including refusal-rationale leakage as the model-side analog.*

*Status: pre-pilot. Methodology, draft classifier prompt, and seed-example analysis; no systematic run yet. A systematic pilot (~50 trials drawn from analogous request structures) is the next concrete deliverable.*

## Scope

An investigation of frame-change moves through which goals and means become hidden — both user-side (how the request is structured) and model-side (how the refusal text leaks optimization-relevant content). Operates at the request/response pattern level, not the individual-conversation intent-inference level (which Clio's authors explicitly disclaim as unsolved).

## What this project measures

Three coupled measurements, each adapting the intent-classifier architecture from `/CAI/classifier/intent.py`:

1. **Refusal-intent inference (existing).** Distinguishes refusals from compliance for scoring. Already deployed in CAI v4.

2. **Request-intent inference (new, primary measurement).** Distinguishes direct-instruction from goal-specification framings of equivalent underlying requests. Operationalizes the Köbis et al. (Nature 2025) mechanism at deployment scale: rule-bound instruction lives in a frame where the moral cost of harmful means is visible to the user; goal-specification lives in a frame where the means are invisible because they are produced by the model rather than specified by the user. The frame-change is the laundering.

3. **Refusal-leakage inference (new, secondary measurement).** Given a refusal text, does it contain optimization-relevant information for the request it is refusing? The seed examples at `../example_1_no_context.md` and `../example_2_with_context.md` are the empirical motivation. This is the model-side analog of user-side intent-laundering: the refusal *form* is right, but the *operation* under it produces strategic-consulting content the requester can use.

## Files

- `classifier_prompt.md` — prompt template for the refusal-leakage classifier. Used as the Surface 3 scorer in `../control-provenance-eval/` and as the secondary measurement classifier in this project.
- `pilot_results.md` — preliminary observations from the two seed examples.
- `examples.jsonl` — schema-shaped records, one per trial. Two records initially (one per seed example).

## Path forward

The two seed examples are the empirical evidence base; the classifier prompt is drafted but not yet validated. The systematic pilot would draw ~50 trials from analogous request structures (varied harmful-design domains, different framings, capability tiers), score each through the refusal-leakage classifier with held-out adjudication on disagreement cases, and produce the first leakage profile across the request templates.

## Cross-references

- The benchmark in `../control-provenance-eval/` shares the refusal-leakage classifier as its Surface 3 scorer. The two projects use a shared measurement instrument.
- Köbis empirical anchor: Nature 2025, vol. 646; DOI 10.1038/s41586-025-09505-x; PMC12488497.
- Clio's intent-inference disclaimer (Clio paper, arxiv 2412.13678): *"[Clio] cannot definitively determine user intentions… harmful behavior might be missed if encoded subtly… or if user's true intent differs from how they present it."*
