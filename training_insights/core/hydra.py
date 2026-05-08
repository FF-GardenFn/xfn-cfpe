"""
HYDRA architectural primitives — bifurcated local/global attention building blocks.

These are the reusable building blocks of the bifurcated recurrent language model
in `train_gpt.py`. They define a dual-path attention regime:

  * **Local path**: full-resolution sliding-window causal attention with RoPE,
    QK normalization, and a chunked-mask attention that lets each window also
    attend to its predecessor (preserves cross-chunk information at chunk
    granularity).

  * **Global path**: pooled latent-bottleneck causal attention with grouped
    query support; intended to operate on coarser-resolution summaries
    (chunk-pooled or otherwise reduced) and contribute long-range signal to
    the local stream.

Auxiliary primitives include:
  - `RMSNorm` — module wrapper around `F.rms_norm`
  - `Rotary` / `apply_rotary_emb` — RoPE rotation cache + application
  - `SmearGate` — per-channel blend of a token with its predecessor
  - `CausalInterferometer` — pairwise past-lag phase mixer inserted before local QKV
  - `HydraMLP` — gate-up SiLU MLP using QATLinear
  - `SageBus` — Surprise-Anchored Global Echo, a deterministic-routing global-to-
    local context injection driven by bigram entropy and structural anchor signals

This module re-exports `QATLinear` so callers don't need a separate import.

Extracted from `train_gpt.py` (Farhat).
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor, nn

from core.quant import QATLinear


# =============================================================================
# Norms, rotations, gates
# =============================================================================

class RMSNorm(nn.Module):
    """Module wrapper for `F.rms_norm` with optional explicit epsilon."""

    def __init__(self, eps: float | None = None):
        super().__init__()
        self.eps = eps

    def forward(self, x: Tensor) -> Tensor:
        return F.rms_norm(x, (x.size(-1),), eps=self.eps)


class Rotary(nn.Module):
    """Rotary positional embedding cache. Caches `cos`/`sin` per (seq_len, device)."""

    def __init__(self, dim: int, base: float = 10000.0):
        super().__init__()
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        self._seq_len_cached = 0
        self._cos_cached: Tensor | None = None
        self._sin_cached: Tensor | None = None

    def forward(self, seq_len: int, device: torch.device, dtype: torch.dtype) -> tuple[Tensor, Tensor]:
        if (
            self._cos_cached is None
            or self._sin_cached is None
            or self._seq_len_cached != seq_len
            or self._cos_cached.device != device
        ):
            t = torch.arange(seq_len, device=device, dtype=self.inv_freq.dtype)
            freqs = torch.outer(t, self.inv_freq.to(device))
            self._cos_cached = freqs.cos()[None, None, :, :]
            self._sin_cached = freqs.sin()[None, None, :, :]
            self._seq_len_cached = seq_len
        return self._cos_cached.to(dtype=dtype), self._sin_cached.to(dtype=dtype)


def apply_rotary_emb(x: Tensor, cos: Tensor, sin: Tensor) -> Tensor:
    """Apply RoPE rotation to the second half of the channel dimension."""
    half = x.size(-1) // 2
    x1, x2 = x[..., :half], x[..., half:]
    return torch.cat((x1 * cos + x2 * sin, x1 * (-sin) + x2 * cos), dim=-1)


class SmearGate(nn.Module):
    """Per-channel learnable blend of each token embedding with its predecessor.

    `out[t] = (1 - σ(g)) * x[t] + σ(g) * x[t-1]`

    Useful immediately after the embedding layer to give the model cheap access
    to local history without committing attention budget.
    """

    def __init__(self, dim: int):
        super().__init__()
        self.gate = nn.Parameter(torch.zeros(dim, dtype=torch.float32))

    def forward(self, x: Tensor) -> Tensor:
        gate = torch.sigmoid(self.gate.to(dtype=x.dtype))[None, None, :]
        prev = torch.cat([torch.zeros_like(x[:, :1]), x[:, :-1]], dim=1)
        return (1.0 - gate) * x + gate * prev


# =============================================================================
# MLP, interferometer
# =============================================================================

class HydraMLP(nn.Module):
    """Gate-up SiLU MLP using `QATLinear` for both projections."""

    def __init__(self, dim: int, mlp_mult: float, group_size: int = 128):
        super().__init__()
        hidden_dim = int(dim * mlp_mult)
        self.gate_up = QATLinear(dim, 2 * hidden_dim, bias=False, group_size=group_size)
        self.down = QATLinear(hidden_dim, dim, bias=False, group_size=group_size)

    def forward(self, x: Tensor) -> Tensor:
        gate_up = self.gate_up(x)
        gate, up = gate_up.chunk(2, dim=-1)
        return self.down(F.silu(gate) * up)


class CausalInterferometer(nn.Module):
    """Pairwise past-lag phase mixer inserted before local QKV.

    Concatenates four lag combinations of the input `(x + x_lag1, x - x_lag1,
    x_lag2 + x_lag4, x_lag2 - x_lag4)` and projects through a bottleneck SiLU
    block. The output is residually added with a learnable scalar gate. This
    gives local attention cheap access to a 4-tap phase-difference signal
    without spending attention heads on it.

    Real-valued analogue of complex-pair sum/phase-difference; the bottleneck
    `lag_mix_up` is zero-initialized so the module starts inactive.
    """

    def __init__(self, dim: int, gate_init: float = -3.0, group_size: int = 128):
        super().__init__()
        bottleneck = max(dim // 4, 16)
        self.lag_norm = RMSNorm()
        self.lag_mix_down = QATLinear(4 * dim, bottleneck, bias=False, group_size=group_size)
        self.lag_mix_up = QATLinear(bottleneck, dim, bias=False, group_size=group_size)
        self.lag_mix_up._zero_init = True
        self.lag_gate = nn.Parameter(torch.tensor(gate_init, dtype=torch.float32))

    @staticmethod
    def _shift_right(x: Tensor, lag: int) -> Tensor:
        if lag <= 0:
            return x
        pad = torch.zeros_like(x[:, :lag])
        return torch.cat([pad, x[:, :-lag]], dim=1)

    def forward(self, x: Tensor, route_stats: dict[str, list[Tensor]] | None = None) -> Tensor:
        x0 = x
        x1 = self._shift_right(x, 1)
        x2 = self._shift_right(x, 2)
        x4 = self._shift_right(x, 4)
        z = torch.cat([x0 + x1, x0 - x1, x2 + x4, x2 - x4], dim=-1)
        z = self.lag_mix_up(F.silu(self.lag_mix_down(self.lag_norm(z))))
        gate = torch.sigmoid(self.lag_gate.float()).to(dtype=x.dtype)
        if route_stats is not None:
            route_stats.setdefault("interferometer_gate", []).append(gate.detach().float())
            route_stats.setdefault("interferometer_norm", []).append(z.detach().float().norm(dim=-1).mean())
        return x + gate * z


# =============================================================================
# Global path
# =============================================================================

class HydraGlobalSelfAttention(nn.Module):
    """Pooled latent-bottleneck causal attention with grouped-query support.

    K and V are projected through a low-rank latent (`kv_down` then `kv_up`),
    which compresses the KV cache and reduces the QKV-projection FLOPs at the
    cost of an extra matmul. RoPE and per-head Q-gain are applied. An optional
    XSA (eXternal-Subspace Annihilation) projection is supported for ablations.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int,
        num_kv_heads: int,
        rope_base: float,
        qk_gain_init: float,
        group_size: int = 128,
        latent_dim: int = 128,
    ):
        super().__init__()
        if dim % num_heads != 0:
            raise ValueError("dim must be divisible by num_heads")
        if num_heads % num_kv_heads != 0:
            raise ValueError("num_heads must be divisible by num_kv_heads")
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = dim // num_heads
        if self.head_dim % 2 != 0:
            raise ValueError("head_dim must be even for RoPE")
        kv_dim = num_kv_heads * self.head_dim
        self.q_proj = QATLinear(dim, dim, bias=False, group_size=group_size)
        self.kv_down = QATLinear(dim, latent_dim, bias=False, group_size=group_size)
        self.kv_up = QATLinear(latent_dim, 2 * kv_dim, bias=False, group_size=group_size)
        self.out_proj = QATLinear(dim, dim, bias=False, group_size=group_size)
        self.q_gain = nn.Parameter(torch.full((num_heads,), qk_gain_init, dtype=torch.float32))
        self.rotary = Rotary(self.head_dim, base=rope_base)
        self.use_xsa = False

    def _xsa_efficient(self, y: Tensor, v: Tensor) -> Tensor:
        bsz, heads, seqlen, head_dim = y.shape
        kv_heads = v.size(1)
        group = heads // kv_heads
        y_grouped = y.reshape(bsz, kv_heads, group, seqlen, head_dim)
        vn = F.normalize(v, dim=-1).unsqueeze(2)
        proj = (y_grouped * vn).sum(dim=-1, keepdim=True) * vn
        return (y_grouped - proj).reshape(bsz, heads, seqlen, head_dim)

    def forward(self, x: Tensor) -> Tensor:
        bsz, seqlen, dim = x.shape
        q = self.q_proj(x).reshape(bsz, seqlen, self.num_heads, self.head_dim).transpose(1, 2)
        latent = self.kv_down(x)
        kv = self.kv_up(latent)
        kv_dim = self.num_kv_heads * self.head_dim
        k, v = kv.split([kv_dim, kv_dim], dim=-1)
        k = k.reshape(bsz, seqlen, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = v.reshape(bsz, seqlen, self.num_kv_heads, self.head_dim).transpose(1, 2)
        q = F.rms_norm(q, (q.size(-1),))
        k = F.rms_norm(k, (k.size(-1),))
        cos, sin = self.rotary(seqlen, x.device, q.dtype)
        q = apply_rotary_emb(q, cos, sin)
        k = apply_rotary_emb(k, cos, sin)
        q = q * self.q_gain.to(dtype=q.dtype)[None, :, None, None]
        y = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=None,
            is_causal=True,
            enable_gqa=(self.num_kv_heads != self.num_heads),
        )
        if self.use_xsa:
            y = self._xsa_efficient(y, v)
        y = y.transpose(1, 2).contiguous().reshape(bsz, seqlen, dim)
        return self.out_proj(y)


