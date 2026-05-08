"""
Explicit optimizer-parameter taxonomy and bucketed allreduce utilities.

`build_optimizer_groups` partitions a model's parameters into named groups based
on a deliberate taxonomy: Muon receives only hidden/backbone matrices; heads,
behavioral controls, zero-init adapters, and aux predictors stay on AdamW so
their small early gradients are not converted into normalized semi-orthogonal
updates. `assert_no_bad_muon_params` defends against routing regressions by
forbidding tok_emb / lm_head / heads / biases / norms / specific aux modules
from a Muon group.

`launch_bucketed_allreduce_grads` / `finish_bucketed_allreduce_grads` provide
a generic bucketed all-reduce primitive useful for cross-rank gradient averaging
of parameters not covered by a specialized optimizer's communication path.

Helpers `freeze_unused_local_only_params` / `freeze_spine_fallback_params` and
`state_dict_for_export` operate on a HYDRA-style bifurcated GPT and gate which
modules participate in training based on local-only / sage-global / spine
configuration.

Extracted from `train_gpt.py` (Farhat).
"""

from __future__ import annotations

import torch
import torch.distributed as dist
from torch import Tensor, nn


# =============================================================================
# Optimizer group taxonomy
# =============================================================================

def build_optimizer_groups(
    base_model: nn.Module,
    route_params: list[nn.Parameter],
    muon_min_params: int = 0,
    pmi_proj_adamw: bool = False,
) -> dict[str, list[nn.Parameter]]:
    """Partition `base_model.parameters()` into named optimizer groups.

    Groups (in priority order):
        embed              tok_emb.weight
        head               local_head / global_head / lm_head
        route              parameters in `route_params`
        aux_adam           lag_mix_up, sage_summary_pred, macro_*, mtp_transforms,
                           zero-init adapters (modules with `_zero_init = True`)
        small_matrix_adam  matrix params with numel() < muon_min_params
        scalar             0/1-D params + bias / norm / gate / scale / smear matches
        muon               everything remaining with ndim >= 2

    Raises if any trainable parameter is left unassigned, ensuring the taxonomy
    covers the model exhaustively (regressions surface at construction).
    """
    named = list(base_model.named_parameters())
    modules = dict(base_model.named_modules())
    route_ids = {id(p) for p in route_params if p.requires_grad}
    used: set[int] = set()

    def module_for_param(name: str) -> nn.Module | None:
        if "." not in name:
            return None
        return modules.get(name.rsplit(".", 1)[0])

    def has_any(name: str, parts: tuple[str, ...]) -> bool:
        lower = name.lower()
        return any(part in lower for part in parts)

    def take_where(pred) -> list[nn.Parameter]:
        out: list[nn.Parameter] = []
        for name, param in named:
            if not param.requires_grad or id(param) in used:
                continue
            if pred(name, param):
                out.append(param)
                used.add(id(param))
        return out

    groups: dict[str, list[nn.Parameter]] = {}
    groups["embed"] = take_where(lambda n, p: n == "tok_emb.weight")
    groups["head"] = take_where(
        lambda n, p: has_any(n, ("local_head.", "global_head.", "lm_head."))
    )
    groups["route"] = take_where(lambda n, p: id(p) in route_ids)
    groups["aux_adam"] = take_where(
        lambda n, p: (
            has_any(
                n,
                (
                    "lag_mix_up.weight",
                    "sage_summary_pred.",
                    "macro_pred.",
                    "macro_film_scale.",
                    "macro_phi_in.",
                    "macro_phi_out.",
                    "macro_distill_proj.",
                    "macro_distill_pred.",
                    "mix_proj.",
                    "mtp_transforms.",
                ),
            )
            or (pmi_proj_adamw and has_any(n, ("pmi_proj_local.",)))
            or bool(getattr(module_for_param(n), "_zero_init", False))
        )
    )
    groups["small_matrix_adam"] = take_where(
        lambda n, p: p.ndim >= 2 and p.numel() < muon_min_params
    )
    groups["scalar"] = take_where(
        lambda n, p: (
            p.ndim < 2
            or has_any(
                n,
                (
                    "bias",
                    "norm",
                    "q_gain",
                    "attn_scale",
                    "mlp_scale",
                    "continue_probe",
                    "sage_bus_gate",
                    "macro_gate",
                    "depth_gate",
                    "smear",
                ),
            )
        )
    )
    groups["muon"] = take_where(lambda n, p: p.ndim >= 2)

    leftovers = [
        (name, param)
        for name, param in named
        if param.requires_grad and id(param) not in used
    ]
    if leftovers:
        raise RuntimeError(
            "Unassigned trainable parameters:\n"
            + "\n".join(f"{name}: {tuple(param.shape)}" for name, param in leftovers)
        )
    return groups


