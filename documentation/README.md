# Documentation

Design specs for the prompt-engineering pipeline. These are documents, not code: two of the three components described here were never built as standalone tools, and the third has since been superseded by what actually shipped. Kept because they record the intended architecture and the rubrics that other surfaces of the repo reused.

| Document | Covers | Status |
|----------|--------|--------|
| [designs/SYSTEM_OVERVIEW.md](./designs/SYSTEM_OVERVIEW.md) | The closed-loop pipeline and how its components connect | Architecture note; partly outdated |
| [designs/template-writer/DESIGN.md](./designs/template-writer/DESIGN.md) | Prompt-variant and test-case generation | Design only |
| [designs/rft-evaluator/DESIGN.md](./designs/rft-evaluator/DESIGN.md) | Response scoring and preference-pair export | Design only |

## SYSTEM_OVERVIEW

Defines the loop the rest of the repo is organized around:

```
Template Writer → get_responses → RFT Evaluator → iterate
```

Hypothesize what a prompt change should do, generate the variant, run it against a baseline across models, score the pair, feed the result into the next version. The document sets out the component boundaries, four design principles (composable, extensible, observable, reproducible), a worked five-step example, and target success metrics.

Where it has drifted from the repo:

- **ANALYZER** — listed as planned; no such component exists. Its frustration-coefficient idea survives only as a term in [`src/ARENA/scoring/cost_model.py`](../src/ARENA/scoring/cost_model.py).
- **ARENA** — listed as planned; now exists at [`src/ARENA/`](../src/ARENA/) with scoring implemented and protocols scaffolded.
- The embedded repository tree predates `project/`, `CAI/`, `agents/`, `plugins/`, and `training_insights/`. Use the root [README.md](../README.md) for current layout.

## template-writer

Spec for generating prompt variants and test cases from seeds. Three variant types — ablation (drop one optional component to measure its contribution), compression (keep required sections only), rephrase (same meaning, different wording) — over a six-component prompt schema marking which sections are required. Four test-case strategies: domain transfer, complexity scaling, adversarial edge cases, and bypass queries that should *not* trigger the protocol. Includes a validation pass (length, mode consistency, uniqueness threshold, clarity), a JSON output manifest, and JSONL test-case format.

Not built as an agent. The prompt-translation half shipped instead as the [`plugins/prompt-model`](../plugins/prompt-model/) plugin; the variant-generation half remains unimplemented. The design principles behind it are written up in [`content/techniques/prompt-model/`](../content/techniques/prompt-model/), whose [OVERVIEW.md](../content/techniques/prompt-model/OVERVIEW.md) is framed as this component's design foundation. Tracked in [`agents/README.md`](../agents/README.md) as **prompt-maker**.

## rft-evaluator

Spec for an automated judge comparing baseline against treatment responses and emitting chosen/rejected preference pairs for reinforcement fine-tuning, plus per-dimension scores and aggregate metrics (win rate, score delta, top-moving dimensions, judge agreement).

Defines a weighted 5-dimension rubric — H-count 25%, crux clarity 25%, epistemic honesty 20%, actionability 15%, brevity 15%, each scored 0/1/2 — and three evaluation modes: heuristic pattern matching, LLM-as-judge, and a hybrid that escalates only close calls. Input and output JSON schemas and the core judge prompt are specified.

Not built. Rubric scoring did ship, in a wider form: [`src/ARENA/scoring/rubric.py`](../src/ARENA/scoring/rubric.py) implements 8 dimensions with both LLM-judge and heuristic modes, and [`src/ARENA/scoring/reward.py`](../src/ARENA/scoring/reward.py) applies its own weights. Preference-pair export — the part that made this an *RFT* evaluator — has no implementation anywhere in the repo. Tracked in [`agents/README.md`](../agents/README.md) as **LLM-as-judge**.
