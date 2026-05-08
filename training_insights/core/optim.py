"""
Mixed AdamW / Muon optimizer for matrix parameter training.

Muon (MomentUm Orthogonalized by Newton-schulz) reshapes 2D parameter updates
through approximate orthogonalization, applied to hidden/backbone matrices.
AdamW handles embeddings, heads, scalars, and zero-init adapters where small
early gradients should not be normalized.

This module exposes:
  - MuonAdamW            single-GPU combined optimizer
  - DistMuonAdamW        multi-GPU combined optimizer (ZeRO-2-style sharding)
  - orthogonalize_muon_update / zeropower_via_*  orthogonalizer backends
  - build_muon_orthogonalizer_config             variant + config helper
  - clip_grad_norm_no_sync_                      device-local grad clipping

The Muon system supports five variants and two orthogonalizer backends:
  Variants:       standard5, standard4, polar_express5, turbo4_aol, custom
  Backends:       Newton-Schulz polynomial (standard_ns), stabilized
                  Gram-Newton-Schulz with restart (stabilized_gram_ns)
  Optional:       AOL (Absolute-Off-the-wall) diagonal equilibration on
                  the column Gram before orthogonalization

The Polar Express coefficients used here are calibrated for safety_factor=1.05
and a 5-iteration schedule, per Amsel et al. 2025 (arXiv:2505.16932). The
stabilized Gram-NS backend uses a configurable restart pattern to avoid
fixed-point drift across long iteration chains.

Adapted from `train_gpt.py` (Farhat); AdamW fused kernel preserved.
"""

import torch
import torch.distributed as dist
from torch import Tensor

# =============================================================================
# Muon coefficient banks
# =============================================================================

MUON_STANDARD_COEFFS: tuple[tuple[float, float, float], ...] = (
    (3.4445, -4.7750, 2.0315),
)

# Polar Express, num_iters=5, safety_factor=2e-2, cushion=2 (Amsel et al. 2025)
MUON_POLAR_EXPRESS_UNSCALED_COEFFS: tuple[tuple[float, float, float], ...] = (
    (8.28721201814563, -23.595886519098837, 17.300387312530933),
    (4.107059111542203, -2.9478499167379106, 0.5448431082926601),
    (3.9486908534822946, -2.908902115962949, 0.5518191394370137),
    (3.3184196573706015, -2.488488024314874, 0.51004894012372),
    (2.300652019954817, -1.6689039845747493, 0.4188073119525673),
)

MUON_POLAR_EXPRESS_SAFETY: float = 1.05

MUON_POLAR_EXPRESS_COEFFS: tuple[tuple[float, float, float], ...] = tuple(
    (
        a / MUON_POLAR_EXPRESS_SAFETY,
        b / (MUON_POLAR_EXPRESS_SAFETY ** 3),
        c / (MUON_POLAR_EXPRESS_SAFETY ** 5),
    )
    for a, b, c in MUON_POLAR_EXPRESS_UNSCALED_COEFFS
)


def parse_muon_coeffs(spec: str) -> tuple[tuple[float, float, float], ...]:
    """Parse semicolon-separated 'a,b,c' triples into Muon coefficients."""
    coeffs: list[tuple[float, float, float]] = []
    for chunk in spec.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [part.strip() for part in chunk.split(",")]
        if len(parts) != 3:
            raise ValueError(
                "Muon custom coefficients must be semicolon-separated 'a,b,c' triples; "
                f"got malformed chunk: {chunk!r}"
            )
        coeffs.append((float(parts[0]), float(parts[1]), float(parts[2])))
    if not coeffs:
        raise ValueError("Muon custom coefficients must define at least one triple when variant='custom'")
    return tuple(coeffs)