def assert_no_bad_muon_params(base_model: nn.Module, muon_params: list[nn.Parameter]) -> None:
    """Defend against routing regressions: forbid known-bad params from Muon group.

    Muon orthogonalizes 2D matrix updates. Routing 0/1-D params, embeddings,
    heads, gates, or specific aux predictors here would silently produce broken
    updates. This guard asserts at construction.
    """
    name_by_id = {id(param): name for name, param in base_model.named_parameters()}
    forbidden = (
        "tok_emb",
        "lm_head",
        "local_head",
        "global_head",
        "mix_proj",
        "copy_gate",
        "global_continue_probe",
        "macro_pred",
        "macro_film_scale",
        "macro_distill",
        "sage_summary_pred",
        "lag_mix_up",
        "mtp_transforms",
        "bias",
        "norm",
    )
    bad: list[tuple[str, tuple[int, ...]]] = []
    for param in muon_params:
        name = name_by_id.get(id(param), "<unknown>")
        if param.ndim < 2 or any(part in name for part in forbidden):
            bad.append((name, tuple(param.shape)))
    if bad:
        raise RuntimeError(
            "Bad parameters routed to Muon:\n"
            + "\n".join(f"{name}: {shape}" for name, shape in bad)
        )


# =============================================================================
# Unused-state gating (HYDRA local-only / sage-global / spine config)
# =============================================================================

LOCAL_ONLY_UNUSED_STATE_PREFIXES: tuple[str, ...] = (
    "proj_global.",
    "global_blocks.",
    "macro_q.",
    "macro_k.",
    "macro_v.",
    "macro_pred.",
    "macro_distill_proj.",
    "macro_distill_pred.",
    "macro_film_scale.",
    "macro_phi_in.",
    "macro_phi_out.",
    "macro_q2.",
    "macro_k2.",
    "macro_v2.",
    "global_continue_probe.",
    "upsample_proj.",
    "inject_proj.",
    "global_head.",
    "mix_proj.",
    "mtp_transforms.",
)

LOCAL_ONLY_UNUSED_STATE_NAMES: set[str] = {
    "macro_gate",
    "macro_phi_gate",
    "macro_gate2",
    "upsample_gate",
    "inject_gate",
}

SAGE_GLOBAL_UNUSED_STATE_PREFIXES: tuple[str, ...] = (
    "proj_global.",
    "macro_q.",
    "macro_k.",
    "macro_v.",
    "macro_pred.",
    "macro_distill_proj.",
    "macro_distill_pred.",
    "macro_film_scale.",
    "macro_phi_in.",
    "macro_phi_out.",
    "macro_q2.",
    "macro_k2.",
    "macro_v2.",
    "upsample_proj.",
    "global_head.",
    "mix_proj.",
    "global_out_norm.",
)

SAGE_GLOBAL_UNUSED_STATE_NAMES: set[str] = {
    "macro_gate",
    "macro_phi_gate",
    "macro_gate2",
    "upsample_gate",
}


def is_unused_local_only_state_name(name: str) -> bool:
    return name in LOCAL_ONLY_UNUSED_STATE_NAMES or name.startswith(LOCAL_ONLY_UNUSED_STATE_PREFIXES)


def is_unused_sage_global_state_name(base_model: nn.Module, name: str) -> bool:
    if not getattr(base_model, "sage_enabled", False) and name.startswith("sage_bus."):
        return True
    if (
        getattr(base_model, "spine_enabled", False)
        and getattr(base_model, "spine_active", False)
        and name.startswith("sage_global_in.")
    ):
        return True
    return name in SAGE_GLOBAL_UNUSED_STATE_NAMES or name.startswith(SAGE_GLOBAL_UNUSED_STATE_PREFIXES)


