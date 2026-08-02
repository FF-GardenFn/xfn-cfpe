"""Concept erasure via residual-stream intervention (exp_proposal.md, Phase 3).

Two modes, installed as a forward hook on one decoder block:

- ``steer``   : h' = h - strength * v          (the proposal's method, kept as the
                default so the implementation matches the committed protocol)
- ``project`` : h' = h - strength * (h.v̂) v̂    (directional-projection removal;
                stronger erasure semantics, provided as the natural comparison)

The hook math is mirrored in ``_erase_pure`` (pure python) so the arithmetic is
self-testable without torch; the tensor path applies the identical formula.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import List, Optional

VALID_MODES = ("steer", "project")


def _erase_pure(hidden: List[float], vector: List[float], strength: float, mode: str) -> List[float]:
    """Reference implementation of the erasure arithmetic on plain lists.

    Exists so the self-test can verify the formula without torch; the tensor
    hook below must stay in lockstep with this function.
    """
    if mode == "steer":
        return [h - strength * v for h, v in zip(hidden, vector)]
    if mode == "project":
        norm_sq = sum(v * v for v in vector) or 1.0
        proj = sum(h * v for h, v in zip(hidden, vector)) / norm_sq
        return [h - strength * proj * v for h, v in zip(hidden, vector)]
    raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")


def _hidden_from_layer_output(output):
    return output[0] if isinstance(output, tuple) else output


def _replace_hidden_in_layer_output(output, hidden):
    if isinstance(output, tuple):
        return (hidden,) + tuple(output[1:])
    return hidden


@contextmanager
def concept_erasure(
    model,
    vector,
    layer_idx: int,
    strength: float = 3.0,
    mode: str = "steer",
):
    """Context manager: erase a concept direction for everything run inside it.

    ``strength`` defaults to 3.0 — the middle of the proposal's 2–5 sweet spot.
    The hook is always removed on exit, including on exception.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    try:
        from .concept_vectors import get_transformer_layers
    except ImportError:  # script mode without package context
        from concept_vectors import get_transformer_layers

    layers = get_transformer_layers(model)
    if not (0 <= layer_idx < len(layers)):
        raise ValueError(f"layer_idx {layer_idx} out of range 0..{len(layers) - 1}")

    direction = vector.detach()
    unit: Optional[object] = None
    if mode == "project":
        unit = direction / direction.norm().clamp(min=1e-12)

    def hook_fn(module, inputs, output):
        hidden = _hidden_from_layer_output(output)
        d = direction.to(device=hidden.device, dtype=hidden.dtype)
        if mode == "steer":
            hidden = hidden - strength * d
        else:
            u = unit.to(device=hidden.device, dtype=hidden.dtype)
            proj = (hidden * u).sum(dim=-1, keepdim=True)
            hidden = hidden - strength * proj * u
        return _replace_hidden_in_layer_output(output, hidden)

    handle = layers[layer_idx].register_forward_hook(hook_fn)
    try:
        yield
    finally:
        handle.remove()


def self_test() -> int:
    """No-torch checks of the reference arithmetic. Returns number of passed checks."""
    passed = 0

    # steer: subtracts strength * v elementwise
    out = _erase_pure([1.0, 2.0, 3.0], [1.0, 0.0, 1.0], 2.0, "steer")
    assert out == [-1.0, 2.0, 1.0], out
    passed += 1

    # project with strength 1 on a unit axis removes exactly that component
    out = _erase_pure([3.0, 4.0], [1.0, 0.0], 1.0, "project")
    assert out == [0.0, 4.0], out
    passed += 1

    # projecting a vector already orthogonal to v is a no-op
    out = _erase_pure([0.0, 5.0], [1.0, 0.0], 1.0, "project")
    assert out == [0.0, 5.0], out
    passed += 1

    # project is scale-invariant in v (uses v̂): same result for v and 10v
    a = _erase_pure([3.0, 4.0], [2.0, 0.0], 1.0, "project")
    b = _erase_pure([3.0, 4.0], [20.0, 0.0], 1.0, "project")
    assert a == b == [0.0, 4.0], (a, b)
    passed += 1

    # invalid mode raises
    try:
        _erase_pure([1.0], [1.0], 1.0, "nonsense")
    except ValueError:
        passed += 1
    else:  # pragma: no cover
        raise AssertionError("invalid mode did not raise")

    return passed


if __name__ == "__main__":
    n = self_test()
    print(f"erasure self-test: {n}/5 passed")