def build_muon_orthogonalizer_config(
    *,
    variant: str = "polar_express5",
    custom_coeffs: str = "",
    aol_eps: float = 1e-6,
    aol_scale_cap: float = 1.0,
    ortho_impl: str = "stabilized_gram_ns",
    gram_restart_every: int = 2,
    gram_force_fp32: bool = False,
    gram_dtype: str = "float16",
    gram_renorm_after_restart: bool = False,
) -> dict[str, object]:
    """Build an orthogonalizer config dict from named parameters.

    Variant selects coefficient bank and AOL usage. Backend selects which
    orthogonalization implementation runs. The Gram-NS knobs apply only when
    ortho_impl='stabilized_gram_ns'.
    """
    variant = variant.strip().lower()
    if variant == "standard5":
        coeffs = MUON_STANDARD_COEFFS * 5
        use_aol = False
    elif variant == "standard4":
        coeffs = MUON_STANDARD_COEFFS * 4
        use_aol = False
    elif variant == "polar_express5":
        coeffs = MUON_POLAR_EXPRESS_COEFFS
        use_aol = False
    elif variant == "turbo4_aol":
        coeffs = MUON_STANDARD_COEFFS * 4
        use_aol = True
    elif variant == "custom":
        coeffs = parse_muon_coeffs(custom_coeffs)
        use_aol = True
    else:
        raise ValueError(
            f"Unknown Muon variant={variant!r}; expected one of "
            "'standard5', 'standard4', 'polar_express5', 'turbo4_aol', 'custom'"
        )

    ortho_impl = ortho_impl.strip().lower()
    if ortho_impl not in ("standard_ns", "stabilized_gram_ns"):
        raise ValueError(
            f"Unknown Muon ortho_impl={ortho_impl!r}; expected 'standard_ns' or 'stabilized_gram_ns'"
        )

    return {
        "variant": variant,
        "coeffs": coeffs,
        "use_aol": use_aol,
        "aol_eps": aol_eps,
        "aol_scale_cap": aol_scale_cap,
        "ortho_impl": ortho_impl,
        "gram_restart_every": gram_restart_every,
        "gram_force_fp32": gram_force_fp32,
        "gram_dtype": gram_dtype.strip().lower(),
        "gram_renorm_after_restart": gram_renorm_after_restart,
    }


def _default_orthogonalizer_config(steps: int) -> dict[str, object]:
    """Fallback config used when an orthogonalizer is called without one."""
    return {
        "variant": "standard5",
        "coeffs": MUON_STANDARD_COEFFS * steps,
        "use_aol": False,
        "aol_eps": 1e-6,
        "aol_scale_cap": 0.0,
        "ortho_impl": "standard_ns",
        "gram_restart_every": 2,
        "gram_force_fp32": False,
        "gram_dtype": "float16",
        "gram_renorm_after_restart": True,
    }


# =============================================================================
# Orthogonalization backends
# =============================================================================

def apply_aol_preconditioner(X: Tensor, eps: float, scale_cap: float) -> Tensor:
    """AOL-style diagonal equilibration on the column Gram matrix in fp32."""
    gram = X.mT @ X
    scales = torch.rsqrt(gram.abs().sum(dim=-1).clamp_min(eps))
    if scale_cap > 0.0:
        scales = scales.clamp(max=scale_cap)
    return X * scales.unsqueeze(-2)


def zeropower_via_newtonschulz5(
    G: Tensor,
    steps: int = 5,
    eps: float = 1e-7,
    *,
    orthogonalizer_config: dict[str, object] | None = None,
) -> Tensor:
    """Batched Newton-Schulz orthogonalization.

    G shape: (B, M, N) or (M, N). The fp32 polynomial path is preserved; the
    config selects which coefficient bank runs (and whether AOL preconditioning
    is applied first).
    """
    config = orthogonalizer_config or _default_orthogonalizer_config(steps)
    coeffs = tuple(config["coeffs"])

    was_2d = G.ndim == 2
    if was_2d:
        G = G.unsqueeze(0)

    X = G.bfloat16()
    transposed = X.size(-2) > X.size(-1)
    if transposed:
        X = X.mT
    X = X / (X.norm(dim=(-2, -1), keepdim=True) + eps)

    if bool(config.get("use_aol", False)):
        X = apply_aol_preconditioner(
            X.float(),
            eps=float(config.get("aol_eps", 1e-6)),
            scale_cap=float(config.get("aol_scale_cap", 0.0)),
        ).bfloat16()

    for a, b, c in coeffs:
        # fp32 for the entire polynomial — Gram + squaring + application
        Xf = X.float()
        A = Xf @ Xf.mT
        B = b * A + c * (A @ A)
        X = (a * Xf + B @ Xf).bfloat16()

    if transposed:
        X = X.mT
    if was_2d:
        X = X.squeeze(0)
    return X


