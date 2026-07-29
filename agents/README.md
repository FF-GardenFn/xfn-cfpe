# Agents

Agent designs for automating the prompt-engineering pipeline described in [`/documentation/designs/SYSTEM_OVERVIEW.md`](../documentation/designs/SYSTEM_OVERVIEW.md):

```
Template Writer → get_responses → RFT Evaluator → iterate
```

Rather than standalone agent processes, most of this functionality has been absorbed into other surfaces of the repo. Status below is honest: where a capability shipped, the table says where it lives; where it didn't, it stays "designed, not built."

## Status

| Agent | Purpose | Design spec | Where it stands |
|-------|---------|-------------|-----------------|
| **prompt-maker** | Generate prompt variants: ablation (remove components to measure contribution), compression (minimize tokens, preserve intent), rephrase (alternate framings) | [`/documentation/designs/template-writer/`](../documentation/designs/template-writer/) | Shipped as the [`plugins/prompt-model`](../plugins/prompt-model/) plugin |
| **LLM-as-judge** | Score responses against the 8-dimension rubric; produce chosen/rejected preference pairs for RFT | [`/documentation/designs/rft-evaluator/`](../documentation/designs/rft-evaluator/) | Rubric scoring implemented in [`src/ARENA`](../src/ARENA/)'s pipeline (RubricScorer → CostModel → CompositeReward); preference-pair export not built |
| **evaluator** | Batch evaluation over benchmark datasets (GPQA Diamond, MATH-500, MMLU STEM, GSM8K) with cross-provider comparison and cost tracking | [`/evaluation/benchmarks/`](../evaluation/benchmarks/) | Batch cross-provider execution lives in [`src/get_responses`](../src/get_responses/) and ARENA's suite runner; a standalone metrics agent is not built |

## Archive

| Agent | Status | Notes |
|-------|--------|-------|
| **dialectica** | Archived | Early agent-framework design. Concepts migrated to the prompt ([`/content/prompts/dialectica/`](../content/prompts/dialectica/)) and the evaluation framework. |
