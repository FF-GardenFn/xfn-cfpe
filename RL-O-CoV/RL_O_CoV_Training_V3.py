# %%
"""
================================================================================
RL-O-CoV V2: Reinforcement Learning for Oscillatory Chain of Verification
================================================================================

LESSONS FROM V1 FAILURE:
1. GSM8K too easy (88% baseline) - model doesn't need to oscillate
2. Too many trainable params (342M @ 4.3%) with LR=3e-5 = catastrophic forgetting
3. Goldilocks zone never hit (0%) - zone too narrow or similarity calc broken
4. Loss went NEGATIVE = REINFORCE gradient exploded

V2 FIXES:
- Conservative hyperparameters (don't destroy baseline)
- Harder datasets (force model to actually think)
- Wider Goldilocks zone (easier to hit)
- Better similarity logging (see actual values)
- Preserve SemanticCapture with layer hooks (V1's key innovation)
- Keep drift penalty

================================================================================
"""

import os
import json
import re
import random
from dataclasses import dataclass, field, asdict
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
class TrainingConfigV2:
    """Conservative config - learned from V1's catastrophic forgetting"""

    # Model
    model_name: str = "Qwen/Qwen2-7B-Instruct"

    # SAFETY RAILS BACK ON
    use_4bit: bool = True  # Was False in V1, caused OOM on gradients
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"

    # CONSERVATIVE LORA (V1 had r=128, way too high)
    lora_r: int = 32              # Was 128
    lora_alpha: int = 64          # 2x rank
    lora_dropout: float = 0.1
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj"  # Attention only, not MLP
    ])

    # CONSERVATIVE TRAINING (V1 had lr=3e-5, exploded)
    learning_rate: float = 5e-6   # Was 3e-5 (6x lower)
    warmup_steps: int = 100       # NEW: gradual ramp-up
    num_epochs: int = 3           # Was 5
    batch_size: int = 2           # Was 4
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    max_new_tokens: int = 768
    max_grad_norm: float = 0.5    # Was 1.0 (tighter clipping)

    # SEMANTIC ANALYSIS
    # V3 FIX: Layer 20 was too deep — at 71% depth, representations converge
    # and hypothesis/oscillation sections always have similarity >0.86.
    # Layer 14 (50% depth) retains more surface-level semantic differences.
    analysis_layer: int = 14      # Was 20 (too deep, representations converge)
    analysis_layers_to_log: List[int] = field(
        default_factory=lambda: [8, 14, 20]  # Log multiple layers for calibration
    )
    use_first_sentence: bool = True  # Extract first sentence instead of mean-pooling entire section

    # WIDER GOLDILOCKS ZONE
    # V3 FIX: Ceiling raised from 0.85 to 0.95 — at layer 20, similarity was
    # always >0.86 so the zone NEVER fired. Even at layer 14, sections about
    # the same problem will be correlated; 0.95 gives room for the reward signal
    # to exist while we calibrate the optimal layer.
    goldilocks_low: float = 0.15  # Was 0.3
    goldilocks_high: float = 0.95 # Was 0.85 (V2 ceiling was too low for layer 20)

    # GENTLER REWARDS (prioritize not forgetting)
    correctness_weight: float = 2.5   # Higher than V1
    structure_weight: float = 1.5
    resonance_reward: float = 1.5     # Was 2.0
    drift_penalty_weight: float = 0.3 # Preserved from V1

    # DATA (Issue #3: Config-driven split)
    train_samples: int = 1000     # Was 2000
    eval_samples: int = 100
    train_split_ratio: float = 0.8  # For GSM8K train/eval split
    hard_mix_ratio: float = 0.2     # Fraction of harder problems in training

    # REPRODUCIBILITY (Issue #2)
    seed: int = 42

    # REINFORCE BASELINE (Issue #4: Variance reduction)
    use_baseline: bool = True
    baseline_ema_decay: float = 0.9  # EMA for reward baseline
    normalize_advantages: bool = True  # Normalize (r - baseline)

    # MISSING PHASE PENALTY (Issue #6)
    missing_phase_penalty: float = 0.3  # Per missing required phase

    # CHECKPOINTING (Issue #1)
    save_every_n_steps: int = 200
    save_on_best: bool = True

    # EVALUATION
    eval_every_n_steps: int = 50  # More frequent checks
    num_eval_samples: int = 50

    # LOGGING
    log_every: int = 5
    log_similarities: bool = True  # NEW: see actual cosine values

    # OUTPUT
    output_dir: str = "./rl_ocov_v3_checkpoints"

# %%
# ============================================================================
# DIALECTICA PROMPT (same as V1)
# ============================================================================