def zeropower_via_stabilized_gram_newtonschulz(
    G: Tensor,
    steps: int = 5,
    eps: float = 1e-7,
    *,
    orthogonalizer_config: dict[str, object] | None = None,
) -> Tensor:
    """Stabilized Gram-Newton-Schulz backend with optional restart.

    Operates on R = X X^T directly to avoid fixed-point drift in long iteration
    chains. Restarts re-form X = Q X and recompute R after `gram_restart_every`
    iterations. Falls back to the polynomial NS path for square inputs where
    Gram-NS provides no advantage.
    """
    config = orthogonalizer_config or _default_orthogonalizer_config(steps)
    coeffs = tuple(config.get("coeffs", MUON_STANDARD_COEFFS * steps))
    restart_after = int(config.get("gram_restart_every", 2))
    force_fp32 = bool(config.get("gram_force_fp32", True))
    gram_dtype_name = str(config.get("gram_dtype", "float16")).lower()
    renorm_after_restart = bool(config.get("gram_renorm_after_restart", True))

    if force_fp32:
        work_dtype = torch.float32
    elif gram_dtype_name in ("float16", "fp16", "half"):
        work_dtype = torch.float16
    elif gram_dtype_name in ("bfloat16", "bf16"):
        work_dtype = torch.bfloat16
    elif gram_dtype_name in ("float32", "fp32"):
        work_dtype = torch.float32
    else:
        raise ValueError(f"Unknown gram_dtype={gram_dtype_name!r}; expected float16, bfloat16, or float32")

    restart_indices = {restart_after} if 0 < restart_after < len(coeffs) else set()

    input_dtype = G.dtype
    was_2d = G.ndim == 2
    if was_2d:
        G = G.unsqueeze(0)
    if G.ndim != 3:
        raise ValueError(f"Gram-NS expects G to be 2D or 3D, got shape={tuple(G.shape)}")

    X = G
    transposed = X.size(-2) > X.size(-1)
    if transposed:
        X = X.mT
    if X.size(-2) == X.size(-1):
        # Square inputs: Gram-NS offers no benefit over the polynomial path
        return zeropower_via_newtonschulz5(
            G.squeeze(0) if was_2d else G,
            steps=steps,
            eps=eps,
            orthogonalizer_config=orthogonalizer_config,
        )

    X = X.float()
    X = X / (X.norm(dim=(-2, -1), keepdim=True) + eps)

    if bool(config.get("use_aol", False)):
        X = apply_aol_preconditioner(
            X,
            eps=float(config.get("aol_eps", 1e-6)),
            scale_cap=float(config.get("aol_scale_cap", 0.0)),
        )
        X = X / (X.norm(dim=(-2, -1), keepdim=True) + eps)

    X = X.to(work_dtype)
    R = X @ X.mT
    eye = torch.eye(R.size(-1), device=R.device, dtype=R.dtype).unsqueeze(0).expand(R.size(0), -1, -1)
    Q: Tensor | None = None

    for idx, (a, b, c) in enumerate(coeffs):
        if idx in restart_indices and Q is not None:
            X = Q @ X
            if renorm_after_restart:
                X = X / (X.norm(dim=(-2, -1), keepdim=True) + eps)
            R = X @ X.mT
            Q = None

        Z = b * R + c * (R @ R)
        if Q is None:
            Q = Z + a * eye
        else:
            Q = Q @ Z + a * Q

        if idx < len(coeffs) - 1 and (idx + 1) not in restart_indices:
            RZ = R @ Z + a * R
            R = Z @ RZ + a * RZ
            R = 0.5 * (R + R.mT)

    if Q is not None:
        X = Q @ X

    if transposed:
        X = X.mT
    if was_2d:
        X = X.squeeze(0)
    return X.to(dtype=input_dtype)


def orthogonalize_muon_update(
    update: Tensor,
    *,
    steps: int,
    orthogonalizer_config: dict[str, object],
) -> Tensor:
    """Dispatcher: route to the configured backend."""
    ortho_impl = str(orthogonalizer_config.get("ortho_impl", "standard_ns"))
    if ortho_impl == "stabilized_gram_ns":
        return zeropower_via_stabilized_gram_newtonschulz(
            update,
            steps=steps,
            orthogonalizer_config=orthogonalizer_config,
        )
    return zeropower_via_newtonschulz5(
        update,
        steps=steps,
        orthogonalizer_config=orthogonalizer_config,
    )


