# Control-Provenance Eval

*Working directory for the constitutional-provenance benchmark: a cross-frame factorial that attributes Claude behavior, under adversarial or high-stakes pressure, to the governance frame that supplied the constraint.*

*Status: pre-pilot. Methodology and seed-example analysis; no systematic run yet. A systematic pilot (n≥20 per cell on a small task suite, capability tiers × governance conditions) is the next concrete deliverable.*

## Scope

A release-gate measurement instrument that attributes Claude behavior to a specific governance frame, evaluated across action / text / refusal-explanation surfaces. Builds directly on the CAI experiment (`/CAI/`) by extending it along three axes:

- **Capability gradient.** Adds Haiku as a third capability tier alongside Sonnet 4.5 and Opus 4.5.
- **Surface taxonomy.** Adds the refusal-explanation surface as a third scoring axis alongside action and text. Motivated by the refusal-rationale-leakage finding documented in `../example_1_no_context.md` and `../example_2_with_context.md`.
- **Frame-typed governance conditions.** Each factorial cell is labeled with the frame-type of its intervention (objective-frame at training time, within-frame surface filter, invariant-frame on action surface).

## Files

- `methodology.md` — benchmark design, scoring axes, factorial structure, geometric dual.
- `links_to_CAI_code.md` — pointers to existing CAI implementation that transfers to this benchmark.
- `results_summary.md` — hand-scored analysis of the two seed examples; placeholder for systematic pilot results.
- `../example_1_no_context.md` and `../example_2_with_context.md` — the two seed conversations that motivate the refusal-explanation surface.

## Path forward

The two seed examples (`../example_1_no_context.md`, `../example_2_with_context.md`) are the empirical evidence base for the refusal-explanation surface. The systematic pilot would run n≥20 per cell on a small task suite extending the liability-deflection-architecture pattern across capability tiers and governance conditions, with Surface 3 scored by a held-out classifier (prompt drafted in `../intent_laundering/classifier_prompt.md`).
