"""
behavioral_delta.py — RL-O-CoV process rewards for training checkpoints.

Measures HOW the model reasons, not just what it produces.

The key finding from RL-O-CoV V1→V2→V3 iteration:
  - V1: Diagnostic at layer 20 → catastrophic forgetting (88%→0% cosine sim)
  - V2: Moved to layer 14, added warmup, widened Goldilocks zone (0.10–0.98)
  - V3: Conservative hyperparams, Goldilocks 0.15–0.95 — stable learning

Core insight: **layer depth determines whether cosine similarity between
checkpoint hidden states is informative or degenerate.**
  - Too early (layers 0–8): similarity collapses to 1.0 (representations
    unchanged — the layer hasn't specialised yet)
  - Too late (layers 20+): similarity collapses to 0.0 (catastrophic
    forgetting — the diagnostic layer is overwritten)
  - Goldilocks zone (layers 12–16): similarity stays in 0.15–0.95,
    meaning the model is updating representations without forgetting them

This module computes ProcessRewards for a training checkpoint by:
  1. Loading baseline + candidate checkpoints
  2. Running a small probe dataset through both at the diagnostic layer
  3. Computing resonance (mean cosine similarity across probe positions)
  4. Computing structure (std dev of cosine similarity — low = collapsed)
  5. Checking Goldilocks zone membership
  6. Returning a ProcessRewards dataclass for inclusion in CheckpointReport

Usage:
    from training_insights.evaluation.behavioral_delta import BehavioralDeltaScorer

    scorer = BehavioralDeltaScorer(
        baseline_checkpoint="checkpoints/baseline.pt",
        diagnostic_layer=14,
    )
    process_rewards = scorer.score(candidate_checkpoint="checkpoints/exp_002.pt")

    # Then pass to CheckpointEvaluator.evaluate()
    report = evaluator.evaluate(
        training_metrics=metrics,
        process_rewards=process_rewards,
    )
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# Goldilocks zone from RL-O-CoV V3 calibration
GOLDILOCKS_LOW:  float = 0.15
GOLDILOCKS_HIGH: float = 0.95

# Default diagnostic layer (V3 finding: layer 14 is stable on depth-24 models)
DEFAULT_DIAGNOSTIC_LAYER: int = 14

# Probe sentences — short, diverse, semantically distinct
# Kept CPU-runnable (tiny forward pass) for fast evaluation
DEFAULT_PROBE_TEXTS: list[str] = [
    "The capital of France is",
    "In mathematics, the derivative of x squared is",
    "To make a soufflé, you must first",
    "The primary cause of the First World War was",
    "def fibonacci(n):\n    if n <= 1:\n        return n",
    "The mitochondria is the powerhouse of the",
    "Water boils at 100 degrees Celsius at",
    "The speed of light in a vacuum is approximately",
]


@dataclass
class LayerActivation:
    """Hidden state tensor at a specific layer for a batch of tokens."""
    layer: int
    mean_hidden: list[float]   # mean across token positions, per hidden dim
    norm: float                # L2 norm of the mean hidden state


@dataclass
class BehavioralDeltaResult:
    """Full behavioral delta between baseline and candidate checkpoint."""
    resonance: float           # mean cosine similarity across probes
    structure: float           # std dev of cosine similarities (0=collapsed)
    goldilocks: bool           # True if resonance is in [0.15, 0.95]
    layer_depth: int           # diagnostic layer used
    n_probes: int              # number of probe sentences used
    per_probe_similarity: list[float]  # cosine sim per probe sentence
    collapse_type: str | None  # "high" (forgetting) | "low" (frozen) | None

    def to_process_rewards(self):
        """Convert to ProcessRewards dataclass for CheckpointEvaluator."""
        from training_insights.evaluation.checkpoint_eval import ProcessRewards
        return ProcessRewards(
            resonance=self.resonance,
            structure=self.structure,
            goldilocks=self.goldilocks,
            layer_depth=self.layer_depth,
        )

    def summary(self) -> str:
        status = "✓ Goldilocks" if self.goldilocks else f"✗ Collapsed ({self.collapse_type})"
        return (
            f"BehavioralDelta @ layer {self.layer_depth}: "
            f"resonance={self.resonance:.4f}  structure={self.structure:.4f}  {status}"
        )


class BehavioralDeltaScorer:
    """Computes process rewards by comparing hidden states across checkpoints.

    Architecture-agnostic: works with any model that exposes intermediate
    hidden states via a hook or explicit return (GPT-style decoder models).

    Parameters
    ----------
    baseline_checkpoint : str | Path
        Path to the baseline model checkpoint (.pt file).
    diagnostic_layer : int
        Layer index to use for hidden-state comparison.
        V3 finding: layer 14 is stable for depth-24 models.
        Rule of thumb: use depth // 2, never > depth - 4.
    probe_texts : list[str] | None
        Short probe sentences to run through the model. If None, uses defaults.
    device : str
        PyTorch device string. Defaults to "cpu" for fast evaluation.
    """

    def __init__(
        self,
        baseline_checkpoint: str | Path,
        diagnostic_layer: int = DEFAULT_DIAGNOSTIC_LAYER,
        probe_texts: list[str] | None = None,
        device: str = "cpu",
    ):
        self.baseline_checkpoint = Path(baseline_checkpoint)
        self.diagnostic_layer = diagnostic_layer
        self.probe_texts = probe_texts or DEFAULT_PROBE_TEXTS
        self.device = device
        self._baseline_activations: list[list[float]] | None = None

    def score(self, candidate_checkpoint: str | Path) -> BehavioralDeltaResult:
        """Compute behavioral delta between baseline and candidate checkpoint.

        Returns BehavioralDeltaResult with resonance, structure, and Goldilocks
        zone membership. Call .to_process_rewards() to use in CheckpointEvaluator.
        """
        try:
            import torch
        except ImportError:
            logger.warning("PyTorch not available — returning neutral ProcessRewards stub")
            return self._stub_result()

        candidate = Path(candidate_checkpoint)
        if not self.baseline_checkpoint.exists():
            logger.warning("Baseline checkpoint not found: %s", self.baseline_checkpoint)
            return self._stub_result()
        if not candidate.exists():
            logger.warning("Candidate checkpoint not found: %s", candidate)
            return self._stub_result()

        try:
            baseline_acts = self._get_activations(self.baseline_checkpoint, torch)
            candidate_acts = self._get_activations(candidate, torch)
        except Exception as exc:
            logger.error("Failed to extract activations: %s", exc)
            return self._stub_result()

        return self._compute_delta(baseline_acts, candidate_acts)

    def score_from_activations(
        self,
        baseline_acts: list[list[float]],
        candidate_acts: list[list[float]],
    ) -> BehavioralDeltaResult:
        """Compute delta from pre-extracted activation lists (for testing)."""
        return self._compute_delta(baseline_acts, candidate_acts)

    # ------------------------------------------------------------------
    # Activation extraction
    # ------------------------------------------------------------------

    def _get_activations(
        self, checkpoint_path: Path, torch
    ) -> list[list[float]]:
        """Load checkpoint and extract mean hidden states at diagnostic_layer
        for each probe sentence. Returns list[n_probes][hidden_dim]."""
        import sys
        from pathlib import Path as P

        # Add training_insights/ to path so we can import core
        ti_root = P(__file__).parent.parent
        if str(ti_root) not in sys.path:
            sys.path.insert(0, str(ti_root))

        try:
            from core.gpt import GPT, GPTConfig   # type: ignore
            from prepare import Tokenizer  # type: ignore
        except ImportError as e:
            raise ImportError(f"Cannot import core modules: {e}") from e

        state = torch.load(checkpoint_path, map_location=self.device, weights_only=True)

        # Support both raw state_dict and {'model': state_dict} formats
        if isinstance(state, dict) and "model" in state:
            state_dict = state["model"]
            config_dict = state.get("config", {})
        else:
            state_dict = state
            config_dict = {}

        # Infer config from state_dict or stored config
        config = GPTConfig(
            n_layer=config_dict.get("n_layer", 12),
            n_head=config_dict.get("n_head", 6),
            n_embd=config_dict.get("n_embd", 768),
            vocab_size=config_dict.get("vocab_size", 32768),
        )

        # Clamp diagnostic layer to valid range
        layer = min(self.diagnostic_layer, config.n_layer - 1)
        if layer != self.diagnostic_layer:
            logger.warning(
                "Clamped diagnostic_layer %d → %d (model depth=%d)",
                self.diagnostic_layer, layer, config.n_layer,
            )

        model = GPT(config).to(self.device)
        model.load_state_dict(state_dict, strict=False)
        model.eval()

        # Register hook to capture hidden state after target layer
        activations: list[torch.Tensor] = []

        def hook_fn(module, input, output):
            # output may be (hidden, ...) tuple or just hidden
            h = output[0] if isinstance(output, tuple) else output
            activations.append(h.detach().mean(dim=1).cpu())  # mean over tokens

        hook = model.transformer.h[layer].register_forward_hook(hook_fn)

        try:
            tokenizer = Tokenizer()
            acts_per_probe: list[list[float]] = []
            with torch.no_grad():
                for text in self.probe_texts:
                    activations.clear()
                    tokens = tokenizer.encode(text)
                    t = torch.tensor(tokens[:64], dtype=torch.long, device=self.device).unsqueeze(0)
                    _ = model(t)
                    if activations:
                        # [1, hidden_dim] → [hidden_dim]
                        h = activations[0].squeeze(0)
                        acts_per_probe.append(h.tolist())
        finally:
            hook.remove()

        return acts_per_probe

    # ------------------------------------------------------------------
    # Delta computation (pure Python — no torch dependency after this point)
    # ------------------------------------------------------------------

    def _compute_delta(
        self,
        baseline: list[list[float]],
        candidate: list[list[float]],
    ) -> BehavioralDeltaResult:
        """Compute cosine similarities between activation pairs."""
        if not baseline or not candidate:
            return self._stub_result()

        n = min(len(baseline), len(candidate))
        similarities: list[float] = []

        for b_vec, c_vec in zip(baseline[:n], candidate[:n]):
            sim = _cosine_similarity(b_vec, c_vec)
            similarities.append(sim)

        if not similarities:
            return self._stub_result()

        resonance = sum(similarities) / len(similarities)
        mean_sq = sum(s * s for s in similarities) / len(similarities)
        structure = (mean_sq - resonance ** 2) ** 0.5   # std dev

        goldilocks = GOLDILOCKS_LOW <= resonance <= GOLDILOCKS_HIGH

        collapse_type: str | None = None
        if resonance > GOLDILOCKS_HIGH:
            collapse_type = "low"    # representations frozen (didn't learn)
        elif resonance < GOLDILOCKS_LOW:
            collapse_type = "high"   # catastrophic forgetting

        return BehavioralDeltaResult(
            resonance=resonance,
            structure=structure,
            goldilocks=goldilocks,
            layer_depth=self.diagnostic_layer,
            n_probes=n,
            per_probe_similarity=similarities,
            collapse_type=collapse_type,
        )

    @staticmethod
    def _stub_result() -> BehavioralDeltaResult:
        """Neutral stub when checkpoints or torch are unavailable."""
        return BehavioralDeltaResult(
            resonance=0.0,
            structure=0.0,
            goldilocks=True,   # neutral: don't penalise if we can't measure
            layer_depth=DEFAULT_DIAGNOSTIC_LAYER,
            n_probes=0,
            per_probe_similarity=[],
            collapse_type=None,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure-Python cosine similarity between two equal-length vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def recommended_diagnostic_layer(model_depth: int) -> int:
    """Return the recommended diagnostic layer for a model of given depth.

    Rules derived from RL-O-CoV iteration:
    - Never use the first quarter of layers (not yet specialised)
    - Never use the last 4 layers (catastrophic forgetting risk)
    - Prefer the middle-to-upper-middle range

    Examples:
        depth=8  → layer 4
        depth=12 → layer 6
        depth=24 → layer 14
        depth=32 → layer 18
    """
    if model_depth <= 4:
        return max(0, model_depth // 2)
    # Target ~58% depth, clamped away from the last 4 layers
    target = int(model_depth * 0.58)
    return min(target, model_depth - 4)
