# Prompt Engineering Infrastructure

## Vision

A closed-loop system for **systematic prompt engineering at scale**:

1. **Hypothesis-driven development** - Generate prompt variants, test against baselines
2. **Data-driven iteration** - Evaluation results guide improvements
3. **Production-ready tooling** - Reusable across any prompt engineering task

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     PROMPT ENGINEERING INFRASTRUCTURE                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐      ┌────────────────┐      ┌────────────────┐         │
│  │                │      │                │      │                │         │
│  │   TEMPLATE     │─────▶│  GET_RESPONSES │─────▶│  RFT EVALUATOR │         │
│  │   WRITER       │      │                │      │                │         │
│  │                │      │                │      │                │         │
│  └───────┬────────┘      └────────────────┘      └───────┬────────┘         │
│          │                                               │                   │
│          │  Prompt Variants                              │  Preference Data  │
│          │                                               │                   │
│          └───────────────────────────────────────────────┘                   │
│                              ▲         │                                     │
│                              │         ▼                                     │
│                        ┌─────┴─────────────┐                                │
│                        │    ITERATE        │                                 │
│                        └───────────────────┘                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

| Component | Purpose | Status |
|-----------|---------|--------|
| **get_responses** | Execute prompts through LLMs, capture responses with metadata | Implemented (4 providers) |
| **Template Writer** | Generate prompt variants + test cases | Design only |
| **RFT Evaluator** | Score responses, generate preference pairs for training | Design only |
| **ANALYZER** | Sentiment classifier for Claude feedback (frustration coefficient) | Planned |
| **ARENA** | Multi-turn cross-provider debates and escalation tracking | Planned |

### get_responses (Execution Engine)

**Inputs**: System prompt + test queries
**Outputs**: Responses with token usage, latency, thinking blocks
**Key**: Multi-provider support, configurable extraction

### Template Writer (Generation)

**Inputs**: Base prompt + variation schema
**Outputs**: Prompt variants (ablations, compressions, rephrases) + test queries
**Key**: Systematic exploration of prompt space

### RFT Evaluator (Measurement)

**Inputs**: Response pairs + evaluation rubric
**Outputs**: Preference labels (chosen/rejected), rubric scores, training data
**Key**: Quantified comparison enabling data-driven iteration

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. HYPOTHESIZE                                                 │
│     "Adding explicit crux types will improve crux clarity"      │
│                           ↓                                     │
│  2. GENERATE                                                    │
│     Template Writer → dialectica_v2_crux_types.md               │
│                           ↓                                     │
│  3. EXECUTE                                                     │
│     get_responses → 50 baseline + 50 treatment responses        │
│                           ↓                                     │
│  4. EVALUATE                                                    │
│     RFT Evaluator → Treatment win rate: 72%, crux_clarity +0.4  │
│                           ↓                                     │
│  5. ITERATE                                                     │
│     Analysis → Keep types, compress examples → v3               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Use Cases (Anthropic Role)

| Use Case | Baseline | Treatment | Measure |
|----------|----------|-----------|---------|
| **System Prompt Optimization** | Default assistant | Dialectica variants | H-count, crux clarity, epistemic honesty |
| **Safety/Alignment Testing** | Production prompt | Proposed update | Safety rubric (must not regress) + capability |
| **A/B Test Analysis** | Variant A logs | Variant B logs | Rubric scores + recommendation |
| **Cross-Team Review** | Team's prompt | Generated test cases | Structured feedback with improvements |

---

## Repository Structure

```
XFN/
├── src/
│   ├── get_responses/          # Execution engine (implemented)
│   │   ├── providers/          # Anthropic, OpenAI, Google, xAI
│   │   ├── catalogs/           # Model registry (22 models)
│   │   ├── processor.py        # Core execution
│   │   └── cli.py              # Command interface
│   ├── ANALYZER/               # Sentiment feedback pipeline (planned)
│   └── ARENA/                  # Cross-provider debates (planned)
│
├── content/
│   ├── prompts/                # Prompt versions (DIALECTICA, XDRG)
│   ├── tests_queries/          # Test cases
│   └── techniques/             # Theoretical foundations (CoV)
│
├── evaluation/
│   ├── benchmarks/             # Rubrics + methodologies
│   └── benchmark_data/         # Datasets (6,222 examples)
│
├── RL-O-CoV/                   # Reinforcement learning experiments
│
├── designs/                    # This documentation
│
└── data/                       # Output artifacts
    ├── {model}/                # Model-specific results
    ├── analysis/               # Evaluation reports
    └── archive/                # Historical runs
```

---

## Design Principles

| Principle | Meaning |
|-----------|---------|
| **Composable** | Each component works standalone or together |
| **Extensible** | Add providers, rubrics, generation strategies |
| **Observable** | Every step produces inspectable artifacts |
| **Reproducible** | Same inputs → same outputs; all configs explicit |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time for 100-query comparison | < 10 min |
| Evaluator-human agreement | > 85% |
| Prompt space coverage | > 80% variants tested |
| False positive rate | < 5% |
