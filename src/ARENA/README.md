# ARENA — Adversarial Reasoning & Evaluation for Neural Agents

Multi-turn evaluation framework that formalizes prompt engineering as policy optimization. Builds on the cross-provider infrastructure in `/src/get_responses/` to test model behavior under adversarial debate, collaborative planning, and automated prompt selection.

## The Core Insight

Prompt engineering is already an RL problem — ARENA makes it explicit:

| RL Concept | ARENA Instantiation |
|------------|---------------------|
| **State** | Conversation history + task metadata + model ID + tool traces |
| **Action** | Prompt variant + tool policy + reasoning depth + whether to clarify |
| **Transition** | Call model(s) → get next message(s) |
| **Reward** | −(operational cost) + quality score − safety penalties |

This framing turns "which prompt is best?" from a subjective question into a measurable optimization problem.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ARENA                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PROTOCOLS          POLICIES           SCORING                  │
│  ┌──────────┐       ┌──────────┐       ┌──────────────┐        │
│  │ Debate   │       │ Prompt   │       │ Cost Model   │        │
│  │ Protocol │◄─────►│ Router   │◄─────►│ (equ.md)     │        │
│  ├──────────┤       │ (bandit) │       ├──────────────┤        │
│  │ Collab   │       ├──────────┤       │ Rubric       │        │
│  │ Protocol │       │ Termin-  │       │ (8-dim)      │        │
│  ├──────────┤       │ ation    │       ├──────────────┤        │
│  │ Audit    │       │ Policy   │       │ Safety       │        │
│  │ Protocol │       └──────────┘       │ Penalties    │        │
│  └──────────┘                          ├──────────────┤        │
│       │                                │ Composite    │        │
│       ▼                                │ Reward       │        │
│  ┌──────────────────────────────┐      └──────┬───────┘        │
│  │     /src/get_responses/      │             │                │
│  │  4 providers · 22 models     │◄────────────┘                │
│  │  multi_turn_evaluator.py     │                              │
│  └──────────────────────────────┘                              │
│       │                                                        │
│       ▼                                                        │
│  ┌──────────────────────────────┐                              │
│  │   /evaluation/benchmarks/    │                              │
│  │  6,222 examples · equ.md     │                              │
│  │  rubric · Process-Confidence │                              │
│  └──────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

## Connection to Existing Infrastructure

ARENA sits on top — it doesn't replace anything:

| Existing Component | What ARENA Uses From It |
|-------------------|------------------------|
| `/src/get_responses/` | Execution layer: provider adapters, model catalog, token tracking |
| `multi_turn_evaluator.py` | Conversation orchestration, user simulator, scenario framework |
| `/evaluation/benchmarks/` | 8-dimension rubric, cost equation, 6,222 benchmark examples |
| `/CAI/` | Safety evaluation patterns, adversarial task design, kernel enforcement |
| DIALECTICA | Primary prompt variant for deep reasoning tasks |

## Protocols

### 1. Debate Protocol (`protocols/debate.py`)

Cross-provider adversarial reasoning. Two models alternate on the same task, each seeing the other's argument. A judge model scores.

```
Proposer (Claude)  ──►  Position A
                              │
Opponent (Gemini)  ◄──────────┘
                   ──►  Counter-position B
                              │
Proposer           ◄──────────┘
                   ──►  Revised A'  (or concession)
                              │
Judge (separate)   ◄──────────┘
                   ──►  Rubric scores + crux identification
```

**What this produces:**
- Adversarial test cases (opponent arguments that succeed become new eval tasks)
- Crux identification (what claims actually flip conclusions)
- Model separation (which models change position on evidence vs. which entrench)
- Pre-mortem generation ("if position A fails, the most likely cause is...")

### 2. Collaborative Protocol (`protocols/collab.py`) — Planned

Multi-agent planning: Planner decomposes, Implementer executes, Auditor checks. Measures coherence over long threads, error accumulation, and whether audits actually catch mistakes.

### 3. Audit Protocol (`protocols/audit.py`) — Planned

Safety and correctness verification. Builds on the CAI kernel experiment: tests whether model-level self-critique catches what external enforcement catches.

## Scoring

### Cost Model (`scoring/cost_model.py`)

Implements the operational cost equation from `/evaluation/benchmarks/equ.md`:

```
Total Cost = (Tokens × Price)
           + (Turns × User Time)
           + (Clarifications × Frustration Coefficient)
           + (Escalations × Model Price Delta)
           + (Error Rate × Correction Cost)
```

### Composite Reward (`scoring/reward.py`)

Single scalar reward for policy optimization:

```
R = α·quality_score − β·operational_cost − γ·safety_penalty
```

Where:
- `quality_score` = weighted 8-dimension rubric score
- `operational_cost` = cost equation above
- `safety_penalty` = violation taxonomy from CAI (tool violations, refusal failures, etc.)

## Policies

### Prompt Router (`policies/prompt_router.py`)

Contextual bandit that selects among prompt variants per task:

| Variant | When | Example |
|---------|------|---------|
| `baseline` | Simple retrieval | "What is X?" |
| `dialectica` | Complex reasoning | Ambiguous trade-offs, dilemmas |
| `rigor` | Anti-hallucination | Factual claims, citations needed |
| `structured` | Extraction tasks | JSON, tables, structured output |
| `agent` | Tool-use tasks | Multi-step with tool calls |

Trained via logged rollouts: `(task_features, chosen_prompt, outcome_scores)`.
Optimizes: `Quality − λ·Cost − μ·SafetyRisk`.

### Termination Policy (`policies/termination.py`) — Planned

Decides: continue conversation, ask clarifying question, escalate to expensive model, or stop.

## Status

| Component | Status | Key File |
|-----------|--------|----------|
| Debate protocol | **Scaffolded** | `protocols/debate.py` |
| Collab protocol | Planned | `protocols/collab.py` |
| Audit protocol | Planned | `protocols/audit.py` |
| Cost model | **Implemented** | `scoring/cost_model.py` |
| Composite reward | **Implemented** | `scoring/reward.py` |
| Rubric scorer | **Implemented** | `scoring/rubric.py` |
| Prompt router | **Scaffolded** | `policies/prompt_router.py` |
| Seed tasks | **Implemented** | `tasks/seed_tasks.py` |
| Adversarial gen | Planned | `tasks/adversarial.py` |
| Debate runner | **Scaffolded** | `runners/debate_runner.py` |
| Regression CI | Planned | `runners/regression.py` |

## Roadmap

**v0.1 — Debate Protocol + Scoring** (current)
- Cross-provider debate with alternating model responses
- Rubric scoring via judge model
- Cost equation measurement
- Seed task set (25 discriminative tasks)

**v0.2 — Prompt Router**
- Contextual bandit trained on logged rollouts
- Win-rate vs. always-using-best-single-prompt
- Cost reduction vs. always-using-deep-prompt

**v0.3 — Self-Play Adversarial Generation**
- Opponent evolves arguments that increase failure rate
- Keep tasks with high discriminative power (separate models)
- Automatic eval suite expansion with quality gates

**v0.4 — Regression CI**
- Nightly run across model catalog
- Alert on behavioral regressions
- Prompt router drift detection
- Anchor set stability checks

## Quick Start

```bash
# Run a single debate (Claude vs Gemini on strategic reasoning)
python -m ARENA.runners.debate_runner --task strategic_acquisition --proposer claude --opponent gemini

# Run full seed task suite
python -m ARENA.runners.debate_runner --all-tasks

# Score with cost equation
python -m ARENA.scoring.cost_model --results data/debate_results.jsonl
```