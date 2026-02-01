# XFN-CFPE

Infrastructure for systematic prompt engineering: hypothesis generation, cross-provider testing, and evaluation.

## What This Is

A closed-loop system for developing and validating prompt engineering techniques. Generate a hypothesis about what improves LLM reasoning, implement it as a prompt variant, test across providers, measure against rubric, iterate. The machinery handles execution and measurement; the engineer focuses on hypotheses and interpretation.

## The Stack

| Layer | Artifact | Status |
|-------|----------|--------|
| **Prompt** | DIALECTICA v0.3.7 | Implemented |
| **Evaluation** | 8-dimension rubric + Process-Confidence Coupling | Implemented |
| **Training** | RL-O-CoV | Experimental |

## Implementation Status

| Component | Status | Notes                                      |
|-----------|--------|--------------------------------------------|
| DIALECTICA prompt | Done | v0.3.7 with bypass detection               |
| DIALECTICA-RIGOR | Done | v0.4 anti-hallucination variant            |
| Cross-provider testing | Done | 4 providers, 22 models                     |
| Evaluation framework | Done | Process-Confidence Coupling                |
| Benchmark datasets | Done | 6,222 examples (GPQA, MATH-500, HLE, etc.) |
| RL-O-CoV training | Experimental | N/A                                        |
| ANALYZER | Planned | TBD                                        |
| ARENA | Planned | TBD                                        |

## Directory Structure

- **content/** - Prompts and theoretical foundations
  - [prompts/dialectica/](./content/prompts/dialectica/) - DIALECTICA versions (v0.1 → v0.3.7)
    - [dialectica_v0.3.7.md](./content/prompts/dialectica/dialectica_v0.3.7.md) - Current version
  - [prompts/XDRG/](./content/prompts/XDRG/) - DIALECTICA-RIGOR anti-hallucination variant
    - [dialectica-rigor-V0.4.md](./content/prompts/XDRG/dialectica-rigor-V0.4.md) - Current version
  - [techniques/CoV/](./content/techniques/CoV/) - Oscillatory Chain of Verification theory
- **src/** - Testing infrastructure
  - [get_responses/](./src/get_responses/) - Cross-provider execution engine
    - [providers/](./src/get_responses/providers/) - Anthropic, OpenAI, Google, xAI
    - [catalogs/](./src/get_responses/catalogs/) - Model registry (22 models with pricing)
  - [ANALYZER/](./src/ANALYZER/) - Sentiment classifier (planned)
  - [ARENA/](./src/ARENA/) - Cross-provider debates (planned)
- **evaluation/** - Measurement infrastructure
  - [benchmarks/](./evaluation/benchmarks/) - Rubrics, methodologies, test cases
    - [evaluation_framework.md](./evaluation/benchmarks/evaluation_framework.md) - 8-dimension scoring
    - [equ.md](./evaluation/benchmarks/equ.md) - Cost equations
  - [benchmark_data/](./evaluation/benchmark_data/) - Datasets (GPQA, MATH-500, MMLU, GSM8K, HLE)
- **RL-O-CoV/** - Reinforcement learning experiments
  - [README.md](./RL-O-CoV/README.md) - Approach and business case
  - [RL_O_CoV_Training_V2.py](RL-O-CoV/RL_O_CoV_Training_V2.py) - Training script
  - [RL_O_CoV_Training_V3.py](RL-O-CoV/RL_O_CoV_Training_V3.py) - Latest Training script
- **data/** - Experimental results
  - [haiku/](./data/haiku/), [sonnet/](./data/sonnet/), [opus/](./data/opus/) - Per-model results
  - [analysis/](./data/analysis/) - Evaluation reports
- **designs/** - System architecture
  - [SYSTEM_OVERVIEW.md](./designs/SYSTEM_OVERVIEW.md) - Pipeline architecture
  - [rft-evaluator/](./designs/rft-evaluator/) - Preference pair generation spec
  - [template-writer/](./designs/template-writer/) - Prompt variant generation spec
- **agents/** - Automation (planned)
  - [prompt-maker/](./agents/prompt-maker/) - Variant generation
  - [LLM-as-judge/](./agents/LLM-as-judge/) - Response scoring
  - [evaluator/](./agents/evaluator/) - Batch evaluation