TRAINING_PROMPT_TEMPLATE = """Solve this problem using structured reasoning:

{problem}

Use this format:
[DETECT] Is this complex reasoning or simple lookup?
[HYPOTHESIZE]
H1: [approach 1]
H2: [approach 2]
[OSCILLATION] Test each approach - what works, what fails?
[SYNTHESIZE] Final answer based on analysis.

Answer:"""


# %%
# ============================================================================
# SEMANTIC CAPTURE (PRESERVED FROM V1 - key innovation)
# V3 FIX: Added first-sentence extraction + multi-layer support
# ============================================================================

class SemanticCapture:
    """Extract semantic embeddings from specific transformer layers"""

    def __init__(self, model, layer_idx: int):
        self.model = model
        self.layer_idx = layer_idx
        self.captured = None
        self.hook_handle = None

    def _get_target_layer(self):
        """Find the target layer across different architectures"""
        if hasattr(self.model, 'base_model'):
            model = self.model.base_model.model  # PEFT wrapped
        else:
            model = self.model

        # Qwen2, Llama, Mistral
        if hasattr(model, 'model') and hasattr(model.model, 'layers'):
            return model.model.layers[self.layer_idx]
        # GPT-2, GPT-Neo
        elif hasattr(model, 'transformer') and hasattr(model.transformer, 'h'):
            return model.transformer.h[self.layer_idx]
        else:
            raise ValueError(f"Unknown model architecture for {type(model)}")

    def _hook_fn(self, module, input, output):
        if isinstance(output, tuple):
            self.captured = output[0].detach()
        else:
            self.captured = output.detach()

    def __enter__(self):
        target_layer = self._get_target_layer()
        self.hook_handle = target_layer.register_forward_hook(self._hook_fn)
        return self

    def __exit__(self, *args):
        if self.hook_handle:
            self.hook_handle.remove()

    def get_embedding(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Get mean-pooled embedding for the input"""
        with torch.no_grad():
            self.model(input_ids)

        if self.captured is not None:
            return self.captured.mean(dim=1).squeeze(0)
        return None


def extract_first_sentence(text: str) -> str:
    """
    Extract the first meaningful sentence from a section.
    
    V3 FIX: Mean-pooling entire sections washes out differences because
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


def get_section_embedding(
    text: str,
    model,
    tokenizer,
    layer_idx: int,
    max_length: int = 512,
    first_sentence_only: bool = False
) -> torch.Tensor:
    """
    Get semantic embedding for a text section using layer hooks.
    
    Args:
        first_sentence_only: If True, extract and embed only the first sentence
            instead of the entire section. This preserves semantic differences
            between sections that discuss the same problem differently.
    """

    if not text or len(text.strip()) < 10:
        hidden_size = model.config.hidden_size
        device = next(model.parameters()).device
        return torch.zeros(hidden_size, device=device)

    # V3 FIX: Optionally extract first sentence for more discriminative embeddings
    if first_sentence_only:
        text = extract_first_sentence(text)
        if not text or len(text.strip()) < 10:
            hidden_size = model.config.hidden_size
            device = next(model.parameters()).device
            return torch.zeros(hidden_size, device=device)

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=max_length
    ).to(next(model.parameters()).device)

    with SemanticCapture(model, layer_idx) as capturer:
        return capturer.get_embedding(inputs.input_ids)


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
    similarities = {}
    for layer_idx in layers:
        emb_a = get_section_embedding(text_a, model, tokenizer, layer_idx,
                                       first_sentence_only=first_sentence_only)
        emb_b = get_section_embedding(text_b, model, tokenizer, layer_idx,
                                       first_sentence_only=first_sentence_only)
        if emb_a is not None and emb_b is not None:
            sim = F.cosine_similarity(emb_a.unsqueeze(0), emb_b.unsqueeze(0)).item()
            similarities[layer_idx] = sim
        else:
            similarities[layer_idx] = None
    return similarities

# %%
# ============================================================================
# DATA LOADING (with accessible datasets)
# ============================================================================

def load_gsm8k_data(path: str = None, num_samples: int = None) -> List[Dict]:
    """Load GSM8K dataset - supports local JSONL or HuggingFace download"""
    
    processed = []
    
    # Try local file first
    if path and os.path.exists(path):
        print(f"Loading GSM8K from local file: {path}")
        with open(path, 'r') as f:
            for line in f:
                item = json.loads(line)
                answer_text = item.get("answer", "")
                if "####" in answer_text:
                    final_answer = answer_text.split("####")[-1].strip()
                else:
                    numbers = re.findall(r'-?\d+\.?\d*', answer_text)
                    final_answer = numbers[-1] if numbers else answer_text

                processed.append({
                    "question": item["question"],
                    "answer": final_answer,
                    "full_solution": answer_text,
                    "difficulty": 1,
                    "source": "gsm8k_local"
                })
    else:
        # Fallback to HuggingFace download
        from datasets import load_dataset
        print("Loading GSM8K dataset from HuggingFace...")
        dataset = load_dataset("gsm8k", "main", split="train")

        for item in dataset:
            answer_text = item.get("answer", "")
            if "####" in answer_text:
                final_answer = answer_text.split("####")[-1].strip()
            else:
                numbers = re.findall(r'-?\d+\.?\d*', answer_text)
                final_answer = numbers[-1] if numbers else answer_text

            processed.append({
                "question": item["question"],
                "answer": final_answer,
                "full_solution": answer_text,
                "difficulty": 1,
                "source": "gsm8k"
            })

    if num_samples:
        processed = processed[:num_samples]

    print(f"Loaded {len(processed)} GSM8K examples")
    return processed


