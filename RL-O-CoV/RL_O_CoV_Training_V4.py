# %%
"""
================================================================================
RL-O-CoV V4: Resonance-shaped RL for Oscillatory Chain of Verification
================================================================================

V4 fixes the V3 audit failures:
- Correct hard-label ground truth and stricter math equivalence checks.
- Frozen, adapter-disabled reward judge with centered hidden-state geometry.
- Shaped resonance rewards over H1/H2 distinctness and oscillation engagement.
- K-sample group baselines, deterministic LoRA dropout, true LR warmup.
- Greedy evaluation, no eval contamination of training reward statistics.

================================================================================
"""

import os
import json
import math
import re
import random
from contextlib import nullcontext
from dataclasses import dataclass, field, asdict
from fractions import Fraction
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset


# =============================================================================
# REPRODUCIBILITY (Issue #2: No seeding)
# =============================================================================

def set_seed(seed: int = 42):
    """Set all seeds for reproducibility"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    # Deterministic algorithms (slower but reproducible)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    try:
        import transformers
        transformers.set_seed(seed)
    except ImportError:
        pass

    return seed


def get_version_info() -> Dict[str, str]:
    """Capture versions for reproducibility"""
    import sys
    versions = {
        "python": sys.version,
        "torch": torch.__version__,
        "cuda": torch.version.cuda if torch.cuda.is_available() else "N/A",
    }
    try:
        import transformers
        versions["transformers"] = transformers.__version__
    except ImportError:
        pass
    try:
        import peft
        versions["peft"] = peft.__version__
    except ImportError:
        pass
    try:
        import bitsandbytes
        versions["bitsandbytes"] = bitsandbytes.__version__
    except ImportError:
        pass
    return versions

# %%
# ============================================================================
# CONFIGURATION - CONSERVATIVE (learned from V1 disaster)
# ============================================================================

@dataclass
class TrainingConfigV4:
    """V4 config: stable RL estimator plus frozen mechanistic reward judge."""

    # Model
    model_name: str = "Qwen/Qwen2-7B-Instruct"

    # SAFETY RAILS BACK ON
    use_4bit: bool = True  # Was False in V1, caused OOM on gradients
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"

    # CONSERVATIVE LORA (V1 had r=128, way too high)
    lora_r: int = 32              # Was 128
    lora_alpha: int = 64          # 2x rank
    lora_dropout: float = 0.0     # RL policy gradients need deterministic policy forwards
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj"  # Attention only, not MLP
    ])

    # CONSERVATIVE TRAINING (V1 had lr=3e-5, exploded)
    learning_rate: float = 5e-6   # Was 3e-5 (6x lower)
    warmup_steps: int = 100       # NEW: gradual ramp-up
    total_training_steps: Optional[int] = None
    num_epochs: int = 3           # Was 5
    batch_size: int = 2           # Prompts per optimizer step
    group_size: int = 4           # GRPO-style samples per prompt
    max_seq_length: int = 2048
    max_new_tokens: int = 768
    max_grad_norm: float = 0.5    # Was 1.0 (tighter clipping)

    # SEMANTIC ANALYSIS
    # V4 keeps mid-layer analysis but fixes anisotropy with frozen, centered
    # embeddings rather than widening the similarity zone until it is constant.
    analysis_layer: int = 14      # Was 20 (too deep, representations converge)
    analysis_layers_to_log: List[int] = field(
        default_factory=lambda: [8, 14, 20]  # Log multiple layers for calibration
    )

    # SHAPED RESONANCE REWARD
    # Mean-centered similarities avoid same-model anisotropy; Gaussian bumps give
    # directional signal instead of a binary "zone" that collapses to a constant.
    hypothesis_distinct_target: float = 0.35
    oscillation_engagement_target: float = 0.50
    resonance_sigma: float = 0.18
    embedding_center_momentum: float = 0.99
    problem_anchor_min: float = 0.15

    # GENTLER REWARDS (prioritize not forgetting)
    correctness_weight: float = 2.5   # Higher than V1
    structure_weight: float = 1.5
    resonance_reward: float = 1.5     # Was 2.0
    drift_penalty_weight: float = 0.3 # Preserved from V1
    wrong_answer_max_reward: float = -0.25
    kl_coef: float = 0.02
    entropy_coef: float = 0.01

    # DATA (Issue #3: Config-driven split)
    train_samples: int = 1000     # Was 2000
    eval_samples: int = 100
    hard_mix_ratio: float = 0.2     # Fraction of harder problems in training
    allow_benchmark_hard_data: bool = False
    allow_gsm8k_test_hard_fallback: bool = False

    # REPRODUCIBILITY (Issue #2)
    seed: int = 42

    # REINFORCE BASELINE (Issue #4: Variance reduction)
    use_baseline: bool = True
    baseline_ema_decay: float = 0.9  # EMA for reward baseline
    normalize_advantages: bool = True  # Normalize (r - baseline)

    # MISSING PHASE PENALTY (Issue #6)
    missing_phase_penalty: float = 0.3  # Per missing required phase
    min_phase_chars: int = 30
    min_hypothesis_chars: int = 20

    # CHECKPOINTING (Issue #1)
    save_every_n_steps: int = 200
    save_on_best: bool = True

    # EVALUATION
    eval_every_n_steps: int = 50  # More frequent checks
    num_eval_samples: int = 50
    halt_on_catastrophe: bool = True
    catastrophe_accuracy_drop: float = 20.0

    # LOGGING
    log_every: int = 5
    calibration_every: int = 10

    # OUTPUT
    output_dir: str = "./rl_ocov_v4_checkpoints"

# %%
# ============================================================================
# DIALECTICA PROMPT (same as V1)
# ============================================================================

SYSTEM_PROMPT = """You are a careful mathematical reasoner. Solve the user's problem using the requested DIALECTICA structure."""

TRAINING_USER_TEMPLATE = """Solve this problem using structured reasoning:

{problem}

Use this exact structure with substantive content in every phase:
[DETECT] Decide whether this requires complex reasoning or a simple lookup.
[HYPOTHESIZE]
H1: Give one plausible approach.
H2: Give a genuinely different plausible approach.
[OSCILLATION] Test both H1 and H2, including what works and what fails.
[SYNTHESIZE] Resolve the approaches into a final result.

End with exactly:
Answer: <final answer>"""


# %%
# ============================================================================
# SEMANTIC CAPTURE
# ============================================================================

def _model_device(model) -> torch.device:
    return next(model.parameters()).device


def _adapter_disabled(model):
    """Use the PEFT base model as a frozen reward judge when available."""
    if hasattr(model, "disable_adapter"):
        return model.disable_adapter()
    return nullcontext()


def _hidden_state_for_layer(hidden_states: Tuple[torch.Tensor, ...], layer_idx: int) -> torch.Tensor:
    # Hugging Face returns embeddings at index 0, then transformer block outputs.
    hf_idx = layer_idx + 1
    if hf_idx >= len(hidden_states):
        hf_idx = len(hidden_states) - 1
    return hidden_states[hf_idx]


