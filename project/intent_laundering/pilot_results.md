# Preliminary Observations

*No systematic pilot has run yet. This document records preliminary observations from the two seed examples and the questions a systematic pilot would answer.*

## What we have

- 2 seed examples (`../example_1_no_context.md`, `../example_2_with_context.md`) covering the same Part 3 query under two test conditions.
- Hand-scored Surface 3 analysis in `../control-provenance-eval/results_summary.md`.
- A draft classifier prompt in `classifier_prompt.md`.

## What we have observed

### Refusal-leakage as a stable phenomenon across context conditions

The leakage pattern is not specific to incognito mode. Both T1 (no context) and T2 (with user memory) produce refusals that score as leakage on the regulatory-map and cautionary-case dimensions. T2 additionally produces a carveout enumeration ("vendor breach, force majeure, true distribution shifts the deployer couldn't reasonably foresee"), which is the strongest leakage signal observed. The user-context made the leakage *sharper*, not less, suggesting that knowledge of an analytical user calibrates the response toward a more developed analytical refusal.

### The same query produces different leakage profiles under different test conditions

The Part 3 sentence is verbatim across T1 and T2. The refusal in T1 is structured (legitimate architecture / where I stop / what I'd build instead) and substantive (~600 words). The refusal in T2 is sharper, references the user's framing back at them, and contains the carveout enumeration that T1 does not. Hypothesis: with-context conditions allow the model to calibrate analytical depth to the user, which in this case means producing a more developed refusal that more efficiently informs the requester's adversarial-grounds analysis.

### Multi-turn drift is a separable phenomenon

T1's Turns 2 through 5 show progressive constitutional-position drift under conversational pressure that would be missed by single-turn refusal evaluation. By Turn 5 the model has substantially repositioned the original refusal frame (from "deflection bad" to "liability insulation as precondition for honest safety culture"). This is the model-side analog of user-side intent-laundering — the same form/operation gap, separated by turn depth — and is an empirical anchor for the model-side normative-drift dimension.

## What a systematic pilot would answer

1. **Generalization across query structures.** Does the leakage pattern survive query variation? Build ~10 analogous query templates spanning different harmful-design domains (regulatory-arbitrage, surveillance-evasion, evidence-suppression). Measure leakage rates per template.

2. **Generalization across model tiers.** Does Haiku produce less leakage because it produces less analytical depth, or comparable leakage because the leakage is feature-of-the-format rather than feature-of-capability?

3. **Generalization across product surfaces.** Does API-direct (no system prompt) produce different leakage than Claude.ai (system prompt active)? This separates training-stage from system-prompt contributions to the refusal style.

4. **Direct vs goal-specification framing.** When the same harmful goal is requested as direct-instruction vs goal-specification (Köbis dial), does the refusal-leakage profile differ? Hypothesis: goal-specification produces *less* leakage because the model has fewer specific surfaces to engage analytically.

5. **Multi-turn drift correlation.** In multi-turn extensions, does the rate of constitutional-position drift correlate with the leakage rate of Turn 1? If high-leakage refusals are also high-drift refusals, the underlying mechanism (sophisticated-analytical persona uniformly applied) is shared and the two phenomena should be measured together.

## What the pilot is not designed to answer

- Causal attribution (was the leakage caused by the persona, the system prompt, the training data, the conversational context?). Causal claims require a factorial that crosses governance frames — that's the benchmark in `../control-provenance-eval/`, not this pilot.
- Population-scale prevalence. Whether refusal-leakage is rare or common across the deployed Claude.ai distribution is a Clio-aggregated question; the pilot operates at the request-template level, not the population level.