# =============================================================================
# AdamW fused kernel
# =============================================================================

@torch.compile(dynamic=False, fullgraph=True)
def adamw_step_fused(
    p: Tensor,
    grad: Tensor,
    exp_avg: Tensor,
    exp_avg_sq: Tensor,
    step_t: Tensor,
    lr_t: Tensor,
    beta1_t: Tensor,
    beta2_t: Tensor,
    eps_t: Tensor,
    wd_t: Tensor,
) -> None:
    """Fused AdamW: weight_decay -> momentum_update -> bias_correction -> param_update.

    All ops in one compiled graph to eliminate Python overhead between them.
    The 0-D CPU tensors avoid recompilation when hyperparameter values change.
    """
    p.mul_(1 - lr_t * wd_t)
    exp_avg.lerp_(grad, 1 - beta1_t)
    exp_avg_sq.lerp_(grad.square(), 1 - beta2_t)
    bias1 = 1 - beta1_t ** step_t
    bias2 = 1 - beta2_t ** step_t
    denom = (exp_avg_sq / bias2).sqrt() + eps_t
    step_size = lr_t / bias1
    p.add_(exp_avg / denom, alpha=-step_size)


# =============================================================================
# MuonAdamW: single-GPU combined optimizer
# =============================================================================

class MuonAdamW(torch.optim.Optimizer):
    """Combined optimizer: Muon for 2D matrix params, AdamW for others (single GPU).

    Each param group must specify 'kind': 'adamw' or 'muon'.

    AdamW group fields:
      lr, betas, eps, weight_decay
    Muon group fields:
      lr, momentum, ns_steps, weight_decay
      orthogonalizer_config (optional, dict from build_muon_orthogonalizer_config)
      nesterov (optional, default True)

    Muon caveats (preserved from the original design):
      - Embeddings, final fully connected layer, and any 0/1-D parameters
        should NOT be in a Muon group; route them through AdamW.
      - For 4D conv filters, flatten the last 3 dims before adding to a
        Muon group.
    """

    def __init__(self, param_groups: list[dict]):
        super().__init__(param_groups, defaults={})
        # 0-D CPU tensors avoid torch.compile recompilation on value changes.
        self._adamw_step_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_lr_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_beta1_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_beta2_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_eps_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_wd_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")

    def _step_adamw(self, group: dict) -> None:
        for p in group['params']:
            if p.grad is None:
                continue
            grad = p.grad
            state = self.state[p]
            if not state:
                state['step'] = 0
                state['exp_avg'] = torch.zeros_like(p)
                state['exp_avg_sq'] = torch.zeros_like(p)
            state['step'] += 1

            self._adamw_step_t.fill_(state['step'])
            self._adamw_lr_t.fill_(group['lr'])
            self._adamw_beta1_t.fill_(group['betas'][0])
            self._adamw_beta2_t.fill_(group['betas'][1])
            self._adamw_eps_t.fill_(group['eps'])
            self._adamw_wd_t.fill_(group['weight_decay'])

            adamw_step_fused(
                p, grad, state['exp_avg'], state['exp_avg_sq'],
                self._adamw_step_t, self._adamw_lr_t, self._adamw_beta1_t,
                self._adamw_beta2_t, self._adamw_eps_t, self._adamw_wd_t,
            )

    def _step_muon(self, group: dict) -> None:
        params: list[Tensor] = group['params']
        if not params:
            return
        lr = group['lr']
        momentum = group['momentum']
        nesterov = group.get('nesterov', True)
        wd = group.get('weight_decay', 0.0)
        steps = group['ns_steps']
        ortho_cfg = group.get('orthogonalizer_config') or _default_orthogonalizer_config(steps)

        # Same-shape buckets for batched orthogonalization.
        buckets: dict[tuple[int, ...], list[Tensor]] = {}
        for p in params:
            if p.grad is None:
                continue
            buckets.setdefault(tuple(p.shape), []).append(p)

        for shape, bucket_params in buckets.items():
            # Per-param momentum (fp32) so all updates are computed in the same precision
            updates: list[Tensor] = []
            for p in bucket_params:
                state = self.state[p]
                if 'momentum_buffer' not in state:
                    state['momentum_buffer'] = torch.zeros_like(p, dtype=torch.float32)
                buf = state['momentum_buffer']
                g = p.grad.float()
                buf.mul_(momentum).add_(g)
                update = g.add(buf, alpha=momentum) if nesterov else buf
                updates.append(update)

            if len(updates) >= 2:
                stacked = torch.stack(updates, dim=0)
                orthog = orthogonalize_muon_update(
                    stacked, steps=steps, orthogonalizer_config=ortho_cfg,
                )
                final_updates = [orthog[i] for i in range(orthog.size(0))]
            else:
                final_updates = [
                    orthogonalize_muon_update(
                        u, steps=steps, orthogonalizer_config=ortho_cfg,
                    )
                    for u in updates
                ]

            scale = max(1.0, shape[-2] / shape[-1]) ** 0.5
            for p, update in zip(bucket_params, final_updates):
                if wd > 0.0:
                    p.data.mul_(1.0 - lr * wd)
                p.add_(update.to(dtype=p.dtype), alpha=-lr * scale)

    @torch.no_grad()
    def step(self):
        for group in self.param_groups:
            kind = group['kind']
            if kind == 'adamw':
                self._step_adamw(group)
            elif kind == 'muon':
                self._step_muon(group)
            else:
                raise ValueError(f"Unknown optimizer kind: {kind!r}")