def masked_mean_pool(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Mean-pool hidden states over real tokens only."""
    mask = attention_mask.to(hidden.device).unsqueeze(-1).to(hidden.dtype)
    denom = mask.sum(dim=1).clamp(min=1.0)
    return (hidden * mask).sum(dim=1) / denom


def extract_first_sentence(text: str) -> str:
    """
    Extract the first meaningful sentence from a section.
    
    V4 note: mean-pooling entire sections can wash out differences because
    both hypothesis and oscillation discuss the same problem. The first
    sentence captures the *framing* ("I'll try algebra" vs "Testing: algebra
    gives...") which is where sections genuinely differ.
    """
    # Strip the phase marker header
    text = re.sub(r'^\[?(?:HYPOTHESIZE|OSCILLATION|SYNTHESIZE|DETECT)\]?\s*:?\s*', '', text.strip(), flags=re.IGNORECASE)
    text = text.strip()
    
    if not text:
        return text
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Take first 1-2 sentences (at least 20 chars to be meaningful)
    result = sentences[0] if sentences else text
    if len(result) < 20 and len(sentences) > 1:
        result = ' '.join(sentences[:2])
    
    # Cap at ~150 chars to keep it focused
    if len(result) > 150:
        result = result[:150]
    
    return result


def get_text_embeddings(
    texts: List[str],
    model,
    tokenizer,
    layers: List[int],
    max_length: int = 512,
) -> Dict[int, torch.Tensor]:
    """
    Get frozen-judge embeddings for multiple texts and layers in one forward.

    V4 uses output_hidden_states instead of forward hooks so multi-layer
    calibration is effectively free once the judge forward has been paid.
    """
    if not texts:
        return {layer: torch.empty(0, device=_model_device(model)) for layer in layers}

    inputs = tokenizer(
        [text if text and text.strip() else " " for text in texts],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=max_length
    ).to(_model_device(model))

    was_training = model.training
    model.eval()
    try:
        with torch.no_grad(), _adapter_disabled(model):
            outputs = model(
                **inputs,
                output_hidden_states=True,
                use_cache=False,
                return_dict=True,
            )
    finally:
        model.train(was_training)

    embeddings = {}
    for layer_idx in layers:
        hidden = _hidden_state_for_layer(outputs.hidden_states, layer_idx)
        embeddings[layer_idx] = masked_mean_pool(hidden, inputs["attention_mask"]).detach()
    return embeddings


def get_multi_layer_similarity(
    text_a: str,
    text_b: str,
    model,
    tokenizer,
    layers: List[int],
    first_sentence_only: bool = False
) -> Dict[int, float]:
    """
    Compute cosine similarity between two texts at multiple layers.
    Used for calibration logging — helps find the optimal analysis layer.
    """
    if first_sentence_only:
        text_a = extract_first_sentence(text_a)
        text_b = extract_first_sentence(text_b)

    embeddings = get_text_embeddings([text_a, text_b], model, tokenizer, layers)
    similarities = {}
    for layer_idx in layers:
        layer_embs = embeddings[layer_idx]
        similarities[layer_idx] = F.cosine_similarity(
            layer_embs[0].unsqueeze(0), layer_embs[1].unsqueeze(0)
        ).item()
    return similarities


# %%
# ============================================================================
# ANSWER NORMALIZATION AND EQUIVALENCE
# ============================================================================

def _extract_braced_command(text: str, command: str) -> Optional[str]:
    start = text.find(command)
    if start < 0:
        return None
    brace_start = text.find("{", start + len(command))
    if brace_start < 0:
        return None

    depth = 0
    for idx in range(brace_start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1:idx]
    return None


def normalize_answer_text(answer: Any) -> str:
    """Normalize answer text without destroying math structure."""
    text = "" if answer is None else str(answer)
    text = text.strip()

    if "####" in text:
        text = text.split("####")[-1].strip()

    boxed = _extract_braced_command(text, r"\boxed")
    if boxed:
        text = boxed

    text = re.sub(r"(?i)^(?:the\s+)?(?:final\s+)?answer\s*(?:is|=|:)\s*", "", text)
    text = text.strip().strip("$").strip()
    text = text.replace("\\\\", "\\")
    text = text.replace(r"\left", "").replace(r"\right", "")
    text = text.replace(r"\,", "").replace(r"\!", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,\n\t")


def extract_final_answer(text: str) -> str:
    """Extract the final answer from generated text."""
    if not text:
        return ""

    answer_match = re.search(
        r"(?is)(?:^|\n)\s*(?:final\s+answer|answer)\s*:\s*(.+?)(?:\n|$)",
        text,
    )
    if answer_match:
        return normalize_answer_text(answer_match.group(1))

    if "####" in text:
        return normalize_answer_text(text.split("####")[-1])

    boxed = _extract_braced_command(text, r"\boxed")
    if boxed:
        return normalize_answer_text(boxed)

    # Prefer a final fraction/number if no explicit delimiter was produced.
    candidates = re.findall(
        r"\\frac\s*\{[^{}]+\}\s*\{[^{}]+\}|-?\d[\d,]*(?:\.\d+)?(?:\s*/\s*-?\d[\d,]*(?:\.\d+)?)?",
        text,
    )
    if candidates:
        return normalize_answer_text(candidates[-1])

    return normalize_answer_text(text)


def _as_fraction(text: str) -> Optional[Fraction]:
    text = normalize_answer_text(text)
    text = text.replace(",", "").strip()

    frac_match = re.fullmatch(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", text)
    if frac_match:
        try:
            return Fraction(frac_match.group(1).strip()) / Fraction(frac_match.group(2).strip())
        except (ValueError, ZeroDivisionError):
            return None

    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def _math_verify_equal(generated: str, expected: str) -> Optional[bool]:
    try:
        from math_verify import parse, verify
    except ImportError:
        return None

    try:
        parsed_generated = parse(generated)
        parsed_expected = parse(expected)
        if parsed_generated and parsed_expected:
            return bool(verify(parsed_generated, parsed_expected))
    except Exception:
        return None
    return None


def _sympy_equal(generated: str, expected: str) -> Optional[bool]:
    try:
        import sympy as sp
    except ImportError:
        return None

    def to_expr(text: str):
        expr = normalize_answer_text(text)
        expr = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", expr)
        expr = expr.replace("^", "**")
        expr = expr.replace(r"\pi", "pi")
        expr = expr.replace("{", "(").replace("}", ")")
        return sp.sympify(expr)

    try:
        gen_expr = to_expr(generated)
        exp_expr = to_expr(expected)
        diff = sp.simplify(gen_expr - exp_expr)
        if diff == 0:
            return True
        return bool(abs(float(diff)) < 1e-8)
    except Exception:
        return None


def answers_equivalent(generated: str, expected: str) -> bool:
    gen = normalize_answer_text(generated)
    exp = normalize_answer_text(expected)

    if not gen or not exp:
        return False

    if gen.lower() == exp.lower():
        return True

    math_verify_result = _math_verify_equal(gen, exp)
    if math_verify_result is True:
        return True

    gen_frac = _as_fraction(gen)
    exp_frac = _as_fraction(exp)
    if gen_frac is not None and exp_frac is not None:
        return gen_frac == exp_frac

    sympy_result = _sympy_equal(gen, exp)
    if sympy_result is not None:
        return sympy_result

    compact_gen = re.sub(r"\s+", "", gen.lower())
    compact_exp = re.sub(r"\s+", "", exp.lower())
    return compact_gen == compact_exp

# %%
# ============================================================================
# DATA LOADING (with accessible datasets)
# ============================================================================

def question_key(question: str) -> str:
    return re.sub(r"\s+", " ", question or "").strip().lower()


GSM8K_DATASET_CANDIDATES = ("openai/gsm8k", "gsm8k")


def load_hf_gsm8k_split(split: str):
    """Load GSM8K from HF across old/new dataset ids."""
    from datasets import load_dataset

    errors = []
    for dataset_id in GSM8K_DATASET_CANDIDATES:
        try:
            print(f"Loading GSM8K {split} split from HuggingFace ({dataset_id})...")
            return load_dataset(dataset_id, "main", split=split)
        except Exception as e:
            errors.append(f"{dataset_id}: {type(e).__name__}: {e}")
            print(f"  GSM8K load failed for {dataset_id}: {type(e).__name__}: {e}")

    raise RuntimeError("Could not load GSM8K from HuggingFace. Tried: " + " | ".join(errors))


def load_gsm8k_data(
    path: str = None,
    num_samples: int = None,
    split: str = "train",
    source_label: str = None,
) -> List[Dict]:
    """Load GSM8K dataset - supports local JSONL or HuggingFace download"""
    
    processed = []
    source = source_label or f"gsm8k_{split}"
    
    # Try local file first
    if path and os.path.exists(path):
        print(f"Loading GSM8K from local file: {path}")
        with open(path, 'r') as f:
            for idx, line in enumerate(f):
                item = json.loads(line)
                answer_text = item.get("answer", "")
                if "####" in answer_text:
                    final_answer = normalize_answer_text(answer_text.split("####")[-1])
                else:
                    final_answer = extract_final_answer(answer_text)

                processed.append({
                    "id": f"{source}:{idx}",
                    "question": item["question"],
                    "answer": final_answer,
                    "full_solution": answer_text,
                    "difficulty": 1,
                    "source": source
                })
    else:
        # Fallback to HuggingFace download
        dataset = load_hf_gsm8k_split(split)

        for idx, item in enumerate(dataset):
            answer_text = item.get("answer", "")
            if "####" in answer_text:
                final_answer = normalize_answer_text(answer_text.split("####")[-1])
            else:
                final_answer = extract_final_answer(answer_text)

            processed.append({
                "id": f"{source}:{idx}",
                "question": item["question"],
                "answer": final_answer,
                "full_solution": answer_text,
                "difficulty": 1,
                "source": source
            })

    if num_samples:
        processed = processed[:num_samples]

    print(f"Loaded {len(processed)} GSM8K examples")
    return processed


def load_harder_math_data(
    path: str = None,
    num_samples: int = 200,
    exclude_questions: Optional[set] = None,
    allow_benchmark_hard_data: bool = False,
    allow_gsm8k_test_fallback: bool = False,
) -> List[Dict]:
    """
    Load harder math problems - supports local MATH-500 JSONL or HuggingFace download
    
    Primary: local math_500.jsonl (if path provided)
    Fallback 1: HuggingFace MATH-500
    Fallback 2: GSM8K test set
    Fallback 3: synthetic problems
    """
    
    processed = []
    excluded = exclude_questions or set()

    def maybe_add(item: Dict) -> bool:
        if question_key(item.get("question", "")) in excluded:
            return False
        item.setdefault("id", f"{item.get('source', 'hard')}:{len(processed)}")
        processed.append(item)
        return True

    # Try local MATH-500 file first
    if allow_benchmark_hard_data and path and os.path.exists(path):
        print(f"Loading MATH-500 from local file: {path}")
        try:
            with open(path, 'r') as f:
                for idx, line in enumerate(f):
                    if len(processed) >= num_samples:
                        break
                    item = json.loads(line)
                    maybe_add({
                        "id": f"math500_local:{idx}",
                        "question": item.get("problem", item.get("question", "")),
                        "answer": normalize_answer_text(item.get("answer", "")),
                        "full_solution": item.get("solution", ""),
                        "difficulty": item.get("level", 3),
                        "source": "math500_local"
                    })
            print(f"Loaded {len(processed)} MATH-500 examples from local file")
        except Exception as e:
            print(f"Failed to load local MATH-500: {e}")

    # Fallback 1: Try HuggingFace MATH-500 only when benchmark training is explicit.
    if allow_benchmark_hard_data and len(processed) < num_samples:
        try:
            from datasets import load_dataset
            print("Trying HuggingFace MATH-500 dataset...")
            dataset = load_dataset("HuggingFaceH4/MATH-500", split="test")

            for idx, item in enumerate(dataset):
                if len(processed) >= num_samples:
                    break
                maybe_add({
                    "id": f"math500_hf:{idx}",
                    "question": item.get("problem", ""),
                    "answer": normalize_answer_text(item.get("answer", "")),
                    "full_solution": item.get("solution", ""),
                    "difficulty": item.get("level", 3),
                    "source": "math500_hf"
                })
            print(f"Loaded {len(processed)} MATH-500 examples from HuggingFace")

        except Exception as e:
            print(f"HuggingFace MATH-500 failed: {e}")

    # Fallback 2: Try GSM8K test set (harder than train)
    if allow_gsm8k_test_fallback and len(processed) < num_samples:
        try:
            print("Trying GSM8K test set as harder problems...")
            dataset = load_hf_gsm8k_split("test")

            for idx, item in enumerate(dataset):
                if len(processed) >= num_samples:
                    break
                answer_text = item.get("answer", "")
                if "####" in answer_text:
                    final_answer = normalize_answer_text(answer_text.split("####")[-1])
                else:
                    final_answer = extract_final_answer(answer_text)

                maybe_add({
                    "id": f"gsm8k_test_hard:{idx}",
                    "question": item["question"],
                    "answer": final_answer,
                    "difficulty": 2,
                    "source": "gsm8k_test"
                })

            print(f"Total examples: {len(processed)}")

        except Exception as e:
            print(f"GSM8K test failed: {e}")

    # Fallback 3: Add synthetic olympiad-style problems
    if len(processed) < num_samples:
        print("Adding synthetic hard problems...")
        synthetic = generate_synthetic_hard_problems(
            num_samples - len(processed),
            exclude_questions=excluded,
        )
        processed.extend(synthetic)

    return processed


def generate_synthetic_hard_problems(n: int, exclude_questions: Optional[set] = None) -> List[Dict]:
    """Generate synthetic hard problems that require multi-step reasoning"""
    excluded = exclude_questions or set()

    problems = [
        {
            "question": "Find the sum of all positive integers n such that n² + 12n - 2007 is a perfect square.",
            "answer": "1464",
            "difficulty": 3
        },
        {
            "question": "How many ordered pairs of positive integers (a,b) satisfy 1/a + 1/b = 1/20?",
            "answer": "15",
            "difficulty": 3
        },
        {
            "question": "In triangle ABC, AB=13, BC=14, CA=15. Find the length of the altitude from A to BC.",
            "answer": "12",
            "difficulty": 3
        },
        {
            "question": "Find the last three digits of 7^999.",
            "answer": "143",
            "difficulty": 3
        },
        {
            "question": "How many positive integers less than 1000 are divisible by neither 5 nor 7?",
            "answer": "686",
            "difficulty": 3
        },
        {
            "question": "A sequence is defined by a₁=1, a₂=2, and aₙ=aₙ₋₁+aₙ₋₂ for n≥3. Find a₁₀.",
            "answer": "89",
            "difficulty": 2
        },
        {
            "question": "Find the sum of all prime factors of 2310.",
            "answer": "28",
            "difficulty": 2
        },
        {
            "question": "If x + 1/x = 5, find x² + 1/x².",
            "answer": "23",
            "difficulty": 2
        },
        {
            "question": "How many 4-digit numbers have all distinct digits?",
            "answer": "4536",
            "difficulty": 2
        },
        {
            "question": "Find the GCD of 48 and 180.",
            "answer": "12",
            "difficulty": 1
        },
    ]

    result = []
    i = 0
    attempts = 0
    max_attempts = max(n * len(problems) * 2, len(problems))
    while len(result) < n and attempts < max_attempts:
        prob = problems[i % len(problems)].copy()
        i += 1
        attempts += 1
        if question_key(prob["question"]) in excluded:
            continue
        prob["id"] = f"synthetic:{len(result)}"
        prob["source"] = "synthetic"
        result.append(prob)

    return result


def generate_synthetic_eval_problems(n: int) -> List[Dict]:
    """Small verified eval fallback, separate from synthetic training problems."""
    problems = [
        {
            "question": "What is the remainder when 2^20 is divided by 1000?",
            "answer": "576",
            "difficulty": 3,
        },
        {
            "question": "How many positive divisors does 360 have?",
            "answer": "24",
            "difficulty": 2,
        },
        {
            "question": "If a fair coin is flipped 6 times, how many possible sequences have exactly 4 heads?",
            "answer": "15",
            "difficulty": 2,
        },
        {
            "question": "Find the area of a triangle with side lengths 5, 5, and 6.",
            "answer": "12",
            "difficulty": 2,
        },
        {
            "question": "Solve for x: 3x + 7 = 31.",
            "answer": "8",
            "difficulty": 1,
        },
        {
            "question": "What is the sum of the first 20 positive integers?",
            "answer": "210",
            "difficulty": 1,
        },
        {
            "question": "How many integers from 1 to 100 inclusive are divisible by 3 or 5?",
            "answer": "47",
            "difficulty": 2,
        },
        {
            "question": "If x + y = 10 and xy = 21, find x^2 + y^2.",
            "answer": "58",
            "difficulty": 2,
        },
        {
            "question": "What is the last digit of 3^2026?",
            "answer": "9",
            "difficulty": 2,
        },
        {
            "question": "A rectangle has perimeter 50 and length 15. What is its area?",
            "answer": "150",
            "difficulty": 1,
        },
    ]

    result = []
    for i in range(n):
        prob = problems[i % len(problems)].copy()
        prob["id"] = f"synthetic_eval:{i}"
        prob["source"] = "synthetic_eval"
        result.append(prob)
    return result


# %%
# ============================================================================
# REWARD CALCULATOR (V4 shaped resonance reward)
# ============================================================================

class OCovRewardCalculator:
    """
    Reward model for O-CoV training:
    - terminal answer correctness using math-aware equivalence,
    - phase structure with minimum content checks,
    - frozen base-model geometry over H1/H2/oscillation/problem embeddings.
    """

    def __init__(self, model, tokenizer, config: TrainingConfigV4):
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.device = next(model.parameters()).device

        self.phases = ["DETECT", "HYPOTHESIZE", "OSCILLATION", "SYNTHESIZE"]

        self.similarity_history = []
        self.hypothesis_similarity_history = []
        self.goldilocks_history = []
        self.accuracy_history = []
        self.multi_layer_history = {layer: [] for layer in config.analysis_layers_to_log}
        self.embedding_centers: Dict[int, torch.Tensor] = {}
        self.pending_center_updates: List[Dict[int, torch.Tensor]] = []
        self.reward_calls = 0

    def extract_answer(self, text: str) -> str:
        return extract_final_answer(text)

    def check_accuracy(self, generated: str, expected: str) -> float:
        gen_answer = self.extract_answer(generated)
        if answers_equivalent(gen_answer, expected):
            return self.config.correctness_weight
        return -1.0

    def _phase_marker_present(self, text: str, phase: str) -> bool:
        text_upper = text.upper()
        patterns = [f"[{phase}]", f"**{phase}**", f"{phase}:", f"## {phase}"]
        return any(pattern.upper() in text_upper for pattern in patterns)

    def _strip_phase_label(self, section: str, phase: str) -> str:
        return re.sub(
            rf"^\s*(?:\[?{phase}\]?|\*\*{phase}\*\*|##\s*{phase})\s*:?\s*",
            "",
            section.strip(),
            flags=re.IGNORECASE,
        ).strip()

    def extract_sections(self, text: str) -> Dict[str, str]:
        sections = {"detect": "", "hypothesis": "", "oscillation": "", "synthesize": ""}
        text_upper = text.upper()
        phase_specs = [
            ("detect", ["DETECT"], ["HYPOTHESIZE", "OSCILLATION", "SYNTHESIZE", "SYNTHESIS", "ANSWER"]),
            ("hypothesis", ["HYPOTHESIZE"], ["OSCILLATION", "SYNTHESIZE", "SYNTHESIS", "ANSWER"]),
            ("oscillation", ["OSCILLATION"], ["SYNTHESIZE", "SYNTHESIS", "ANSWER"]),
            ("synthesize", ["SYNTHESIZE", "SYNTHESIS"], ["ANSWER"]),
        ]

        for section_name, markers, next_markers in phase_specs:
            starts = [(text_upper.find(marker), marker) for marker in markers if marker in text_upper]
            starts = [(idx, marker) for idx, marker in starts if idx >= 0]
            if not starts:
                continue
            start, marker = min(starts, key=lambda item: item[0])
            end = len(text)
            for next_marker in next_markers:
                idx = text_upper.find(next_marker, start + len(marker))
                if idx > 0:
                    end = min(end, idx)
            sections[section_name] = self._strip_phase_label(text[start:end], marker)

        return sections

    def extract_hypotheses(self, hypothesis_section: str) -> Tuple[str, str]:
        h1_match = re.search(r"(?is)(?:^|\n)\s*(?:\*\*)?H1(?:\*\*)?\s*:\s*", hypothesis_section)
        h2_match = re.search(r"(?is)(?:^|\n)\s*(?:\*\*)?H2(?:\*\*)?\s*:\s*", hypothesis_section)

        if not h1_match or not h2_match or h2_match.start() <= h1_match.start():
            return "", ""

        h1 = hypothesis_section[h1_match.end():h2_match.start()].strip()
        h2 = hypothesis_section[h2_match.end():].strip()
        h2 = re.split(r"(?is)\n\s*(?:\[?OSCILLATION\]?|\[?SYNTHESIZE\]?)", h2)[0].strip()
        return h1, h2

    def check_structure(self, text: str) -> Tuple[float, Dict[str, bool]]:
        sections = self.extract_sections(text)
        h1, h2 = self.extract_hypotheses(sections["hypothesis"])

        found = {
            "DETECT": (
                self._phase_marker_present(text, "DETECT") and
                len(sections["detect"]) >= self.config.min_phase_chars
            ),
            "HYPOTHESIZE": (
                self._phase_marker_present(text, "HYPOTHESIZE") and
                len(sections["hypothesis"]) >= self.config.min_phase_chars
            ),
            "OSCILLATION": (
                self._phase_marker_present(text, "OSCILLATION") and
                len(sections["oscillation"]) >= self.config.min_phase_chars
            ),
            "SYNTHESIZE": (
                (self._phase_marker_present(text, "SYNTHESIZE") or self._phase_marker_present(text, "SYNTHESIS")) and
                len(sections["synthesize"]) >= self.config.min_phase_chars
            ),
            "HYPOTHESES": (
                len(h1) >= self.config.min_hypothesis_chars and
                len(h2) >= self.config.min_hypothesis_chars
            ),
        }

        phase_score = sum(found.values()) / len(found)
        return phase_score * self.config.structure_weight, found

    def _update_embedding_centers(self, embeddings_by_layer: Dict[int, torch.Tensor]):
        momentum = self.config.embedding_center_momentum
        for layer_idx, embeddings in embeddings_by_layer.items():
            batch_mean = embeddings.detach().mean(dim=0)
            if layer_idx not in self.embedding_centers:
                self.embedding_centers[layer_idx] = batch_mean
            else:
                self.embedding_centers[layer_idx] = (
                    momentum * self.embedding_centers[layer_idx] +
                    (1.0 - momentum) * batch_mean
                ).detach()

    def flush_embedding_center_updates(self):
        """Update running centers after a batch so rewards do not center on themselves."""
        if not self.pending_center_updates:
            return

        combined = {}
        for update in self.pending_center_updates:
            for layer_idx, embeddings in update.items():
                combined.setdefault(layer_idx, []).append(embeddings.detach())

        self._update_embedding_centers({
            layer_idx: torch.cat(layer_embeddings, dim=0)
            for layer_idx, layer_embeddings in combined.items()
        })
        self.pending_center_updates.clear()

    def _center(self, layer_idx: int, embeddings: torch.Tensor) -> torch.Tensor:
        center = self.embedding_centers.get(layer_idx)
        if center is None:
            return embeddings
        return embeddings - center.to(embeddings.device, dtype=embeddings.dtype)

    def _cosine(self, a: torch.Tensor, b: torch.Tensor) -> float:
        return F.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0), dim=-1).item()

    def _gaussian_bump(self, value: float, target: float) -> float:
        sigma = max(self.config.resonance_sigma, 1e-6)
        return math.exp(-0.5 * ((value - target) / sigma) ** 2)

    def calculate_resonance(
        self,
        text: str,
        problem_text: str,
        update_stats: bool = True,
        use_centers: bool = True,
    ) -> Tuple[float, Dict]:
        sections = self.extract_sections(text)
        h1_text, h2_text = self.extract_hypotheses(sections["hypothesis"])
        osc_text = sections["oscillation"]

        metrics = {
            "hyp_osc_similarity": None,
            "hyp_hyp_similarity": None,
            "osc_h1_similarity": None,
            "osc_h2_similarity": None,
            "problem_anchor_similarity": None,
            "distinct_score": 0.0,
            "engagement_score": 0.0,
            "in_goldilocks": False,
            "drift": 0.0,
            "multi_layer_sim": {},
        }

        if (
            len(h1_text) < self.config.min_hypothesis_chars or
            len(h2_text) < self.config.min_hypothesis_chars or
            len(osc_text) < self.config.min_phase_chars
        ):
            return 0.0, metrics

        layers = [self.config.analysis_layer]
        should_log_layers = update_stats and (self.reward_calls % self.config.calibration_every == 0)
        if should_log_layers:
            layers = sorted(set(layers + self.config.analysis_layers_to_log))

        embedding_texts = [h1_text, h2_text, osc_text, problem_text, text]
        embeddings_by_layer = get_text_embeddings(
            embedding_texts,
            self.model,
            self.tokenizer,
            layers,
        )

        if update_stats:
            self.pending_center_updates.append({
                layer_idx: embeddings.detach()
                for layer_idx, embeddings in embeddings_by_layer.items()
            })

        primary_raw = embeddings_by_layer[self.config.analysis_layer]
        primary = self._center(self.config.analysis_layer, primary_raw) if use_centers else primary_raw
        h1_emb, h2_emb, osc_emb, problem_emb, full_emb = primary

        hyp_hyp_similarity = self._cosine(h1_emb, h2_emb)
        osc_h1_similarity = self._cosine(osc_emb, h1_emb)
        osc_h2_similarity = self._cosine(osc_emb, h2_emb)
        hyp_osc_similarity = (osc_h1_similarity + osc_h2_similarity) / 2.0
        anchor_similarity = float(np.mean([
            self._cosine(h1_emb, problem_emb),
            self._cosine(h2_emb, problem_emb),
            self._cosine(osc_emb, problem_emb),
            self._cosine(full_emb, problem_emb),
        ]))

        distinct_score = self._gaussian_bump(
            hyp_hyp_similarity,
            self.config.hypothesis_distinct_target,
        )
        engage_h1 = self._gaussian_bump(
            osc_h1_similarity,
            self.config.oscillation_engagement_target,
        )
        engage_h2 = self._gaussian_bump(
            osc_h2_similarity,
            self.config.oscillation_engagement_target,
        )
        engagement_score = 0.5 * ((engage_h1 + engage_h2) / 2.0 + min(engage_h1, engage_h2))
        drift = max(0.0, self.config.problem_anchor_min - anchor_similarity)

        resonance_score = 0.45 * distinct_score + 0.55 * engagement_score
        resonance_reward = self.config.resonance_reward * resonance_score
        resonance_reward -= self.config.drift_penalty_weight * drift

        in_goldilocks = (
            distinct_score >= 0.5 and
            engagement_score >= 0.5 and
            drift <= 0.05
        )

        metrics.update({
            "hyp_osc_similarity": hyp_osc_similarity,
            "hyp_hyp_similarity": hyp_hyp_similarity,
            "osc_h1_similarity": osc_h1_similarity,
            "osc_h2_similarity": osc_h2_similarity,
            "problem_anchor_similarity": anchor_similarity,
            "distinct_score": distinct_score,
            "engagement_score": engagement_score,
            "in_goldilocks": in_goldilocks,
            "drift": drift,
        })

        if should_log_layers:
            for layer_idx, layer_embs in embeddings_by_layer.items():
                centered = self._center(layer_idx, layer_embs) if use_centers else layer_embs
                layer_h1, layer_h2, layer_osc, _, _ = centered
                layer_sim = {
                    "h1_h2": self._cosine(layer_h1, layer_h2),
                    "osc_h1": self._cosine(layer_osc, layer_h1),
                    "osc_h2": self._cosine(layer_osc, layer_h2),
                }
                layer_sim["osc_mean"] = (layer_sim["osc_h1"] + layer_sim["osc_h2"]) / 2.0
                metrics["multi_layer_sim"][layer_idx] = layer_sim
                self.multi_layer_history.setdefault(layer_idx, []).append(layer_sim["osc_mean"])

        if update_stats:
            self.similarity_history.append(hyp_osc_similarity)
            self.hypothesis_similarity_history.append(hyp_hyp_similarity)
            self.goldilocks_history.append(in_goldilocks)
            self.reward_calls += 1

        return resonance_reward, metrics

    def calculate_reward(
        self,
        generated_text: str,
        expected_answer: str,
        problem_text: str,
        update_stats: bool = True,
        use_centers: bool = True,
    ) -> Tuple[float, Dict]:
        accuracy_reward = self.check_accuracy(generated_text, expected_answer)
        if update_stats:
            self.accuracy_history.append(accuracy_reward > 0)

        structure_reward, structure_details = self.check_structure(generated_text)
        resonance_reward, resonance_metrics = self.calculate_resonance(
            generated_text,
            problem_text,
            update_stats=update_stats,
            use_centers=use_centers,
        )

        total_reward = accuracy_reward + structure_reward + resonance_reward
        if accuracy_reward < 0:
            total_reward = min(total_reward, self.config.wrong_answer_max_reward)

        metrics = {
            "total_reward": total_reward,
            "accuracy_reward": accuracy_reward,
            "structure_reward": structure_reward,
            "resonance_reward": resonance_reward,
            "structure_found": structure_details,
            "extracted_answer": self.extract_answer(generated_text),
            **resonance_metrics,
        }

        return total_reward, metrics

    def get_stats(self) -> Dict:
        stats = {}

        if self.similarity_history:
            sims = self.similarity_history[-100:]
            stats["sim_mean"] = sum(sims) / len(sims)
            stats["sim_min"] = min(sims)
            stats["sim_max"] = max(sims)

        if self.hypothesis_similarity_history:
            h_sims = self.hypothesis_similarity_history[-100:]
            stats["h1_h2_sim_mean"] = sum(h_sims) / len(h_sims)

        if self.goldilocks_history:
            recent = self.goldilocks_history[-100:]
            stats["goldilocks_rate"] = sum(recent) / len(recent)

        if self.accuracy_history:
            stats["accuracy"] = sum(self.accuracy_history[-100:]) / min(100, len(self.accuracy_history))

        for layer_idx, layer_sims in self.multi_layer_history.items():
            if layer_sims:
                recent = layer_sims[-20:]
                stats[f"sim_L{layer_idx}_mean"] = sum(recent) / len(recent)
                stats[f"sim_L{layer_idx}_min"] = min(recent)
                stats[f"sim_L{layer_idx}_max"] = max(recent)

        return stats

# %%
# ============================================================================
# TRAINER (with warmup and catastrophe detection)
# ============================================================================

class RLOCovTrainerV4:
    """RL trainer with K-sample group baselines and base-policy KL guardrails."""

    def __init__(self, model, tokenizer, config: TrainingConfigV4):
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.device = next(model.parameters()).device

        self.reward_calc = OCovRewardCalculator(model, tokenizer, config)

        trainable_params = [p for p in model.parameters() if p.requires_grad]
        self.optimizer = torch.optim.AdamW(
            trainable_params,
            lr=config.learning_rate,
            weight_decay=0.01,
        )

        total_steps = config.total_training_steps or max(
            1,
            config.num_epochs * math.ceil(config.train_samples / max(config.batch_size, 1)),
        )
        try:
            from transformers import get_linear_schedule_with_warmup
            self.scheduler = get_linear_schedule_with_warmup(
                self.optimizer,
                num_warmup_steps=config.warmup_steps,
                num_training_steps=total_steps,
            )
        except Exception:
            self.scheduler = None

        self.global_step = 0
        self.best_accuracy = 0
        self.initial_accuracy = None
        self.reward_baseline = 0.0
        self.data_manifest = {}

        self.history = {
            "step": [], "loss": [], "reward": [], "advantage": [],
            "accuracy": [], "structure": [], "resonance": [],
            "goldilocks_rate": [], "similarity": [], "missing_phases": [],
            "grad_norm": [], "entropy": [], "kl": [], "lr": [],
        }
        self.metrics_log = []

    def save_checkpoint(self, path: str, is_best: bool = False):
        """Save LoRA adapter, tokenizer, config, data manifest, and metrics."""
        os.makedirs(path, exist_ok=True)

        adapter_path = os.path.join(path, "adapter")
        self.model.save_pretrained(adapter_path)
        print(f"  ✓ Saved LoRA adapter to {adapter_path}")

        tokenizer_path = os.path.join(path, "tokenizer")
        self.tokenizer.save_pretrained(tokenizer_path)
        print(f"  ✓ Saved tokenizer to {tokenizer_path}")

        config_snapshot = {
            "config": asdict(self.config),
            "versions": get_version_info(),
            "global_step": self.global_step,
            "best_accuracy": self.best_accuracy,
            "initial_accuracy": self.initial_accuracy,
            "reward_baseline": self.reward_baseline,
            "data_manifest": self.data_manifest,
            "timestamp": datetime.now().isoformat(),
            "is_best": is_best,
        }
        config_path = os.path.join(path, "config_snapshot.json")
        with open(config_path, "w") as f:
            json.dump(config_snapshot, f, indent=2, default=str)
        print(f"  ✓ Saved config snapshot to {config_path}")

        metrics_path = os.path.join(path, "metrics.jsonl")
        with open(metrics_path, "w") as f:
            for entry in self.metrics_log:
                f.write(json.dumps(entry) + "\n")
        print(f"  ✓ Saved {len(self.metrics_log)} metric entries to {metrics_path}")

    def format_prompt(self, problem: str) -> str:
        user_prompt = TRAINING_USER_TEMPLATE.format(problem=problem)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                pass

        return f"System: {SYSTEM_PROMPT}\n\nUser: {user_prompt}\n\nAssistant:"

    def _tokenize_prompt(self, prompt: str):
        max_prompt_length = max(32, self.config.max_seq_length - self.config.max_new_tokens)
        return self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=max_prompt_length,
        ).to(self.device)

    def generate(self, prompt: str, do_sample: bool = True) -> Tuple[str, torch.Tensor, int]:
        """Generate response and return the exact prompt length used."""
        inputs = self._tokenize_prompt(prompt)
        was_training = self.model.training
        self.model.eval()

        generation_kwargs = {
            **inputs,
            "max_new_tokens": self.config.max_new_tokens,
            "do_sample": do_sample,
            "pad_token_id": self.tokenizer.pad_token_id,
            "return_dict_in_generate": True,
        }
        if do_sample:
            generation_kwargs["temperature"] = 0.7

        try:
            with torch.no_grad():
                outputs = self.model.generate(**generation_kwargs)
        finally:
            self.model.train(was_training)

        generated_ids = outputs.sequences[0]
        prompt_length = inputs.input_ids.shape[1]
        generated_text = self.tokenizer.decode(
            generated_ids[prompt_length:],
            skip_special_tokens=True,
        )

        return generated_text, generated_ids, prompt_length

    def _mask_generated_tokens(self, sequence_len: int, prompt_length: int, device) -> torch.Tensor:
        mask = torch.zeros(sequence_len - 1, device=device)
        gen_start = max(0, prompt_length - 1)
        mask[gen_start:] = 1.0
        if self.global_step == 0:
            print(
                f"  [DEBUG] prompt_length={prompt_length}, seq_len={sequence_len}, "
                f"mask_start={gen_start}, masked_tokens={int(mask.sum().item())}"
            )
        return mask

    def compute_policy_gradient_loss(
        self,
        full_sequence: torch.Tensor,
        prompt_length: int,
        advantage: float,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """REINFORCE loss with masked entropy and KL-to-base monitoring."""
        was_training = self.model.training
        self.model.eval()

        try:
            outputs = self.model(full_sequence.unsqueeze(0), use_cache=False)
            logits = outputs.logits

            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = full_sequence[1:].contiguous()
            log_probs = F.log_softmax(shift_logits, dim=-1)
            token_log_probs = log_probs[0, torch.arange(len(shift_labels), device=self.device), shift_labels]

            mask = self._mask_generated_tokens(len(full_sequence), prompt_length, token_log_probs.device)
            mask_sum = mask.sum().clamp(min=1.0)
            mean_log_prob = (token_log_probs * mask).sum() / mask_sum

            clamped_advantage = max(-5.0, min(5.0, float(advantage)))
            policy_loss = -clamped_advantage * mean_log_prob

            probs = F.softmax(shift_logits[0], dim=-1)
            entropy = -(probs * log_probs[0]).sum(dim=-1)
            masked_entropy = (entropy * mask).sum() / mask_sum

            kl_value = torch.zeros((), device=self.device, dtype=logits.dtype)
            if hasattr(self.model, "disable_adapter"):
                with torch.no_grad(), _adapter_disabled(self.model):
                    base_outputs = self.model(full_sequence.unsqueeze(0), use_cache=False)
                    base_log_probs = F.log_softmax(base_outputs.logits[..., :-1, :].contiguous(), dim=-1)
                token_kl = (probs * (log_probs[0] - base_log_probs[0])).sum(dim=-1)
                kl_value = (token_kl * mask).sum() / mask_sum

            loss = (
                policy_loss
                - self.config.entropy_coef * masked_entropy
                + self.config.kl_coef * kl_value
            )

            return loss, {
                "advantage": clamped_advantage,
                "entropy": masked_entropy.detach().float().item(),
                "kl": kl_value.detach().float().item(),
                "mean_log_prob": mean_log_prob.detach().float().item(),
            }
        finally:
            self.model.train(was_training)

    def _group_advantages(self, rewards: List[float]) -> List[float]:
        if not rewards:
            return []
        if not self.config.use_baseline:
            return rewards

        old_ema_baseline = self.reward_baseline
        group_mean = float(np.mean(rewards))
        if len(rewards) > 1:
            reward_sum = float(sum(rewards))
            advantages = [
                reward - ((reward_sum - reward) / (len(rewards) - 1))
                for reward in rewards
            ]
        else:
            advantages = [rewards[0] - old_ema_baseline]

        if self.config.normalize_advantages and len(rewards) > 1:
            group_std = float(np.std(advantages)) + 1e-8
            advantages = [adv / group_std for adv in advantages]

        self.reward_baseline = (
            self.config.baseline_ema_decay * self.reward_baseline +
            (1 - self.config.baseline_ema_decay) * group_mean
        )
        return advantages

    def _apply_missing_phase_penalty(self, reward: float, metrics: Dict) -> Tuple[float, int]:
        missing_phases = sum(1 for found in metrics["structure_found"].values() if not found)
        phase_penalty = missing_phases * self.config.missing_phase_penalty
        reward -= phase_penalty
        metrics["missing_phase_penalty"] = phase_penalty
        metrics["total_reward"] = reward
        return reward, missing_phases

    def train_batch(self, batch_items: List[Dict]) -> Dict:
        """Train on several prompts, each with K sampled completions."""
        self.optimizer.zero_grad(set_to_none=True)

        sample_records = []
        total_samples = max(1, len(batch_items) * self.config.group_size)

        for item in batch_items:
            prompt = self.format_prompt(item["question"])
            prompt_samples = []
            rewards = []

            for _ in range(self.config.group_size):
                generated_text, full_sequence, prompt_length = self.generate(prompt, do_sample=True)
                reward, metrics = self.reward_calc.calculate_reward(
                    generated_text,
                    item["answer"],
                    item["question"],
                    update_stats=True,
                )
                reward, missing_phases = self._apply_missing_phase_penalty(reward, metrics)
                prompt_samples.append({
                    "item": item,
                    "generated_text": generated_text,
                    "full_sequence": full_sequence,
                    "prompt_length": prompt_length,
                    "reward": reward,
                    "metrics": metrics,
                    "missing_phases": missing_phases,
                })
                rewards.append(reward)

            advantages = self._group_advantages(rewards)
            for sample, advantage in zip(prompt_samples, advantages):
                sample["advantage"] = advantage
                sample_records.append(sample)

        self.reward_calc.flush_embedding_center_updates()

        losses = []
        entropies = []
        kls = []
        advantages = []

        for sample in sample_records:
            loss, loss_stats = self.compute_policy_gradient_loss(
                sample["full_sequence"],
                sample["prompt_length"],
                sample["advantage"],
            )
            (loss / total_samples).backward()
            losses.append(loss.detach().float().item())
            entropies.append(loss_stats["entropy"])
            kls.append(loss_stats["kl"])
            advantages.append(loss_stats["advantage"])

        trainable_params = [p for p in self.model.parameters() if p.requires_grad]
        grad_norm = torch.nn.utils.clip_grad_norm_(
            trainable_params,
            max_norm=self.config.max_grad_norm,
        )
        self.optimizer.step()
        if self.scheduler is not None:
            self.scheduler.step()

        self.global_step += 1
        lr = self.optimizer.param_groups[0]["lr"]

        avg_reward = float(np.mean([sample["reward"] for sample in sample_records])) if sample_records else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        avg_advantage = float(np.mean(advantages)) if advantages else 0.0
        avg_entropy = float(np.mean(entropies)) if entropies else 0.0
        avg_kl = float(np.mean(kls)) if kls else 0.0
        avg_missing = float(np.mean([sample["missing_phases"] for sample in sample_records])) if sample_records else 0.0
        avg_accuracy = float(np.mean([sample["metrics"]["accuracy_reward"] for sample in sample_records])) if sample_records else 0.0
        avg_structure = float(np.mean([sample["metrics"]["structure_reward"] for sample in sample_records])) if sample_records else 0.0
        avg_resonance = float(np.mean([sample["metrics"]["resonance_reward"] for sample in sample_records])) if sample_records else 0.0
        goldilocks_rate = float(np.mean([sample["metrics"]["in_goldilocks"] for sample in sample_records])) if sample_records else 0.0

        self.history["step"].append(self.global_step)
        self.history["loss"].append(avg_loss)
        self.history["reward"].append(avg_reward)
        self.history["advantage"].append(avg_advantage)
        self.history["accuracy"].append(avg_accuracy)
        self.history["structure"].append(avg_structure)
        self.history["resonance"].append(avg_resonance)
        self.history["goldilocks_rate"].append(goldilocks_rate)
        self.history["missing_phases"].append(avg_missing)
        self.history["grad_norm"].append(float(grad_norm))
        self.history["entropy"].append(avg_entropy)
        self.history["kl"].append(avg_kl)
        self.history["lr"].append(lr)

        similarities = [
            sample["metrics"].get("hyp_osc_similarity")
            for sample in sample_records
            if sample["metrics"].get("hyp_osc_similarity") is not None
        ]
        if similarities:
            self.history["similarity"].append(float(np.mean(similarities)))

        log_entry = {
            "step": self.global_step,
            "loss": avg_loss,
            "reward": avg_reward,
            "advantage": avg_advantage,
            "entropy": avg_entropy,
            "kl": avg_kl,
            "lr": lr,
            "grad_norm": float(grad_norm),
            "missing_phases": avg_missing,
            "goldilocks_rate": goldilocks_rate,
            "accuracy_reward": avg_accuracy,
            "structure_reward": avg_structure,
            "resonance_reward": avg_resonance,
            "batch_ids": [sample["item"].get("id") for sample in sample_records],
        }
        self.metrics_log.append(log_entry)

        return {
            "loss": avg_loss,
            "reward": avg_reward,
            "advantage": avg_advantage,
            "entropy": avg_entropy,
            "kl": avg_kl,
            "lr": lr,
            "grad_norm": float(grad_norm),
            "metrics": {
                "accuracy_reward": avg_accuracy,
                "structure_reward": avg_structure,
                "resonance_reward": avg_resonance,
                "in_goldilocks": goldilocks_rate > 0,
                "missing_phases": avg_missing,
            },
        }

    def train_step(self, problem: str, expected_answer: str) -> Dict:
        return self.train_batch([{"question": problem, "answer": expected_answer, "id": "single"}])

    def evaluate(self, eval_data: List[Dict], num_samples: int = None) -> Dict:
        """Deterministic, side-effect-free evaluation."""
        was_training = self.model.training
        self.model.eval()

        if num_samples:
            eval_data = eval_data[:min(num_samples, len(eval_data))]

        results = {
            "accuracy": 0, "structure_rate": 0,
            "goldilocks_rate": 0, "avg_reward": 0,
            "similarities": [],
        }

        try:
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(self.config.seed)
                for item in eval_data:
                    prompt = self.format_prompt(item["question"])
                    generated_text, _, _ = self.generate(prompt, do_sample=False)
                    reward, metrics = self.reward_calc.calculate_reward(
                        generated_text,
                        item["answer"],
                        item["question"],
                        update_stats=False,
                        use_centers=False,
                    )
                    reward, _ = self._apply_missing_phase_penalty(reward, metrics)

                    results["accuracy"] += 1 if metrics["accuracy_reward"] > 0 else 0
                    results["structure_rate"] += sum(metrics["structure_found"].values()) / len(metrics["structure_found"])
                    results["goldilocks_rate"] += 1 if metrics["in_goldilocks"] else 0
                    results["avg_reward"] += reward
                    if metrics["hyp_osc_similarity"] is not None:
                        results["similarities"].append(metrics["hyp_osc_similarity"])
        finally:
            self.model.train(was_training)

        n = max(1, len(eval_data))
        results["accuracy"] = results["accuracy"] / n * 100
        results["structure_rate"] = results["structure_rate"] / n * 100
        results["goldilocks_rate"] = results["goldilocks_rate"] / n * 100
        results["avg_reward"] = results["avg_reward"] / n
        return results


# %%
# ============================================================================
# MAIN TRAINING LOOP
# ============================================================================

def main():
    """Main execution with safety checks"""

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    config = TrainingConfigV4()

    # REPRODUCIBILITY (Issue #2)
    set_seed(config.seed)
    versions = get_version_info()

    print("=" * 70)
    print("RL-O-CoV V4: FROZEN CENTERED RESONANCE RL")
    print("   V4 fixes: labels/comparator, chat prompts, K-sample baselines, frozen judge")
    print("   Resonance is shaped over H1/H2 distinctness plus oscillation engagement")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Model: {config.model_name}")
    print(f"  Precision: {'4-bit' if config.use_4bit else 'bfloat16'}")
    print(f"  LoRA rank: {config.lora_r} (V1 had 128)")
    print(f"  LoRA dropout: {config.lora_dropout}")
    print(f"  Learning rate: {config.learning_rate} (V1 had 3e-5)")
    print(f"  Warmup steps: {config.warmup_steps}")
    print(f"  Batch size: {config.batch_size} prompts/step")
    print(f"  Group size: {config.group_size} samples/prompt")
    print(f"  Analysis layer: {config.analysis_layer}")
    print(f"  Resonance targets: H1/H2={config.hypothesis_distinct_target}, "
          f"Osc/H={config.oscillation_engagement_target}, sigma={config.resonance_sigma}")
    print(f"  Multi-layer logging: {config.analysis_layers_to_log}")
    print(f"  Seed: {config.seed}")
    print(f"  Group baseline: {config.use_baseline}")
    print(f"  KL coefficient: {config.kl_coef}")
    print(f"  Checkpoint every: {config.save_every_n_steps} steps")

    print(f"\nVersions:")
    for pkg, ver in versions.items():
        print(f"  {pkg}: {ver}")

    # Load data
    print("\n" + "-" * 40)
    print("Loading datasets...")

    # Define paths to local benchmark data (if available)
    gsm8k_train_path = None
    gsm8k_eval_path = None
    math500_path = None

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        benchmark_dir = os.path.join(project_root, "evaluation", "benchmark_data")
        possible_train_path = os.path.join(benchmark_dir, "gsm8k_train.jsonl")
        possible_eval_path = os.path.join(benchmark_dir, "gsm8k_test.jsonl")
        math500_path = os.path.join(benchmark_dir, "math_500.jsonl")

        if os.path.exists(possible_train_path):
            gsm8k_train_path = possible_train_path
        if os.path.exists(possible_eval_path):
            gsm8k_eval_path = possible_eval_path
        if not os.path.exists(math500_path):
            math500_path = None

        print(f"Local dataset check:")
        print(f"  GSM8K train: {'Found' if gsm8k_train_path else 'Not found'}")
        print(f"  GSM8K eval/test: {'Found' if gsm8k_eval_path else 'Not found'}")
        print(f"  MATH-500: {'Found' if math500_path else 'Not found'}")
    except NameError:
        print("Running in notebook environment - will download datasets from HuggingFace")

    try:
        train_gsm8k_data = load_gsm8k_data(
            path=gsm8k_train_path,
            num_samples=config.train_samples,
            split="train",
            source_label="gsm8k_train_local" if gsm8k_train_path else "gsm8k_train_hf",
        )
    except Exception as e:
        print(f"WARNING: Could not load GSM8K train data without leakage: {e}")
        train_gsm8k_data = []

    try:
        eval_data = load_gsm8k_data(
            path=gsm8k_eval_path,
            num_samples=config.eval_samples,
            split="test",
            source_label="gsm8k_eval_local" if gsm8k_eval_path else "gsm8k_test_hf",
        )
    except Exception as e:
        print(f"WARNING: Could not load GSM8K eval data: {e}")
        print("Using separate synthetic eval fallback.")
        eval_data = generate_synthetic_eval_problems(config.eval_samples)
    eval_questions = {question_key(item["question"]) for item in eval_data}
    before_filter = len(train_gsm8k_data)
    train_gsm8k_data = [
        item for item in train_gsm8k_data
        if question_key(item["question"]) not in eval_questions
    ]
    removed_overlap = before_filter - len(train_gsm8k_data)
    if removed_overlap:
        print(f"Filtered {removed_overlap} GSM8K train examples that overlapped eval questions")

    rng = random.Random(config.seed)
    rng.shuffle(train_gsm8k_data)

    hard_target = (
        config.train_samples
        if not train_gsm8k_data
        else max(200, int(config.train_samples * config.hard_mix_ratio))
    )
    hard_data = load_harder_math_data(
        path=math500_path,
        num_samples=hard_target,
        exclude_questions=eval_questions,
        allow_benchmark_hard_data=config.allow_benchmark_hard_data,
        allow_gsm8k_test_fallback=config.allow_gsm8k_test_hard_fallback,
    )
    print(f"Hard problems: {len(hard_data)}")

    # Mix easy and hard (config-driven split)
    if train_gsm8k_data:
        n_hard = min(len(hard_data), int(config.train_samples * config.hard_mix_ratio))
        n_easy = min(len(train_gsm8k_data), config.train_samples - n_hard)
    else:
        n_hard = min(len(hard_data), config.train_samples)
        n_easy = 0
    train_data = train_gsm8k_data[:n_easy] + hard_data[:n_hard]
    print(f"Final mix: {n_easy} easy + {n_hard} hard = {len(train_data)} total")
    rng.shuffle(train_data)
    config.total_training_steps = config.num_epochs * max(1, math.ceil(len(train_data) / max(config.batch_size, 1)))

    # Load model
    print("\n" + "-" * 40)
    print("Loading model...")

    if config.use_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=config.bnb_4bit_quant_type,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    else:
        bnb_config = None

    tokenizer = AutoTokenizer.from_pretrained(config.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if not config.use_4bit else None,
    )

    if config.use_4bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    
    # CRITICAL FIX: Disable gradient checkpointing to restore gradient flow
    model.gradient_checkpointing_disable()

    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=config.target_modules,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Create trainer
    trainer = RLOCovTrainerV4(model, tokenizer, config)
    trainer.data_manifest = {
        "train_ids": [item.get("id") for item in train_data],
        "eval_ids": [item.get("id") for item in eval_data],
        "train_sources": {
            source: sum(1 for item in train_data if (item.get("source") or "unknown") == source)
            for source in sorted({item.get("source") or "unknown" for item in train_data})
        },
        "eval_sources": {
            source: sum(1 for item in eval_data if (item.get("source") or "unknown") == source)
            for source in sorted({item.get("source") or "unknown" for item in eval_data})
        },
        "benchmark_hard_data_enabled": config.allow_benchmark_hard_data,
        "gsm8k_test_hard_fallback_enabled": config.allow_gsm8k_test_hard_fallback,
    }

    # Initial evaluation
    print("\n" + "=" * 60)
    print("INITIAL EVALUATION")
    print("=" * 60)
    initial_eval = trainer.evaluate(eval_data, num_samples=config.num_eval_samples)
    print(f"Accuracy: {initial_eval['accuracy']:.2f}%")
    print(f"Structure Rate: {initial_eval['structure_rate']:.2f}%")
    print(f"Goldilocks Rate: {initial_eval['goldilocks_rate']:.2f}%")
    print(f"Avg Reward: {initial_eval['avg_reward']:.3f}")

    trainer.initial_accuracy = initial_eval['accuracy']
    trainer.best_accuracy = initial_eval['accuracy']

    # Training loop
    print("\n" + "=" * 60)
    print("TRAINING")
    print("=" * 60)

    for epoch in range(config.num_epochs):
        print(f"\n--- Epoch {epoch + 1}/{config.num_epochs} ---")
        rng.shuffle(train_data)

        for batch_start in range(0, len(train_data), config.batch_size):
            batch_items = train_data[batch_start:batch_start + config.batch_size]
            result = trainer.train_batch(batch_items)

            # Logging
            if trainer.global_step % config.log_every == 0:
                stats = trainer.reward_calc.get_stats()
                log_msg = (
                    f"Step {trainer.global_step} | Loss: {result['loss']:.4f} "
                    f"| R: {result['reward']:.2f} | A: {result['advantage']:.2f} "
                    f"| KL: {result['kl']:.4f} | H: {result['entropy']:.2f} "
                    f"| Grad: {result['grad_norm']:.2f} | LR: {result['lr']:.2e}"
                )

                if "sim_mean" in stats:
                    log_msg += f" | Sim@L{config.analysis_layer}: {stats['sim_mean']:.3f} [{stats['sim_min']:.2f}-{stats['sim_max']:.2f}]"
                    log_msg += f" | GL: {stats['goldilocks_rate']*100:.0f}%"

                print(log_msg)

                # V4: Log multi-layer calibration every 50 optimizer steps
                if trainer.global_step % 50 == 0:
                    layer_msg = "  [CALIBRATION]"
                    for layer_idx in config.analysis_layers_to_log:
                        key = f"sim_L{layer_idx}_mean"
                        if key in stats:
                            layer_msg += f" L{layer_idx}={stats[key]:.3f}"
                    print(layer_msg)

            # CHECKPOINTING (Issue #1)
            if trainer.global_step % config.save_every_n_steps == 0:
                ckpt_path = os.path.join(config.output_dir, f"step_{trainer.global_step}")
                print(f"\n--- Saving checkpoint at step {trainer.global_step} ---")
                trainer.save_checkpoint(ckpt_path)
                print()

            # Evaluation
            if trainer.global_step % config.eval_every_n_steps == 0:
                print("\n--- Evaluation ---")
                eval_result = trainer.evaluate(eval_data, num_samples=config.num_eval_samples)
                print(f"Accuracy: {eval_result['accuracy']:.2f}% | "
                      f"Structure: {eval_result['structure_rate']:.2f}% | "
                      f"Goldilocks: {eval_result['goldilocks_rate']:.2f}%")

                # CATASTROPHE DETECTION
                if eval_result['accuracy'] < trainer.initial_accuracy - config.catastrophe_accuracy_drop:
                    print(f"    HALT: Accuracy dropped >{config.catastrophe_accuracy_drop:.1f} points.")
                    catastrophe_path = os.path.join(config.output_dir, f"catastrophe_step_{trainer.global_step}")
                    trainer.save_checkpoint(catastrophe_path, is_best=False)
                    if config.halt_on_catastrophe:
                        return trainer

                if eval_result['accuracy'] > trainer.best_accuracy:
                    trainer.best_accuracy = eval_result['accuracy']
                    print(f"    New best accuracy: {trainer.best_accuracy:.2f}%")

                    if config.save_on_best:
                        best_path = os.path.join(config.output_dir, "best")
                        print(f"    Saving best checkpoint...")
                        trainer.save_checkpoint(best_path, is_best=True)

                print("-" * 40 + "\n")

    # Final evaluation
    print("\n" + "=" * 60)
    print("FINAL EVALUATION")
    print("=" * 60)
    final_eval = trainer.evaluate(eval_data, num_samples=config.num_eval_samples)
    print(f"Accuracy: {final_eval['accuracy']:.2f}%")
    print(f"Structure Rate: {final_eval['structure_rate']:.2f}%")
    print(f"Goldilocks Rate: {final_eval['goldilocks_rate']:.2f}%")
    print(f"Avg Reward: {final_eval['avg_reward']:.3f}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Metric':<20} {'Initial':>10} {'Final':>10} {'Delta':>10}")
    print("-" * 50)
    print(f"{'Accuracy':<20} {initial_eval['accuracy']:>9.1f}% {final_eval['accuracy']:>9.1f}% "
          f"{final_eval['accuracy'] - initial_eval['accuracy']:>+9.1f}%")
    print(f"{'Goldilocks Rate':<20} {initial_eval['goldilocks_rate']:>9.1f}% {final_eval['goldilocks_rate']:>9.1f}% "
          f"{final_eval['goldilocks_rate'] - initial_eval['goldilocks_rate']:>+9.1f}%")
    print(f"{'Structure Rate':<20} {initial_eval['structure_rate']:>9.1f}% {final_eval['structure_rate']:>9.1f}% "
          f"{final_eval['structure_rate'] - initial_eval['structure_rate']:>+9.1f}%")

    stats = trainer.reward_calc.get_stats()
    if "sim_mean" in stats:
        print(f"\nSimilarity Stats (primary layer {config.analysis_layer}):")
        print(f"  Mean: {stats['sim_mean']:.3f}")
        print(f"  Range: [{stats['sim_min']:.3f}, {stats['sim_max']:.3f}]")
        print(f"  In Goldilocks: {stats['goldilocks_rate']*100:.1f}%")

        # V4: Show multi-layer comparison
        print(f"\nMulti-Layer Calibration:")
        for layer_idx in config.analysis_layers_to_log:
            key = f"sim_L{layer_idx}_mean"
            if key in stats:
                marker = " <-- PRIMARY" if layer_idx == config.analysis_layer else ""
                print(f"  Layer {layer_idx}: mean={stats[key]:.3f} "
                      f"[{stats[f'sim_L{layer_idx}_min']:.3f}, {stats[f'sim_L{layer_idx}_max']:.3f}]{marker}")

    # SAVE FINAL CHECKPOINT
    print("\n" + "=" * 60)
    print("SAVING FINAL CHECKPOINT")
    print("=" * 60)
    final_path = os.path.join(config.output_dir, "final")
    trainer.save_checkpoint(final_path, is_best=False)
    print(f"\nAll artifacts saved to {config.output_dir}")
    print(f"  - final/adapter : LoRA weights")
    print(f"  - final/tokenizer : Tokenizer")
    print(f"  - final/config_snapshot.json : Reproducibility info")
    print(f"  - final/metrics.jsonl : Training metrics")

    return trainer


if __name__ == "__main__":
    trainer = main()