def freeze_unused_local_only_params(base_model: nn.Module) -> int:
    """Freeze global-path parameters when running in local-only or sage-global mode.

    Returns the count of frozen parameters (for logging).
    """
    if not getattr(base_model, "local_only_rescue", False) and not getattr(base_model, "sage_global_enabled", False):
        return 0
    frozen = 0
    for name, param in base_model.named_parameters():
        if (
            (getattr(base_model, "local_only_rescue", False) and is_unused_local_only_state_name(name))
            or (getattr(base_model, "sage_global_enabled", False) and is_unused_sage_global_state_name(base_model, name))
        ):
            param.requires_grad_(False)
            frozen += int(param.numel())
    return frozen


def freeze_spine_fallback_params(base_model: nn.Module) -> int:
    """Freeze sage_global_in.* when the PLATO-SPINE channel is active."""
    if not (getattr(base_model, "spine_enabled", False) and getattr(base_model, "spine_active", False)):
        return 0
    frozen = 0
    for name, param in base_model.named_parameters():
        if name.startswith("sage_global_in."):
            param.requires_grad_(False)
            frozen += int(param.numel())
    return frozen


def state_dict_for_export(base_model: nn.Module) -> dict[str, Tensor]:
    """Return a state-dict pruned of frozen / unused modules for export."""
    state = base_model.state_dict()
    if getattr(base_model, "local_only_rescue", False):
        return {name: tensor for name, tensor in state.items() if not is_unused_local_only_state_name(name)}
    if getattr(base_model, "sage_global_enabled", False):
        return {
            name: tensor
            for name, tensor in state.items()
            if not is_unused_sage_global_state_name(base_model, name)
        }
    return state


# =============================================================================
# Bucketed all-reduce
# =============================================================================

@torch.no_grad()
def launch_bucketed_allreduce_grads(
    params: list[nn.Parameter],
    bucket_bytes: int,
) -> list[tuple[object, Tensor, list[tuple[nn.Parameter, int]]]]:
    """Launch async all_reduce on grads, batching small tensors into byte-size buckets.

    Each bucket flattens its members' grads (in fp32) into a single tensor and
    fires `dist.all_reduce` async. Returns a list of `(handle, flat, layout)`
    tuples to be passed to `finish_bucketed_allreduce_grads`.
    """
    handles: list[tuple[object, Tensor, list[tuple[nn.Parameter, int]]]] = []
    bucket: list[nn.Parameter] = []
    bucket_nbytes = 0

    def flush() -> None:
        nonlocal bucket, bucket_nbytes
        if not bucket:
            return
        pieces = [p.grad.detach().reshape(-1).float() for p in bucket if p.grad is not None]
        if not pieces:
            bucket = []
            bucket_nbytes = 0
            return
        flat = torch.cat(pieces)
        handle = dist.all_reduce(flat, op=dist.ReduceOp.AVG, async_op=True)
        layout = [(p, p.grad.numel()) for p in bucket if p.grad is not None]
        handles.append((handle, flat, layout))
        bucket = []
        bucket_nbytes = 0

    for param in params:
        grad = param.grad
        if grad is None:
            continue
        nbytes = grad.numel() * grad.element_size()
        if bucket and bucket_nbytes + nbytes > bucket_bytes:
            flush()
        bucket.append(param)
        bucket_nbytes += nbytes
    flush()
    return handles


@torch.no_grad()
def finish_bucketed_allreduce_grads(
    handles: list[tuple[object, Tensor, list[tuple[nn.Parameter, int]]]]
) -> None:
    """Wait on each bucket's all_reduce and copy averaged grads back to per-param tensors."""
    for handle, flat, layout in handles:
        handle.wait()
        offset = 0
        for param, numel in layout:
            if param.grad is not None:
                param.grad.copy_(flat[offset:offset + numel].reshape_as(param.grad).to(dtype=param.grad.dtype))
            offset += numel