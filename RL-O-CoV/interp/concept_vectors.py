"""Contrastive concept-vector extraction (exp_proposal.md, Phase 2).

Isolates a direction in the residual stream associated with a target concept
by contrasting activations on target-concept prompts against a control set:

    v_T = mean_pool(h_layer | target prompts) - mean_pool(h_layer | control prompts)

Torch is imported lazily so the module can be imported (and its pure logic
self-tested) on machines without a GPU stack. Hook idioms follow the sibling
activation-steering experiment in project/refusal-capability-entanglement/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence


def _require_torch():
    try:
        import torch  # noqa: F401
        return torch
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "concept_vectors requires torch at extraction time; "
            "only the dry-run self-tests work without it"
        ) from e


@dataclass
class ConceptVectorSpec:
    """What to extract: prompts that evoke the concept vs. matched controls."""
    concept_name: str
    target_prompts: List[str]
    control_prompts: List[str]
    layer_idx: int  # transformer block index (0-based, block outputs)

    def validate(self) -> None:
        if not self.target_prompts or not self.control_prompts:
            raise ValueError(f"{self.concept_name}: both prompt sets must be non-empty")
        if self.layer_idx < 0:
            raise ValueError(f"{self.concept_name}: layer_idx must be >= 0")


def default_target_prompts(concept: str) -> List[str]:
    """The proposal's contrastive template, plus paraphrases to reduce prompt-specific noise."""
    return [
        f"Explain {concept} in detail.",
        f"Describe how {concept} works, step by step.",
        f"Give a worked example that uses {concept}.",
        f"What is {concept}? Define it precisely.",
    ]


def get_transformer_layers(model) -> Sequence[Any]:
    """Locate the decoder block list across common HF architectures."""
    for path in ("model.layers", "transformer.h", "gpt_neox.layers", "model.decoder.layers"):
        obj = model
        try:
            for attr in path.split("."):
                obj = getattr(obj, attr)
        except AttributeError:
            continue
        if obj is not None and len(obj) > 0:
            return obj
    raise ValueError("Could not locate transformer layer list on model")


def _pooled_hidden(model, tokenizer, prompts: List[str], layer_idx: int, max_length: int = 256):
    """Mean-pooled hidden state at layer_idx for each prompt, averaged over prompts."""
    torch = _require_torch()
    device = next(model.parameters()).device
    inputs = tokenizer(
        prompts, return_tensors="pt", padding=True, truncation=True, max_length=max_length
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs, output_hidden_states=True, use_cache=False, return_dict=True)

    # hidden_states[0] is the embedding layer; block b's output is index b+1.
    hidden = outputs.hidden_states[layer_idx + 1]
    mask = inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
    return pooled.mean(dim=0)


def extract_concept_vector(model, tokenizer, spec: ConceptVectorSpec):
    """Phase 2: v_T = pooled(target) - pooled(control), at spec.layer_idx.

    Returns a detached fp32 CPU tensor so it can be saved and re-applied
    independently of the extraction session.
    """
    spec.validate()
    target = _pooled_hidden(model, tokenizer, spec.target_prompts, spec.layer_idx)
    control = _pooled_hidden(model, tokenizer, spec.control_prompts, spec.layer_idx)
    return (target - control).detach().float().cpu()


def two_thirds_layer(model) -> int:
    """The proposal's default intervention point: ~2/3 of the way through the model."""
    n = len(get_transformer_layers(model))
    return max(0, (2 * n) // 3 - 1)