class HydraGlobalBlock(nn.Module):
    """Global-path block: norm → attn (+ optional parallel-residual MLP)."""

    def __init__(
        self,
        dim: int,
        num_heads: int,
        num_kv_heads: int,
        mlp_mult: float,
        rope_base: float,
        qk_gain_init: float,
        group_size: int = 128,
        latent_dim: int = 128,
        parallel_residual: bool = True,
    ):
        super().__init__()
        self.attn_norm = RMSNorm()
        self.attn = HydraGlobalSelfAttention(
            dim, num_heads, num_kv_heads, rope_base, qk_gain_init,
            group_size=group_size, latent_dim=latent_dim,
        )
        self.mlp_norm = RMSNorm()
        self.mlp = HydraMLP(dim, mlp_mult, group_size=group_size)
        self.attn_scale = nn.Parameter(torch.ones(dim, dtype=torch.float32))
        self.mlp_scale = nn.Parameter(torch.ones(dim, dtype=torch.float32))
        self.parallel_residual = parallel_residual

    def forward(self, x: Tensor) -> Tensor:
        x_in = x
        attn_out = self.attn(self.attn_norm(x_in))
        if self.parallel_residual:
            mlp_out = self.mlp(self.mlp_norm(x_in))
            return (
                x_in
                + self.attn_scale.to(dtype=x_in.dtype)[None, None, :] * attn_out
                + self.mlp_scale.to(dtype=x_in.dtype)[None, None, :] * mlp_out
            )
        x = x_in + self.attn_scale.to(dtype=x_in.dtype)[None, None, :] * attn_out
        return x + self.mlp_scale.to(dtype=x.dtype)[None, None, :] * self.mlp(self.mlp_norm(x))