# =============================================================================
# DistMuonAdamW: distributed combined optimizer (ZeRO-2 style)
# =============================================================================

class DistMuonAdamW(torch.optim.Optimizer):
    """Combined distributed optimizer: Muon for 2D matrix params, AdamW for others.

    Communication design:

      AdamW (ZeRO-2 style):
        - Small params (<1024 elements): all_reduce gradients, replicate update.
        - Large params: reduce_scatter the grad, update only this rank's slice,
          then all_gather the updated slices. Optimizer state (exp_avg,
          exp_avg_sq) is sharded; requires param.shape[0] % world_size == 0.

      Muon (stacked + chunked):
        - Each Muon group's params must share shape (caller's responsibility,
          enforced by build_optimizer_groups).
        - Stack K params into (K, *shape); each rank owns ceil(K/world_size).
        - reduce_scatter the stacked grads, update only the owned chunk, then
          all_gather to reconstruct full updated params.
        - Padding to (ceil(K/N) * N) handles uneven divisions.

      3-phase async pattern (launch reduces -> compute updates -> wait gathers)
      maximizes overlap between communication and computation.

    Group fields are identical to MuonAdamW.
    """

    def __init__(self, param_groups: list[dict]):
        super().__init__(param_groups, defaults={})
        self._adamw_step_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_lr_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_beta1_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_beta2_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_eps_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        self._adamw_wd_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")

    # --- AdamW ---------------------------------------------------------------

    def _reduce_adamw(self, group: dict, world_size: int) -> dict:
        param_infos = {}
        for p in group['params']:
            grad = p.grad
            if grad is None:
                continue
            if p.numel() < 1024:
                future = dist.all_reduce(grad, op=dist.ReduceOp.AVG, async_op=True).get_future()
                param_infos[p] = dict(future=future, grad_slice=grad, is_small=True)
            else:
                assert grad.shape[0] % world_size == 0, (
                    f"AdamW reduce_scatter requires shape[0] ({grad.shape[0]}) "
                    f"divisible by world_size ({world_size})"
                )
                rank_size = grad.shape[0] // world_size
                grad_slice = torch.empty_like(grad[:rank_size])
                future = dist.reduce_scatter_tensor(
                    grad_slice, grad, op=dist.ReduceOp.AVG, async_op=True,
                ).get_future()
                param_infos[p] = dict(future=future, grad_slice=grad_slice, is_small=False)
        return dict(param_infos=param_infos)

    def _compute_adamw(
        self, group: dict, info: dict, gather_list: list,
        rank: int, world_size: int,
    ) -> None:
        param_infos = info['param_infos']
        for p in group['params']:
            if p not in param_infos:
                continue
            pinfo = param_infos[p]
            pinfo['future'].wait()
            grad_slice = pinfo['grad_slice']
            state = self.state[p]

            if pinfo['is_small']:
                p_slice = p
            else:
                rank_size = p.shape[0] // world_size
                p_slice = p[rank * rank_size:(rank + 1) * rank_size]

            if not state:
                state['step'] = 0
                state['exp_avg'] = torch.zeros_like(p_slice)
                state['exp_avg_sq'] = torch.zeros_like(p_slice)
            state['step'] += 1

            self._adamw_step_t.fill_(state['step'])
            self._adamw_lr_t.fill_(group['lr'])
            self._adamw_beta1_t.fill_(group['betas'][0])
            self._adamw_beta2_t.fill_(group['betas'][1])
            self._adamw_eps_t.fill_(group['eps'])
            self._adamw_wd_t.fill_(group['weight_decay'])
            adamw_step_fused(
                p_slice, grad_slice, state['exp_avg'], state['exp_avg_sq'],
                self._adamw_step_t, self._adamw_lr_t, self._adamw_beta1_t,
                self._adamw_beta2_t, self._adamw_eps_t, self._adamw_wd_t,
            )

            if not pinfo['is_small']:
                future = dist.all_gather_into_tensor(p, p_slice, async_op=True).get_future()
                gather_list.append(dict(future=future, params=None))

    # --- Muon ----------------------------------------------------------------

    def _reduce_muon(self, group: dict, world_size: int) -> dict:
        params = group['params']
        chunk_size = (len(params) + world_size - 1) // world_size
        padded_num_params = chunk_size * world_size
        p = params[0]
        shape, device = p.shape, p.device

        # fp32 buffers throughout to eliminate cross-rank bf16 rounding divergence
        # (creates non-cancelling gradient noise otherwise).
        grad_stack = torch.stack([pp.grad for pp in params if pp.grad is not None]).float()
        stacked_grads = torch.empty(
            padded_num_params, *shape, dtype=torch.float32, device=device,
        )
        stacked_grads[:grad_stack.size(0)].copy_(grad_stack)
        if grad_stack.size(0) < padded_num_params:
            stacked_grads[grad_stack.size(0):].zero_()

        grad_chunk = torch.empty(chunk_size, *shape, dtype=torch.float32, device=device)
        future = dist.reduce_scatter_tensor(
            grad_chunk, stacked_grads, op=dist.ReduceOp.AVG, async_op=True,
        ).get_future()

        return dict(
            future=future,
            grad_chunk=grad_chunk,
            stacked_grads=stacked_grads,
            chunk_size=chunk_size,
            num_real_params=len(params),
        )

    def _compute_muon(self, group: dict, info: dict, gather_list: list, rank: int) -> None:
        info['future'].wait()
        params = group['params']
        chunk_size = info['chunk_size']
        grad_chunk = info['grad_chunk']
        p = params[0]
        shape, device = p.shape, p.device

        start_idx = rank * chunk_size
        num_owned = min(chunk_size, max(0, len(params) - start_idx))

        steps = group['ns_steps']
        momentum = group['momentum']
        nesterov = group.get('nesterov', True)
        wd = group.get('weight_decay', 0.0)
        ortho_cfg = group.get('orthogonalizer_config') or _default_orthogonalizer_config(steps)

        # Group-level momentum buffer, sharded by chunk
        state = self.state[p]
        if 'shard_mom' not in state:
            state['shard_mom'] = torch.zeros(chunk_size, *shape, dtype=torch.float32, device=device)
        shard_mom = state['shard_mom']

        updated_params = torch.empty(chunk_size, *shape, dtype=torch.float32, device=device)

        if num_owned > 0:
            owned_grads = grad_chunk[:num_owned]
            owned_mom = shard_mom[:num_owned]
            owned_mom.mul_(momentum).add_(owned_grads)
            update = owned_grads.add(owned_mom, alpha=momentum) if nesterov else owned_mom

            orthog = orthogonalize_muon_update(
                update, steps=steps, orthogonalizer_config=ortho_cfg,
            )
            scale = max(1.0, shape[-2] / shape[-1]) ** 0.5

            owned_params = [params[start_idx + i] for i in range(num_owned)]
            stacked_owned = torch.stack(owned_params).float()
            if wd > 0.0:
                stacked_owned.mul_(1.0 - group['lr'] * wd)
            stacked_owned.add_(orthog, alpha=-group['lr'] * scale)
            updated_params[:num_owned].copy_(stacked_owned)

        if num_owned < chunk_size:
            updated_params[num_owned:].zero_()

        # Reuse the stacked_grads buffer for all_gather output.
        stacked_params = info['stacked_grads']
        future = dist.all_gather_into_tensor(
            stacked_params, updated_params, async_op=True,
        ).get_future()
        gather_list.append(dict(
            future=future,
            stacked_params=stacked_params,
            params=params,
        ))

    def _finish_gathers(self, gather_list: list) -> None:
        for info in gather_list:
            info['future'].wait()
            if info['params'] is not None:
                # Muon: copy from stacked buffer back to individual params, casting back.
                params = info['params']
                stacked = info['stacked_params'][:len(params)]
                for p, slab in zip(params, stacked.unbind(0)):
                    p.data.copy_(slab.to(dtype=p.dtype))

    @torch.no_grad()
    def step(self):
        rank = dist.get_rank()
        world_size = dist.get_world_size()

        # Phase 1: launch all async reduce ops.
        reduce_infos: list[dict] = []
        for group in self.param_groups:
            kind = group['kind']
            if kind == 'adamw':
                reduce_infos.append(self._reduce_adamw(group, world_size))
            elif kind == 'muon':
                reduce_infos.append(self._reduce_muon(group, world_size))
            else:
                raise ValueError(f"Unknown optimizer kind: {kind!r}")

        # Phase 2: wait for reduces, compute updates, launch gathers.
        gather_list: list[dict] = []
        for group, info in zip(self.param_groups, reduce_infos):
            kind = group['kind']
            if kind == 'adamw':
                self._compute_adamw(group, info, gather_list, rank, world_size)
            elif kind == 'muon':
                self._compute_muon(group, info, gather_list, rank)

        # Phase 3: wait for gathers, copy back.
        self._finish_gathers(gather_list)


