# System Design

This infrastructure enables systematic prompt engineering through a closed-loop pipeline: generate prompt variants, execute them against LLMs, evaluate the outputs, and iterate. The system is designed for reuse across any prompt development task—whether optimizing a system prompt, running ablation studies, or generating training data for reinforcement fine-tuning.

---

## get_responses

The execution layer. It sends prompts to LLMs and captures structured responses including chain-of-thought when available.

The core abstraction is a `Processor` that takes a prompt and system prompt, routes them through a configured provider, and returns a `CompletionResponse` containing the answer, thinking content, token usage, and latency. The provider layer supports four backends: Anthropic (Claude), OpenAI (GPT/o-series), Google (Gemini), and xAI (Grok). All share the same interface—swap providers with a single config change. A centralized model catalog tracks 22 models with pricing, token limits, and capability flags. Configuration lives in environment variables via pydantic-settings.

For comparative work, the processor supports paired execution: run the same query against a baseline prompt and a treatment prompt, then export both responses for downstream evaluation. Batch processing handles multiple queries with multiple prompts, producing a matrix of responses. All outputs serialize to JSON or JSONL for pipeline integration.

The prompt loader reads system prompts from markdown files and test queries from structured documents. This separation means prompts live in version control as readable artifacts, not embedded in code.

**Current state**: Four providers implemented (Anthropic, OpenAI, Google, xAI) with unified interface. Extended thinking support for Claude and Gemini. Reasoning mode support for o1/o3 series. Centralized model catalog with 22 models, pricing, and capabilities. CLI operational for single runs, comparisons, and batch execution. Prompt loading and response export functional.

**Next**: Implement async execution for parallelism. Add retry logic with exponential backoff. Build cross-provider comparison tooling.

---

## RFT Evaluator

The measurement layer. It takes response pairs and determines which is better, producing preference labels suitable for reinforcement fine-tuning.

Evaluation operates against a rubric—currently the Dialectica rubric measuring hypothesis count, crux clarity, epistemic honesty, actionability, and brevity. Each dimension scores 0-2, weights combine to a total, and the higher-scoring response becomes "chosen" while the other becomes "rejected." The evaluator outputs this as structured preference pairs in the format expected by training pipelines.

Two evaluation modes exist. Heuristic scoring uses pattern matching for speed—counting hypothesis markers, detecting crux terminology, finding confidence statements. LLM-as-judge uses a capable model to score against the rubric with justifications. Hybrid mode runs heuristics first and escalates to LLM judgment when scores are close.

The evaluator also produces aggregate metrics: treatment win rate, average score delta, per-dimension breakdowns. These inform whether a prompt variant is worth keeping and which dimensions improved or regressed.

**Current state**: Design complete. Rubric defined. Integration points with get_responses specified.

**Next**: Implement heuristic scorer for Dialectica dimensions. Build LLM-as-judge prompt template. Create preference pair exporter in OpenAI and Anthropic formats.

---

## Template Writer

The generation layer. It produces prompt variants and test cases to feed the evaluation loop.

For prompts, it takes a base prompt and applies systematic variations: ablations that remove one section at a time to measure its contribution, compressions that minimize token count while preserving intent, rephrases that test alternate framings of the same instruction. Each variant becomes a testable hypothesis about what makes the prompt effective.

For test cases, it takes seed examples and expands coverage through domain transfer (same structure, different topic), complexity scaling (simple to nuanced versions), and adversarial generation (edge cases designed to stress the prompt). Validation filters ensure generated content meets quality thresholds before entering the evaluation pipeline.

The output is a manifest linking each variant to its generation strategy and hypothesis, enabling structured analysis of what worked and why.

**Current state**: Design complete. Generation strategies defined. Validation criteria specified.

**Next**: Implement ablation generator for system prompts. Build test case generator with domain transfer. Add deduplication using embedding similarity.

---

## The Loop

These components form a cycle. Template Writer produces prompt variants and test queries. get_responses executes them against LLMs, generating response pairs. RFT Evaluator scores those pairs and identifies which variants improve on baseline. Results inform the next iteration of Template Writer, focusing generation on promising directions.

The loop can run manually—engineer reviews results, formulates next hypothesis, generates new variants—or semi-automatically with the evaluator flagging which dimensions need work and the generator targeting those dimensions.

Artifacts at each stage are inspectable and version-controllable: prompts as markdown, queries as JSONL, responses as JSON, evaluations as structured reports. The pipeline is reproducible; same inputs yield same outputs.

---

## File Structure

```
get_responses/
├── config/           # pydantic-settings configuration
├── models/           # request/response data structures
├── providers/        # LLM backends
│   ├── anthropic.py  # Claude (thinking support)
│   ├── openai.py     # GPT-4o, GPT-5, o1/o3 (reasoning)
│   ├── google.py     # Gemini (thinking support)
│   └── xai.py        # Grok
├── catalogs/         # centralized model registry
│   ├── models.py     # 22 models with pricing/capabilities
│   └── schemas.py    # ModelConfig, ExperimentConfig
├── prompts/          # prompt and query loading
├── storage/          # response export
├── processor.py      # core execution logic
├── cli.py            # command-line interface
├── system_prompts/   # versioned prompt files
├── test_queries/     # versioned test cases
├── evaluator/        # [planned] RFT evaluation
└── templates/        # [planned] variant generation
```

---

## What This Enables

A prompt engineer can formulate a hypothesis ("adding explicit crux types will improve reasoning"), generate the variant, run it against 50 test queries, get quantified results showing +0.4 on crux clarity but -0.1 on brevity, then iterate with a compressed version. The infrastructure handles execution, measurement, and artifact management. The engineer focuses on hypotheses and interpretation.

For training data generation, the same loop produces preference pairs at scale: run thousands of queries, score all responses, export chosen/rejected pairs for RFT. The evaluator's rubric encodes what "better" means; the pipeline produces data reflecting that definition.

For cross-team prompt review, an engineer can take another team's prompt, generate test cases for their use case, run evaluation against a capability rubric, and produce structured feedback with specific dimension scores and improvement suggestions.

The infrastructure is the reusable foundation. The rubrics, prompts, and queries are the domain-specific configuration. Swap in a different rubric for safety evaluation or customer support quality—the machinery stays the same.

---

## Planned Extensions

### ANALYZER (`/src/ANALYZER/`)

Sentiment classifier and scraper for Claude product feedback. Collects user sentiment from public sources, classifies by product area and polarity.

**Connection to evaluation**: Provides proxy data for the "Frustration Coefficient" in `/evaluation/benchmarks/equ.md`. When users express frustration with Claude responses, that signal correlates with evaluation failure modes—false certainty, shallow reasoning, premature convergence.

### ARENA (`/src/ARENA/`)

Multi-turn evaluation framework for cross-provider comparison. Tests Claude against other models in debates, collaborative problem-solving, and extended conversations.

**Connection to evaluation**: Extends multi-turn methodology from `/evaluation/benchmarks/methodologies.md`. Measures escalation patterns (when users switch from Haiku to Sonnet to Opus) and resolution efficiency across providers.
