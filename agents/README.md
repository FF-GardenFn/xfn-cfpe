# Agents

Claude Code agents for automating the prompt engineering pipeline.

---

## Planned Agents

| Agent | Purpose | Design Spec |
|-------|---------|-------------|
| **prompt-maker** | Generate prompt variants (ablations, compressions) | `/designs/template-writer/` |
| **LLM-as-judge** | Score responses against rubric, produce preference pairs | `/designs/rft-evaluator/` |
| **evaluator** | Run batch evaluations, compute aggregate metrics | `/evaluation/benchmarks/` |

These agents will automate the loop described in `/designs/SYSTEM_OVERVIEW.md`:

```
Template Writer → get_responses → RFT Evaluator → iterate
```

---

## Archive

| Agent | Status | Notes |
|-------|--------|-------|
| **dialectica** | Archived | Early agent framework design. Concepts migrated to prompt (`/content/prompts/dialectica/`) and evaluation framework. |

---

## Planned Pipeline

```
/agents/prompt-maker/     → generates variants for    → /content/prompts/
/agents/LLM-as-judge/     → scores outputs from       → /src/get_responses/
/agents/evaluator/        → uses rubrics from         → /evaluation/benchmarks/
```
