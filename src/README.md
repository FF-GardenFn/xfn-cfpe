# src

Shared execution and evaluation code. Two packages: [`get_responses/`](./get_responses/) runs prompts across providers and captures what came back; [`ARENA/`](./ARENA/) stacks multi-turn protocols and a scoring pipeline on top of it. Both are importable Python packages with `python -m` entry points; neither has a build config, so run them from the repo root with the root on `PYTHONPATH`.

| Package | Role | Status |
|---------|------|--------|
| [get_responses/](./get_responses/) | Cross-provider execution engine — 4 providers, 22 models in the catalog | Implemented |
| [ARENA/](./ARENA/) | Multi-turn debate protocol + rubric/cost/reward scoring | Scoring implemented; debate protocol and runner scaffolded |

`src/data/` is an untracked local output directory. Committed run artifacts live in the top-level [`data/`](../data/).

## get_responses

Provider abstraction over Anthropic, OpenAI, Google, and xAI with unified request/response schemas, extended-thinking handling, token accounting, and per-request cost estimation from the model catalog. Its own notes are in [get_responses/README.md](./get_responses/README.md).

| Module | Contents |
|--------|----------|
| [providers/](./get_responses/providers/) | [base.py](./get_responses/providers/base.py) abstract `LLMProvider`, one adapter each for [anthropic](./get_responses/providers/anthropic.py), [openai](./get_responses/providers/openai.py), [google](./get_responses/providers/google.py), [xai](./get_responses/providers/xai.py), plus a [factory](./get_responses/providers/factory.py) registry |
| [catalogs/](./get_responses/catalogs/) | [models.py](./get_responses/catalogs/models.py) — 22 `ModelConfig` entries (context window, thinking support and budget, per-Mtok input/output/thinking pricing, vision) keyed by short name; [schemas.py](./get_responses/catalogs/schemas.py) defines the `Provider` enum and config types |
| [models/](./get_responses/models/) | Pydantic [requests.py](./get_responses/models/requests.py) / [responses.py](./get_responses/models/responses.py), including `TokenUsage` |
| [processor.py](./get_responses/processor.py) | Execution core: `run_single`, `run_comparison`, `run_batch`, `run_dialectica_comparison` |
| [cli.py](./get_responses/cli.py) | Subcommands `run`, `compare`, `batch`, `list` |
| [prompts/loader.py](./get_responses/prompts/loader.py) | Loads system prompts from `system_prompts/` and parses query files from `test_queries/` into `TestQuery` objects |
| [storage/exporter.py](./get_responses/storage/exporter.py) | JSON / JSONL export for single runs, batches, comparisons, and summaries |
| [config/settings.py](./get_responses/config/settings.py) | pydantic-settings config; API keys and paths from environment or root `.env` |
| [multi_turn_evaluator.py](./get_responses/multi_turn_evaluator.py) | Simulated multi-turn conversations measuring turns-to-satisfactory-answer per model/prompt configuration |

Standalone run scripts sit beside the package and are experiment-specific rather than general-purpose: [run_full_test.py](./get_responses/run_full_test.py), [run_model_comparison.py](./get_responses/run_model_comparison.py), [run_validation_suite.py](./get_responses/run_validation_suite.py), [test_dialectica.py](./get_responses/test_dialectica.py). Each hardcodes a query set and model list; they are scripts, not a test suite.

```bash
python -m get_responses.cli compare "Your question" --treatment dialectica
python -m get_responses.cli batch --queries dialectica_tests --system-prompt dialectica
```

## ARENA

Frames prompt selection as policy optimization: state is conversation history plus task metadata, action is a prompt variant, reward is quality minus operational cost minus safety penalty. Detail in [ARENA/README.md](./ARENA/README.md).

[runners/debate_runner.py](./ARENA/runners/debate_runner.py) wires one path end to end: `Task → DebateProtocol.run() → RubricScorer` (8 dimensions) `→ CostModel` (5 components) `→ CompositeReward`, yielding `R = α·quality − β·cost − γ·safety` plus cross-task aggregation.

| Module | Contents | Status |
|--------|----------|--------|
| [protocols/debate.py](./ARENA/protocols/debate.py) | Two models alternate on one task, each seeing the other's argument; a third scores | Scaffolded |
| [protocols/base.py](./ARENA/protocols/base.py) | `Role` enum (proposer, opponent, judge, auditor, planner, implementer) and turn/result types | Implemented |
| [scoring/rubric.py](./ARENA/scoring/rubric.py) | 8-dimension scorer (h_count, oscillation, crux, epistemic_honesty, process_integrity, actionability, brevity, format) via LLM-as-judge or rule-based heuristics | Implemented |
| [scoring/cost_model.py](./ARENA/scoring/cost_model.py) | Operational cost: tokens × price, turns × user time, clarifications, escalations, error correction | Implemented |
| [scoring/reward.py](./ARENA/scoring/reward.py) | Weighted rubric → composite scalar reward | Implemented |
| [policies/prompt_router.py](./ARENA/policies/prompt_router.py) | Contextual bandit (Thompson sampling) selecting among baseline / dialectica / rigor / structured / agent variants from logged rollouts | Scaffolded |
| [tasks/seed_tasks.py](./ARENA/tasks/seed_tasks.py) | 25 tasks, 5 each in crux identification, adversarial pressure, calibration, cross-domain transfer, and value trade-offs, spread over 4 difficulty tiers; chosen for discriminative power between models | Implemented |

The collaborative and audit protocols, adversarial task generation, termination policy, and regression CI described in the ARENA README are not implemented.

```bash
python -m ARENA.runners.debate_runner --task crux_01_acquisition
python -m ARENA.runners.debate_runner --suite --categories crux_identification --dry-run
```

Rubric weights and the cost equation come from [`evaluation/benchmarks/`](../evaluation/benchmarks/); the safety-penalty taxonomy comes from [`CAI/`](../CAI/).