# =============================================================================
# Utility: device-local gradient clipping
# =============================================================================

@torch.no_grad()
def clip_grad_norm_no_sync_(
    parameters,
    max_norm: float,
    eps: float = 1e-6,
) -> Tensor:
    """Clip grads in place on GPU without the normal-path host sync.

    Clip local accumulated grads before any cross-rank averaging. On nonfinite
    total norm, leaves grads untouched (caller-side guard handles the skip).
    """
    params = list(parameters)
    grads_by_group: dict[tuple[torch.device, torch.dtype], list[Tensor]] = {}
    first_device: torch.device | None = None

    for p in params:
        grad = p.grad
        if grad is None:
            continue
        if grad.is_sparse:
            raise RuntimeError("Sparse gradients are not supported in clip_grad_norm_no_sync_")
        if first_device is None:
            first_device = grad.device
        grads_by_group.setdefault((grad.device, grad.dtype), []).append(grad)

    if first_device is None:
        fallback_device = (
            params[0].device if params
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        return torch.zeros((), device=fallback_device, dtype=torch.float32)

    total_sq = torch.zeros((), device=first_device, dtype=torch.float32)
    grouped_grads: list[tuple[torch.device, list[Tensor]]] = []
    for (device, _dtype), grads in grads_by_group.items():
        grouped_grads.append((device, grads))
        norms: list[Tensor] | None = None
        if hasattr(torch, "_foreach_norm"):
            try:
                norms = list(torch._foreach_norm(grads, 2.0))
            except RuntimeError:
                norms = None
        if norms is not None:
            total_sq.add_(
                torch.stack([
                    norm.to(device=first_device, dtype=torch.float32).square()
                    for norm in norms
                ]).sum()
            )
            continue
        for grad in grads:
            total_sq.add_(grad.float().square().sum().to(device=first_device))

    total_norm = total_sq.sqrt()
    clip_scale = torch.where(
        torch.isfinite(total_norm),
        torch.clamp(float(max_norm) / (total_norm + eps), max=1.0),
        torch.ones_like(total_norm),
    )

    for device, grads in grouped_grads:
        scale = clip_scale.to(device=device)
        if hasattr(torch, "_foreach_mul_"):
            try:
                torch._foreach_mul_(grads, scale)
                continue
            except RuntimeError:
                pass
        for grad in grads:
            grad.mul_(scale)

    return total_norm