def load_harder_math_data(path: str = None, num_samples: int = 200) -> List[Dict]:
    """
    Load harder math problems - supports local MATH-500 JSONL or HuggingFace download
    
    Primary: local math_500.jsonl (if path provided)
    Fallback 1: HuggingFace MATH-500
    Fallback 2: GSM8K test set
    Fallback 3: synthetic problems
    """
    
    processed = []

    # Try local MATH-500 file first
    if path and os.path.exists(path):
        print(f"Loading MATH-500 from local file: {path}")
        try:
            with open(path, 'r') as f:
                for line in f:
                    if len(processed) >= num_samples:
                        break
                    item = json.loads(line)
                    processed.append({
                        "question": item.get("problem", item.get("question", "")),
                        "answer": item.get("answer", ""),
                        "full_solution": item.get("solution", ""),
                        "difficulty": item.get("level", 3),
                        "source": "math500_local"
                    })
            print(f"Loaded {len(processed)} MATH-500 examples from local file")
        except Exception as e:
            print(f"Failed to load local MATH-500: {e}")

    # Fallback 1: Try HuggingFace MATH-500
    if len(processed) < num_samples:
        try:
            from datasets import load_dataset
            print("Trying HuggingFace MATH-500 dataset...")
            dataset = load_dataset("HuggingFaceH4/MATH-500", split="test")

            for item in dataset:
                if len(processed) >= num_samples:
                    break
                processed.append({
                    "question": item.get("problem", ""),
                    "answer": item.get("answer", ""),
                    "full_solution": item.get("solution", ""),
                    "difficulty": item.get("level", 3),
                    "source": "math500_hf"
                })
            print(f"Loaded {len(processed)} MATH-500 examples from HuggingFace")

        except Exception as e:
            print(f"HuggingFace MATH-500 failed: {e}")

    # Fallback 2: Try GSM8K test set (harder than train)
    if len(processed) < num_samples:
        try:
            from datasets import load_dataset
            print("Trying GSM8K test set as harder problems...")
            dataset = load_dataset("gsm8k", "main", split="test")

            for item in dataset:
                if len(processed) >= num_samples:
                    break
                answer_text = item.get("answer", "")
                if "####" in answer_text:
                    final_answer = answer_text.split("####")[-1].strip()
                else:
                    numbers = re.findall(r'-?\d+\.?\d*', answer_text)
                    final_answer = numbers[-1] if numbers else ""

                processed.append({
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
        synthetic = generate_synthetic_hard_problems(num_samples - len(processed))
        processed.extend(synthetic)

    return processed


def generate_synthetic_hard_problems(n: int) -> List[Dict]:
    """Generate synthetic hard problems that require multi-step reasoning"""

    problems = [
        {
            "question": "Find the sum of all positive integers n such that n² + 12n - 2007 is a perfect square.",
            "answer": "80",
            "difficulty": 3
        },
        {
            "question": "How many ordered pairs of positive integers (a,b) satisfy 1/a + 1/b = 1/20?",
            "answer": "9",
            "difficulty": 3
        },
        {
            "question": "In triangle ABC, AB=13, BC=14, CA=15. Find the length of the altitude from A to BC.",
            "answer": "12",
            "difficulty": 3
        },
        {
            "question": "Find the last three digits of 7^999.",
            "answer": "343",
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
    for i in range(n):
        prob = problems[i % len(problems)].copy()
        prob["source"] = "synthetic"
        result.append(prob)

    return result


# %%
# ============================================================================
# REWARD CALCULATOR (PRESERVED FROM V1 + V3 fixes for Goldilocks)
# ============================================================================

class OCovRewardCalculator:
    """
    Calculate rewards for O-CoV training (preserved from V1):
    - Terminal accuracy
    - Structural integrity (phase markers)
    - Resonance (Goldilocks zone for hypothesis-oscillation similarity)
    - Drift penalty (staying on topic)
    
    V3 FIXES:
    - First-sentence extraction for more discriminative embeddings
    - Multi-layer similarity logging for calibration
    - Layer 14 instead of 20 (mid-network, more diverse representations)
    - Goldilocks ceiling 0.95 (was 0.85 — never fired at layer 20)
    """

    def __init__(self, model, tokenizer, config: TrainingConfigV2):
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.device = next(model.parameters()).device

        # Phase markers to detect
        self.phases = ["DETECT", "HYPOTHESIZE", "OSCILLATION", "SYNTHESIZE"]

        # Tracking for analysis
        self.similarity_history = []
        self.accuracy_history = []
        
        # V3: Multi-layer similarity tracking for calibration
        self.multi_layer_history = {layer: [] for layer in config.analysis_layers_to_log}

    def extract_answer(self, text: str) -> str:
        """Extract the final answer from generated text"""
        if "Answer:" in text:
            answer_part = text.split("Answer:")[-1].strip()
            lines = answer_part.split('\n')
            answer = lines[0].strip()
        elif "SYNTHESIZE" in text.upper():
            synth_part = text.upper().split("SYNTHESIZE")[-1]
            numbers = re.findall(r'-?\d+\.?\d*', synth_part)
            answer = numbers[-1] if numbers else ""
        else:
            numbers = re.findall(r'-?\d+\.?\d*', text)
            answer = numbers[-1] if numbers else ""

        return answer.strip()

    def check_accuracy(self, generated: str, expected: str) -> float:
        """Check if the generated answer matches expected"""
        gen_answer = self.extract_answer(generated)

        gen_clean = re.sub(r'[^\d.-]', '', gen_answer)
        exp_clean = re.sub(r'[^\d.-]', '', expected)

        try:
            gen_num = float(gen_clean) if gen_clean else None
            exp_num = float(exp_clean) if exp_clean else None

            if gen_num is not None and exp_num is not None:
                if abs(gen_num - exp_num) < 0.01:
                    return self.config.correctness_weight
                if exp_num != 0 and abs(gen_num - exp_num) / abs(exp_num) < 0.1:
                    return self.config.correctness_weight * 0.5
        except ValueError:
            pass

        if gen_clean == exp_clean:
            return self.config.correctness_weight

        return -1.0  # Wrong answer penalty

    def check_structure(self, text: str) -> Tuple[float, Dict[str, bool]]:
        """Check structural integrity (phase markers present)"""
        found = {}
        text_upper = text.upper()

        for phase in self.phases:
            patterns = [f"[{phase}]", f"**{phase}**", f"{phase}:", f"## {phase}"]
            found[phase] = any(p.upper() in text_upper for p in patterns)

        # Check for hypothesis markers
        hypothesis_patterns = [r"H1[:\s]", r"H2[:\s]", r"\*\*H1\*\*", r"\*\*H2\*\*"]
        found["HYPOTHESES"] = any(re.search(p, text, re.IGNORECASE) for p in hypothesis_patterns)

        phase_score = sum(found.values()) / (len(self.phases) + 1)
        reward = phase_score * self.config.structure_weight

        return reward, found

    def extract_sections(self, text: str) -> Dict[str, str]:
        """Extract hypothesis and oscillation sections"""
        sections = {"hypothesis": "", "oscillation": "", "synthesize": ""}
        text_upper = text.upper()

        # Find HYPOTHESIZE section
        if "HYPOTHESIZE" in text_upper:
            start = text_upper.find("HYPOTHESIZE")
            end = len(text)
            for next_phase in ["OSCILLATION", "SYNTHESIZE", "SYNTHESIS"]:
                idx = text_upper.find(next_phase, start + 10)
                if idx > 0:
                    end = min(end, idx)
            sections["hypothesis"] = text[start:end]

        # Find OSCILLATION section
        if "OSCILLATION" in text_upper:
            start = text_upper.find("OSCILLATION")
            end = len(text)
            for next_phase in ["SYNTHESIZE", "SYNTHESIS", "ANSWER"]:
                idx = text_upper.find(next_phase, start + 10)
                if idx > 0:
                    end = min(end, idx)
            sections["oscillation"] = text[start:end]

        # Find SYNTHESIZE section
        for marker in ["SYNTHESIZE", "SYNTHESIS"]:
            if marker in text_upper:
                start = text_upper.find(marker)
                sections["synthesize"] = text[start:]
                break

        return sections

    def calculate_resonance(self, text: str, problem_embedding: torch.Tensor) -> Tuple[float, Dict]:
        """
        Calculate resonance reward (THE KEY INNOVATION from V1)

        Goldilocks Zone: hypothesis and oscillation should be
        related but different (0.15 < similarity < 0.95)
        
        V3 FIXES:
        - Uses first-sentence extraction for more discriminative comparison
        - Logs similarity at multiple layers for calibration
        - Layer 14 (mid-network) instead of 20 (too deep)
        """
        sections = self.extract_sections(text)
        metrics = {
            "hyp_osc_similarity": None,
            "in_goldilocks": False,
            "drift": 0.0,
            "multi_layer_sim": {},  # V3: per-layer similarities for calibration
        }

        hyp_text = sections["hypothesis"]
        osc_text = sections["oscillation"]

        if len(hyp_text) < 20 or len(osc_text) < 20:
            return 0.0, metrics

        # V3: Use first-sentence extraction if configured
        use_first = self.config.use_first_sentence

        # Get embeddings at the primary analysis layer
        hyp_emb = get_section_embedding(
            hyp_text, self.model, self.tokenizer,
            self.config.analysis_layer,
            first_sentence_only=use_first
        )
        osc_emb = get_section_embedding(
            osc_text, self.model, self.tokenizer,
            self.config.analysis_layer,
            first_sentence_only=use_first
        )

        if hyp_emb is None or osc_emb is None:
            return 0.0, metrics

        # Calculate cosine similarity at primary layer
        similarity = F.cosine_similarity(hyp_emb.unsqueeze(0), osc_emb.unsqueeze(0)).item()
        metrics["hyp_osc_similarity"] = similarity
        self.similarity_history.append(similarity)

        # V3: Multi-layer calibration logging (every 10th step to save compute)
        if len(self.similarity_history) % 10 == 1:
            multi_sim = get_multi_layer_similarity(
                hyp_text, osc_text,
                self.model, self.tokenizer,
                self.config.analysis_layers_to_log,
                first_sentence_only=use_first
            )
            metrics["multi_layer_sim"] = multi_sim
            for layer_idx, sim_val in multi_sim.items():
                if sim_val is not None:
                    self.multi_layer_history[layer_idx].append(sim_val)

        # THE GOLDILOCKS ZONE (V3: widened ceiling to 0.95)
        resonance_reward = 0.0
        if self.config.goldilocks_low < similarity < self.config.goldilocks_high:
            resonance_reward = self.config.resonance_reward
            metrics["in_goldilocks"] = True

            # Bonus for being closer to middle of zone
            zone_center = (self.config.goldilocks_low + self.config.goldilocks_high) / 2
            distance_from_center = abs(similarity - zone_center)
            max_distance = (self.config.goldilocks_high - self.config.goldilocks_low) / 2
            centering_bonus = (1 - distance_from_center / max_distance) * 0.3
            resonance_reward += centering_bonus

        # Calculate drift (PRESERVED FROM V1)
        if problem_embedding is not None:
            full_emb = get_section_embedding(
                text, self.model, self.tokenizer,
                self.config.analysis_layer
            )
            if full_emb is not None:
                drift = 1.0 - F.cosine_similarity(
                    full_emb.unsqueeze(0), problem_embedding.unsqueeze(0)
                ).item()
                metrics["drift"] = drift
                resonance_reward -= drift * self.config.drift_penalty_weight

        return resonance_reward, metrics

    def calculate_reward(
        self,
        generated_text: str,
        expected_answer: str,
        problem_text: str
    ) -> Tuple[float, Dict]:
        """Calculate total reward: accuracy + structure + resonance - drift"""

        # Get problem embedding for drift calculation
        problem_emb = get_section_embedding(
            problem_text, self.model, self.tokenizer,
            self.config.analysis_layer
        )

        # 1. Accuracy reward
        accuracy_reward = self.check_accuracy(generated_text, expected_answer)
        self.accuracy_history.append(accuracy_reward > 0)

        # 2. Structure reward
        structure_reward, structure_details = self.check_structure(generated_text)

        # 3. Resonance reward (includes drift penalty)
        resonance_reward, resonance_metrics = self.calculate_resonance(
            generated_text, problem_emb
        )

        # Total reward
        total_reward = accuracy_reward + structure_reward + resonance_reward

        metrics = {
            "total_reward": total_reward,
            "accuracy_reward": accuracy_reward,
            "structure_reward": structure_reward,
            "resonance_reward": resonance_reward,
            "structure_found": structure_details,
            **resonance_metrics
        }

        return total_reward, metrics

    def get_stats(self) -> Dict:
        """Get statistics for logging"""
        stats = {}

        if self.similarity_history:
            sims = self.similarity_history[-100:]  # Last 100
            stats["sim_mean"] = sum(sims) / len(sims)
            stats["sim_min"] = min(sims)
            stats["sim_max"] = max(sims)
            stats["goldilocks_rate"] = sum(
                1 for s in sims
                if self.config.goldilocks_low < s < self.config.goldilocks_high
            ) / len(sims)

        if self.accuracy_history:
            stats["accuracy"] = sum(self.accuracy_history[-100:]) / min(100, len(self.accuracy_history))

        # V3: Multi-layer stats for calibration
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

class RLOCovTrainerV2:
    """RL trainer with safety mechanisms to prevent catastrophic forgetting"""

    def __init__(self, model, tokenizer, config: TrainingConfigV2):
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.device = next(model.parameters()).device

        # Reward calculator
        self.reward_calc = OCovRewardCalculator(model, tokenizer, config)

        # Optimizer
        trainable_params = [p for p in model.parameters() if p.requires_grad]
        self.optimizer = torch.optim.AdamW(
            trainable_params,
            lr=config.learning_rate,
            weight_decay=0.01
        )

        # Training state
        self.global_step = 0
        self.best_accuracy = 0
        self.initial_accuracy = None

        # REINFORCE baseline (Issue #4: Variance reduction)
        self.reward_baseline = 0.0
        self.reward_history_for_norm = []  # For advantage normalization

        # History
        self.history = {
            "step": [], "loss": [], "reward": [], "advantage": [],
            "accuracy": [], "structure": [], "resonance": [],
            "goldilocks_rate": [], "similarity": [], "missing_phases": []
        }

        # Metrics log for JSONL output (Issue #1)
        self.metrics_log = []

    def save_checkpoint(self, path: str, is_best: bool = False):
        """Save LoRA adapter, tokenizer, config, and metrics (Issue #1)"""
        import os
        os.makedirs(path, exist_ok=True)

        # 1. Save LoRA adapter weights
        adapter_path = os.path.join(path, "adapter")
        self.model.save_pretrained(adapter_path)
        print(f"  ✓ Saved LoRA adapter to {adapter_path}")

        # 2. Save tokenizer
        tokenizer_path = os.path.join(path, "tokenizer")
        self.tokenizer.save_pretrained(tokenizer_path)
        print(f"  ✓ Saved tokenizer to {tokenizer_path}")

        # 3. Save config snapshot
        config_snapshot = {
            "config": asdict(self.config),
            "versions": get_version_info(),
            "global_step": self.global_step,
            "best_accuracy": self.best_accuracy,
            "initial_accuracy": self.initial_accuracy,
            "reward_baseline": self.reward_baseline,
            "timestamp": datetime.now().isoformat(),
            "is_best": is_best,
        }
        config_path = os.path.join(path, "config_snapshot.json")
        with open(config_path, "w") as f:
            json.dump(config_snapshot, f, indent=2, default=str)
        print(f"  ✓ Saved config snapshot to {config_path}")

        # 4. Save metrics JSONL
        metrics_path = os.path.join(path, "metrics.jsonl")
        with open(metrics_path, "w") as f:
            for entry in self.metrics_log:
                f.write(json.dumps(entry) + "\n")
        print(f"  ✓ Saved {len(self.metrics_log)} metric entries to {metrics_path}")

    def format_prompt(self, problem: str) -> str:
        return TRAINING_PROMPT_TEMPLATE.format(problem=problem)

    def generate(self, prompt: str) -> Tuple[str, torch.Tensor]:
        """Generate response"""
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_seq_length - self.config.max_new_tokens
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
                pad_token_id=self.tokenizer.pad_token_id,
                return_dict_in_generate=True,
                output_scores=True
            )

        generated_ids = outputs.sequences[0]
        generated_text = self.tokenizer.decode(
            generated_ids[inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )

        return generated_text, generated_ids

    def compute_policy_gradient_loss(
        self,
        full_sequence: torch.Tensor,
        prompt_length: int,
        reward: float
    ) -> Tuple[torch.Tensor, float]:
        """REINFORCE policy gradient loss with baseline (Issue #4)"""

        outputs = self.model(full_sequence.unsqueeze(0))
        logits = outputs.logits

        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = full_sequence[1:].contiguous()

        log_probs = F.log_softmax(shift_logits, dim=-1)
        token_log_probs = log_probs[0, torch.arange(len(shift_labels)), shift_labels]

        # MASK SANITY CHECK (Issue #7: off-by-one risk)
        # prompt_length is the number of tokens in the prompt
        # We want to mask generated tokens only (indices >= prompt_length in shift_labels)
        # shift_labels has length (seq_len - 1), corresponding to predictions for positions 1..seq_len
        # So mask should be 1 for positions where we're predicting generated tokens
        mask = torch.zeros_like(token_log_probs)
        # After shifting: position i predicts token i+1
        # Prompt occupies positions 0..prompt_length-1, so generated starts at prompt_length
        # In shifted space: we want positions prompt_length-1 onwards (predicting tokens prompt_length+)
        gen_start = max(0, prompt_length - 1)
        mask[gen_start:] = 1.0

        # DEBUG: log mask coverage on first step
        if self.global_step == 0:
            print(f"  [DEBUG] prompt_length={prompt_length}, seq_len={len(full_sequence)}, "
                  f"mask_start={gen_start}, masked_tokens={int(mask.sum().item())}")

        # BASELINE AND ADVANTAGE (Issue #4: Variance reduction)
        if self.config.use_baseline:
            # Update EMA baseline
            self.reward_baseline = (
                self.config.baseline_ema_decay * self.reward_baseline +
                (1 - self.config.baseline_ema_decay) * reward
            )
            advantage = reward - self.reward_baseline

            # Optional advantage normalization
            if self.config.normalize_advantages:
                self.reward_history_for_norm.append(reward)
                if len(self.reward_history_for_norm) > 100:
                    self.reward_history_for_norm.pop(0)
                if len(self.reward_history_for_norm) > 1:
                    std = np.std(self.reward_history_for_norm) + 1e-8
                    advantage = advantage / std
        else:
            advantage = reward

        # Clamp advantage to prevent explosion
        advantage = max(-5.0, min(5.0, advantage))

        # WARMUP: scale down learning signal early
        warmup_scale = min(1.0, self.global_step / self.config.warmup_steps)

        masked_log_probs = token_log_probs * mask
        policy_loss = -advantage * warmup_scale * masked_log_probs.sum() / mask.sum().clamp(min=1)

        # Entropy bonus for exploration
        probs = F.softmax(shift_logits[0], dim=-1)
        entropy = -(probs * log_probs[0]).sum(dim=-1)
        entropy_bonus = 0.01 * (entropy * mask).mean()

        return policy_loss - entropy_bonus, advantage

    def train_step(self, problem: str, expected_answer: str) -> Dict:
        """Single training step with safety checks"""

        self.model.train()
        self.optimizer.zero_grad()

        prompt = self.format_prompt(problem)
        prompt_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        prompt_length = prompt_ids.shape[1]

        generated_text, full_sequence = self.generate(prompt)
        reward, metrics = self.reward_calc.calculate_reward(
            generated_text, expected_answer, problem
        )

        # MISSING PHASE PENALTY (Issue #6)
        missing_phases = sum(1 for phase, found in metrics["structure_found"].items() if not found)
        if missing_phases > 0:
            phase_penalty = missing_phases * self.config.missing_phase_penalty
            reward -= phase_penalty
            metrics["missing_phase_penalty"] = phase_penalty
        else:
            metrics["missing_phase_penalty"] = 0.0

        loss, advantage = self.compute_policy_gradient_loss(full_sequence, prompt_length, reward)
        loss.backward()

        # Tight gradient clipping
        torch.nn.utils.clip_grad_norm_(
            [p for p in self.model.parameters() if p.requires_grad],
            max_norm=self.config.max_grad_norm
        )

        self.optimizer.step()
        self.global_step += 1

        # Record history
        self.history["step"].append(self.global_step)
        self.history["loss"].append(loss.item())
        self.history["reward"].append(reward)
        self.history["advantage"].append(advantage)
        self.history["accuracy"].append(metrics["accuracy_reward"])
        self.history["structure"].append(metrics["structure_reward"])
        self.history["resonance"].append(metrics["resonance_reward"])
        self.history["goldilocks_rate"].append(1.0 if metrics["in_goldilocks"] else 0.0)
        self.history["missing_phases"].append(missing_phases)
        if metrics["hyp_osc_similarity"] is not None:
            self.history["similarity"].append(metrics["hyp_osc_similarity"])

        # Log to metrics JSONL (Issue #1)
        self.metrics_log.append({
            "step": self.global_step,
            "loss": loss.item(),
            "reward": reward,
            "advantage": advantage,
            "missing_phases": missing_phases,
            "in_goldilocks": metrics["in_goldilocks"],
            "accuracy_reward": metrics["accuracy_reward"],
            "similarity": metrics.get("hyp_osc_similarity"),
        })

        return {"loss": loss.item(), "reward": reward, "advantage": advantage, "metrics": metrics}

    def evaluate(self, eval_data: List[Dict], num_samples: int = None) -> Dict:
        """Evaluate model"""
        self.model.eval()

        if num_samples:
            eval_data = random.sample(eval_data, min(num_samples, len(eval_data)))

        results = {
            "accuracy": 0, "structure_rate": 0,
            "goldilocks_rate": 0, "avg_reward": 0,
            "similarities": []
        }

        for item in eval_data:
            prompt = self.format_prompt(item["question"])
            generated_text, _ = self.generate(prompt)
            reward, metrics = self.reward_calc.calculate_reward(
                generated_text, item["answer"], item["question"]
            )

            results["accuracy"] += 1 if metrics["accuracy_reward"] > 0 else 0
            results["structure_rate"] += sum(metrics["structure_found"].values()) / len(metrics["structure_found"])
            results["goldilocks_rate"] += 1 if metrics["in_goldilocks"] else 0
            results["avg_reward"] += reward
            if metrics["hyp_osc_similarity"] is not None:
                results["similarities"].append(metrics["hyp_osc_similarity"])

        n = len(eval_data)
        results["accuracy"] = results["accuracy"] / n * 100
        results["structure_rate"] = results["structure_rate"] / n * 100
        results["goldilocks_rate"] = results["goldilocks_rate"] / n * 100
        results["avg_reward"] = results["avg_reward"] / n

        self.model.train()
        return results


# %%
# ============================================================================
# MAIN TRAINING LOOP
# ============================================================================

def main():
    """Main execution with safety checks"""

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    config = TrainingConfigV2()

    # REPRODUCIBILITY (Issue #2)
    set_seed(config.seed)
    versions = get_version_info()

    print("=" * 70)
    print("RL-O-CoV V3: GOLDILOCKS FIX")
    print("   V2 had 0% Goldilocks rate — similarity always >0.86 at layer 20")
    print("   V3 fixes: layer 14, first-sentence extraction, ceiling 0.95")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Model: {config.model_name}")
    print(f"  Precision: {'4-bit' if config.use_4bit else 'bfloat16'}")
    print(f"  LoRA rank: {config.lora_r} (V1 had 128)")
    print(f"  Learning rate: {config.learning_rate} (V1 had 3e-5)")
    print(f"  Warmup steps: {config.warmup_steps}")
    print(f"  Analysis layer: {config.analysis_layer} (V2 had 20 — too deep)")
    print(f"  First-sentence extraction: {config.use_first_sentence}")
    print(f"  Goldilocks Zone: [{config.goldilocks_low}, {config.goldilocks_high}] (V2 had [0.15, 0.85])")
    print(f"  Multi-layer logging: {config.analysis_layers_to_log}")
    print(f"  Seed: {config.seed}")
    print(f"  REINFORCE baseline: {config.use_baseline}")
    print(f"  Checkpoint every: {config.save_every_n_steps} steps")

    print(f"\nVersions:")
    for pkg, ver in versions.items():
        print(f"  {pkg}: {ver}")

    # Load data
    print("\n" + "-" * 40)
    print("Loading datasets...")

    # Define paths to local benchmark data (if available)
    gsm8k_path = None
    math500_path = None

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        benchmark_dir = os.path.join(project_root, "evaluation", "benchmark_data")
        gsm8k_path = os.path.join(benchmark_dir, "gsm8k_test.jsonl")
        math500_path = os.path.join(benchmark_dir, "math_500.jsonl")

        if not os.path.exists(gsm8k_path):
            gsm8k_path = None
        if not os.path.exists(math500_path):
            math500_path = None

        print(f"Local dataset check:")
        print(f"  GSM8K: {'Found' if gsm8k_path else 'Not found'}")
        print(f"  MATH-500: {'Found' if math500_path else 'Not found'}")
    except NameError:
        print("Running in notebook environment - will download datasets from HuggingFace")

    gsm8k_data = load_gsm8k_data(
        path=gsm8k_path,
        num_samples=config.train_samples + config.eval_samples
    )
    random.shuffle(gsm8k_data)
    train_data = gsm8k_data[:config.train_samples]
    eval_data = gsm8k_data[config.train_samples:]

    print(f"Train: {len(train_data)}, Eval: {len(eval_data)}")

    hard_data = load_harder_math_data(
        path=math500_path,
        num_samples=200
    )
    print(f"Hard problems: {len(hard_data)}")

    # Mix easy and hard (config-driven split)
    n_hard = int(len(train_data) * config.hard_mix_ratio)
    n_easy = len(train_data) - n_hard
    train_data = train_data[:n_easy] + hard_data[:n_hard]
    print(f"Final mix: {n_easy} easy + {n_hard} hard = {len(train_data)} total")
    random.shuffle(train_data)

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
    trainer = RLOCovTrainerV2(model, tokenizer, config)

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
        random.shuffle(train_data)

        for i, item in enumerate(train_data):
            result = trainer.train_step(item["question"], item["answer"])

            # Logging
            if trainer.global_step % config.log_every == 0:
                stats = trainer.reward_calc.get_stats()
                log_msg = f"Step {trainer.global_step} | Loss: {result['loss']:.4f} | R: {result['reward']:.2f} | A: {result['advantage']:.2f}"

                if "sim_mean" in stats:
                    log_msg += f" | Sim@L{config.analysis_layer}: {stats['sim_mean']:.3f} [{stats['sim_min']:.2f}-{stats['sim_max']:.2f}]"
                    log_msg += f" | GL: {stats['goldilocks_rate']*100:.0f}%"

                print(log_msg)

                # V3: Log multi-layer calibration every 50 steps
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
                if eval_result['accuracy'] < trainer.initial_accuracy - 20:
                    print("    WARNING: Accuracy dropped >20% - possible catastrophic forgetting!")
                    print("    Consider stopping training or reducing learning rate.")

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

        # V3: Show multi-layer comparison
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