# =============================================================================
# Local path
# =============================================================================

class HydraLocalSelfAttention(nn.Module):
    """Sliding-window causal attention with chunked masking.

    The sequence is partitioned into `T // window` chunks. Each chunk attends
    to its own positions and to the previous chunk's positions, with a custom
    chunk-level mask that preserves causality across the chunk boundary
    (token i in chunk c can see all of chunk c-1 plus chunk c positions <= i).

    A `CausalInterferometer` pre-mixes lag information into the input before
    QKV projection.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int,
        window: int,
        rope_base: float,
        qk_gain_init: float,
        interferometer_gate_init: float = -3.0,
        group_size: int = 128,
    ):
        super().__init__()
        if dim % num_heads != 0:
            raise ValueError("dim must be divisible by num_heads")
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        if self.head_dim % 2 != 0:
            raise ValueError("head_dim must be even for RoPE")
        self.window = window
        self.interferometer = CausalInterferometer(dim, gate_init=interferometer_gate_init, group_size=group_size)
        self.qkv = QATLinear(dim, 3 * dim, bias=False, group_size=group_size)
        self.out_proj = QATLinear(dim, dim, bias=False, group_size=group_size)
        self.q_gain = nn.Parameter(torch.full((num_heads,), qk_gain_init, dtype=torch.float32))
        self.rotary = Rotary(self.head_dim, base=rope_base)
        self.register_buffer("chunk_attn_mask_buf", torch.empty(0, 0, 0), persistent=False)
        self._mask_num_chunks = 0

    def _chunk_attn_mask(self, num_chunks: int, device: torch.device, dtype: torch.dtype) -> Tensor:
        if (
            self.chunk_attn_mask_buf.numel() == 0
            or self._mask_num_chunks != num_chunks
            or self.chunk_attn_mask_buf.device != device
        ):
            pos = torch.arange(self.window, device=device)
            prev_valid = pos.unsqueeze(0) > pos.unsqueeze(1)
            curr_valid = pos.unsqueeze(0) <= pos.unsqueeze(1)
            generic_valid = torch.cat([prev_valid, curr_valid], dim=1)
            first_valid = torch.cat([torch.zeros_like(prev_valid), curr_valid], dim=1)
            valid = generic_valid.unsqueeze(0).expand(num_chunks, -1, -1).clone()
            valid[0] = first_valid
            mask = torch.full((num_chunks, self.window, 2 * self.window), float("-inf"), device=device, dtype=torch.float32)
            mask.masked_fill_(valid, 0.0)
            self.chunk_attn_mask_buf = mask
            self._mask_num_chunks = num_chunks
        return self.chunk_attn_mask_buf.to(dtype=dtype)

    def forward(self, x: Tensor, route_stats: dict[str, list[Tensor]] | None = None) -> Tensor:
        bsz, seqlen, dim = x.shape
        if seqlen % self.window != 0:
            raise ValueError(f"sequence length {seqlen} must be divisible by local window {self.window}")
        x = self.interferometer(x, route_stats=route_stats)
        qkv = self.qkv(x)
        q, k, v = qkv.chunk(3, dim=-1)
        q = q.reshape(bsz, seqlen, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.reshape(bsz, seqlen, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.reshape(bsz, seqlen, self.num_heads, self.head_dim).transpose(1, 2)
        q = F.rms_norm(q, (q.size(-1),))
        k = F.rms_norm(k, (k.size(-1),))
        cos, sin = self.rotary(seqlen, x.device, q.dtype)
        q = apply_rotary_emb(q, cos, sin)
        k = apply_rotary_emb(k, cos, sin)
        q = q * self.q_gain.to(dtype=q.dtype)[None, :, None, None]
        num_chunks = seqlen // self.window
        q_chunks = q.reshape(bsz, self.num_heads, num_chunks, self.window, self.head_dim).permute(0, 2, 1, 3, 4)
        k_chunks = k.reshape(bsz, self.num_heads, num_chunks, self.window, self.head_dim).permute(0, 2, 1, 3, 4)
        v_chunks = v.reshape(bsz, self.num_heads, num_chunks, self.window, self.head_dim).permute(0, 2, 1, 3, 4)
        zero_k = torch.zeros_like(k_chunks[:, :1])
        zero_v = torch.zeros_like(v_chunks[:, :1])
        prev_k = torch.cat([zero_k, k_chunks[:, :-1]], dim=1)
        prev_v = torch.cat([zero_v, v_chunks[:, :-1]], dim=1)
        kv_chunks = torch.cat([prev_k, k_chunks], dim=3)
        vv_chunks = torch.cat([prev_v, v_chunks], dim=3)
        q_flat = q_chunks.reshape(bsz * num_chunks, self.num_heads, self.window, self.head_dim)
        k_flat = kv_chunks.reshape(bsz * num_chunks, self.num_heads, 2 * self.window, self.head_dim)
        v_flat = vv_chunks.reshape(bsz * num_chunks, self.num_heads, 2 * self.window, self.head_dim)
        chunk_mask = self._chunk_attn_mask(num_chunks, x.device, q.dtype)
        attn_mask = chunk_mask.unsqueeze(0).expand(bsz, -1, -1, -1).reshape(
            bsz * num_chunks, 1, self.window, 2 * self.window
        )
        y = F.scaled_dot_product_attention(q_flat, k_flat, v_flat, attn_mask=attn_mask, is_causal=False)
        y = y.reshape(bsz, num_chunks, self.num_heads, self.window, self.head_dim)
        y = y.permute(0, 1, 3, 2, 4).contiguous().reshape(bsz, seqlen, dim)
        return self.out_proj(y)


class HydraLocalBlock(nn.Module):
    """Local-path block: norm → attn (with interferometer preprocess) → optional MLP.

    Per-channel learnable `attn_scale` and `mlp_scale` modulate the residual
    contributions. `use_mlp=False` skips the MLP entirely (used for cheap
    early/late layers in the local stack).
    """

    def __init__(
        self,
        dim: int,
        num_heads: int,
        window: int,
        mlp_mult: float,
        rope_base: float,
        qk_gain_init: float,
        use_mlp: bool,
        interferometer_gate_init: float = -3.0,
        group_size: int = 128,
    ):
        super().__init__()
        self.attn_norm = RMSNorm()
        self.attn = HydraLocalSelfAttention(
            dim, num_heads, window, rope_base, qk_gain_init,
            interferometer_gate_init=interferometer_gate_init,
            group_size=group_size,
        )
        self.use_mlp = use_mlp
        self.mlp_norm = RMSNorm() if use_mlp else None
        self.mlp = HydraMLP(dim, mlp_mult, group_size=group_size) if use_mlp else None
        self.attn_scale = nn.Parameter(torch.ones(dim, dtype=torch.float32))
        self.mlp_scale = nn.Parameter(torch.ones(dim, dtype=torch.float32)) if use_mlp else None

    def forward(self, x: Tensor, route_stats: dict[str, list[Tensor]] | None = None) -> Tensor:
        x = x + self.attn_scale.to(dtype=x.dtype)[None, None, :] * self.attn(
            self.attn_norm(x), route_stats=route_stats
        )
        if self.use_mlp and self.mlp is not None and self.mlp_norm is not None and self.mlp_scale is not None:
            x = x + self.mlp_scale.to(dtype=x.dtype)[None, None, :] * self.mlp(self.mlp_norm(x))
        return x


# =============================================================================
# SAGE Bus (Surprise-Anchored Global Echo)
# =============================================================================

class SageBus(nn.Module):
    """Surprise-Anchored Global Echo: deterministic global-to-local context injection.

    Per-token gates come from current-token bigram entropy and structural-anchor
    membership (no learned routing), keeping the routing signal interpretable
    and gradient-free. The learned part is the projection that maps
    causally-shifted chunk summaries back into the local stream.

    Forward outline:
      1. Compute per-token route logits = ent_scale * (entropy - threshold)
                                         + anchor_scale * anchor + route_bias.
      2. Sigmoid → token gate; weighted-mean within each chunk → summary.
      3. Causally shift summaries one chunk right; apply learned summary predictor.
      4. Cumulative prefix-mean → context tensor (running summary up to current
         chunk); project once per chunk (`sage_value_proj` then `sage_out_proj`)
         and broadcast back to per-token granularity.
      5. Within-chunk causal cummax over token gates ensures position i depends
         only on route signals up to i (never on later tokens in the same chunk).
      6. Add `chunk_gate * bus_gate * context` to the residual stream.

    Buffers and route stats: when `route_stats` is provided, the module logs
    per-step gate / norm scalars for downstream telemetry (gate distributions,
    anchor rate, entropy mean, before/after norms).
    """

    def __init__(
        self,
        dim: int,
        chunk: int,
        ent_threshold: float,
        ent_scale: float,
        anchor_scale: float,
        route_bias: float,
        bus_gate_init: float,
        resid_scale: float,
        group_size: int = 128,
    ):
        super().__init__()
        if chunk <= 0:
            raise ValueError(f"SAGE chunk must be positive, got {chunk}")
        self.chunk = int(chunk)
        self.ent_threshold = float(ent_threshold)
        self.ent_scale = float(ent_scale)
        self.anchor_scale = float(anchor_scale)
        self.route_bias = float(route_bias)
        self.resid_scale = float(resid_scale)
        self.summary_norm = RMSNorm()
        self.context_norm = RMSNorm()
        self.sage_summary_pred = QATLinear(dim, dim, bias=False, group_size=group_size)
        self.sage_summary_pred._zero_init = True
        self.sage_value_proj = QATLinear(dim, dim, bias=False, group_size=group_size)
        self.sage_out_proj = QATLinear(dim, dim, bias=False, group_size=group_size)
        self.sage_bus_gate = nn.Parameter(torch.full((dim,), bus_gate_init, dtype=torch.float32))

    def forward(
        self,
        x: Tensor,
        token_entropy: Tensor,
        anchor: Tensor,
        route_stats: dict[str, list[Tensor]] | None = None,
    ) -> Tensor:
        bsz, seqlen, dim = x.shape
        chunk = self.chunk
        if seqlen % chunk != 0:
            raise ValueError(f"sequence length {seqlen} must be divisible by SAGE chunk={chunk}")
        n_chunks = seqlen // chunk
        local_before = x.float().norm(dim=-1).mean()

        route_logit = (
            self.ent_scale * (token_entropy.float() - self.ent_threshold)
            + self.anchor_scale * anchor.float()
            + self.route_bias
        )
        token_gate = torch.sigmoid(route_logit.clamp(-10.0, 10.0)).to(dtype=x.dtype)
        x_chunks = x.reshape(bsz, n_chunks, chunk, dim)
        gate_chunks = token_gate.reshape(bsz, n_chunks, chunk)
        weighted = (x_chunks * gate_chunks[..., None]).sum(dim=2)
        denom = gate_chunks.sum(dim=2, keepdim=True).clamp_min(1.0)
        summary = weighted / denom
        shifted = torch.cat([torch.zeros_like(summary[:, :1]), summary[:, :-1]], dim=1)
        shifted = shifted + self.sage_summary_pred(self.summary_norm(shifted))

        counts = torch.arange(n_chunks, device=x.device, dtype=torch.float32).clamp_min(1.0).view(1, n_chunks, 1)
        prefix = (shifted.float().cumsum(dim=1) / counts).to(dtype=x.dtype)
        context = self.sage_value_proj(self.summary_norm(prefix))
        context = self.sage_out_proj(self.context_norm(context))
        context = context.repeat_interleave(chunk, dim=1)

        chunk_gate = torch.cummax(gate_chunks, dim=2).values.reshape(bsz, seqlen).unsqueeze(-1).to(dtype=x.dtype)
        bus_gate = self.resid_scale * torch.sigmoid(self.sage_bus_gate.float().clamp(-6.0, 6.0))
        out = x + chunk_gate * bus_gate.to(dtype=x.dtype)[None, None, :] * context

        if route_stats is not None:
            token_gate_f = token_gate.detach().float()
            chunk_gate_f = chunk_gate.detach().float()
            route_stats.setdefault("sage_bus_gate", []).append(torch.sigmoid(self.sage_bus_gate.detach().float()).mean())
            route_stats.setdefault("sage_token_gate_mean", []).append(token_gate_f.mean())
            route_stats.setdefault("sage_token_gate_p90", []).append(torch.quantile(token_gate_f.reshape(-1), 0.90))
            route_stats.setdefault("sage_chunk_gate_mean", []).append(chunk_gate_f.mean())
            route_stats.setdefault("sage_anchor_rate", []).append(anchor.detach().float().mean())
            route_stats.setdefault("sage_entropy_mean", []).append(token_entropy.detach().float().mean())
            route_stats.setdefault("sage_bus_norm", []).append(context.detach().float().norm(dim=-1).mean())
            route_stats.setdefault("local_norm_before_sage", []).append(local_before)
            route_stats.setdefault("local_norm_after_sage", []).append(out.detach().float().norm(dim=-1).mean())
        return out
