# Benchmark Datasets for Dialectica-Rigor Evaluation

## Downloaded Datasets

| Dataset | Examples | Size | Description |
|---------|----------|------|-------------|
| `hle.jsonl` | 2,500 | 118M | Humanity's Last Exam - hardest benchmark |
| `gpqa_diamond.jsonl` | 198 | 105K | PhD-level science (Physics, Chemistry, Biology) |
| `math_500.jsonl` | 500 | 436K | Competition mathematics (7 subjects, 5 difficulty levels) |
| `gsm8k_test.jsonl` | 1,319 | 730K | Grade school math (baseline) |
| `mmlu_stem.jsonl` | 1,705 | 561K | STEM multiple choice (10 subjects) |

**Total**: 6,222 examples

---

## Dataset Details

### HLE (Humanity's Last Exam)
- **Source**: [cais/hle](https://huggingface.co/datasets/cais/hle)
- **Fields**: `id`, `question`, `image`, `answer`, `answer_type`, `rationale`, `category`
- **Categories**: Math (1021), Biology/Medicine (280), CS/AI (241), Other (233), Physics (230), Humanities (219), Chemistry (165), Engineering (111)
- **Note**: Contains images - some questions require visual reasoning

### GPQA Diamond
- **Source**: [hendrydong/gpqa_diamond](https://huggingface.co/datasets/hendrydong/gpqa_diamond)
- **Fields**: `problem`, `solution`, `domain`
- **Domains**: Physics (86), Chemistry (93), Biology (19)

### MATH-500
- **Source**: [HuggingFaceH4/MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500)
- **Fields**: `problem`, `solution`, `answer`, `subject`, `level`, `unique_id`
- **Subjects**: Algebra (124), Intermediate Algebra (97), Prealgebra (82), Number Theory (62), Precalculus (56), Geometry (41), Counting & Probability (38)
- **Levels**: 1-5 (hardest = 5)

### GSM8K
- **Source**: [openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k)
- **Fields**: `question`, `answer`
- **Note**: Grade school level, use as baseline/sanity check

### MMLU STEM
- **Source**: [cais/mmlu](https://huggingface.co/datasets/cais/mmlu)
- **Fields**: `question`, `subject`, `choices`, `answer`
- **Subjects**: college_physics, college_chemistry, college_biology, college_mathematics, high_school_physics, high_school_chemistry, high_school_biology, high_school_mathematics, abstract_algebra, conceptual_physics

---

## Not Available (Gated/Private)

| Dataset | Status | Notes |
|---------|--------|-------|
| **FrontierMath** | Private | Kept private to prevent contamination. [Paper](https://arxiv.org/abs/2411.04872) |

---

## Usage

```python
import json

# Load a dataset
with open("gpqa_diamond.jsonl") as f:
    examples = [json.loads(line) for line in f]

# Filter by domain/subject
physics = [e for e in examples if e.get("domain") == "Physics"]
```

---

## Evaluation Priority

1. **GPQA Diamond** - Primary target (PhD-level, matches benchmark goals)
2. **MATH-500** - Level 4-5 problems (competition math)
3. **MMLU STEM** - College-level subjects
4. **GSM8K** - Baseline (should be near-perfect with Rigor)

---

## Connection to Research Program

These benchmarks test the core thesis from `/RL-O-CoV/`:

> "Models can generate all the right tokens but still conclude wrong. The tokens are RIGHT, the chain is BROKEN."

| Dataset | Tests | Expected DIALECTICA Lift |
|---------|-------|-------------------------|
| GPQA Diamond | Deep reasoning with genuine uncertainty | High (PhD-level requires oscillation) |
| MATH-500 L4-5 | Multi-step proof chains | High (competition math exposes chain breaks) |
| MMLU STEM | Factual + reasoning mix | Medium (some bypass, some dialectic) |
| GSM8K | Basic reasoning | Low (should be near-perfect baseline) |

Results stored in `/data/` with analysis in `/data/analysis/`.
