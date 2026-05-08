"""
INT4 quantization and 4-bit QAT (Quantization-Aware Training) utilities.

Provides:
  - `fake_quantize_4bit` — STE-based 4-bit fake quantization for training-time QAT
  - `QATLinear` — `nn.Linear` drop-in with per-call 4-bit fake-quant on the weight,
                  noise scale driven by an external buffer
  - `quantize_weight_int4` / `pack_int4` / `unpack_int4` — int4 packing for export
  - `quantize_state_dict_int4` / `dequantize_state_dict_int4` — full state-dict
    roundtrip combining int4 weights and int8 control-tensor quantization
  - `restore_low_dim_params_to_fp32` / `restore_runtime_linear_modules_to_fp32` —
    export-side surgery that ensures sensitive scalars stay fp32 during inference

The export format separates QAT-eligible matrix weights (int4, group-quantized) from
control tensors (int8 or fp16 passthrough depending on sensitivity). Sensitive control
tensors with high behavioral leverage but few bytes (gates, gains, scales) stay in
fp16 to avoid the post-roundtrip BPB hit observed when int8-quantizing them.

Extracted from `train_gpt.py` (Farhat).
"""

from __future__ import annotations

import os

import torch
from torch import Tensor, nn
import torch.nn.functional as F


# Tensors matched by these substring patterns are treated as control tensors and
# kept in fp32 at runtime even after a post-roundtrip restore.
CONTROL_TENSOR_NAME_PATTERNS: tuple[str, ...] = tuple(
    pattern
    for pattern in os.environ.get(
        "CONTROL_TENSOR_NAME_PATTERNS",
        "attn_scale,attn_scales,mlp_scale,mlp_scales,q_gain,macro_gate,continue_probe,depth_gate,smear,sage_bus_gate",
    ).split(",")
    if pattern
)


# Weights matched by these suffixes are eligible for int4 QAT during training and
# int4 packed export. Other weights pass through (kept in fp16 / int8).
QAT_WEIGHT_SUFFIXES: tuple[str, ...] = (
    "qkv.weight", "q_proj.weight", "kv_down.weight", "kv_up.weight", "out_proj.weight",
    "gate_up.weight", "down.weight",
    "proj_local.weight", "proj_global.weight", "upsample_proj.weight", "inject_proj.weight",
    "sage_global_in.weight",
    "local_head.weight", "global_head.weight",
    "pack_down_in.weight", "pack_down_out.weight",
    "lag_mix_down.weight", "lag_mix_up.weight",
    "tok_emb.weight", "lm_head.weight",
    "q_bank", "kv_down_bank", "kv_up_bank", "out_bank", "mlp_gateup_bank", "mlp_down_bank",
    "macro_q.weight", "macro_k.weight", "macro_v.weight", "macro_pred.weight",
    "macro_q2.weight", "macro_k2.weight", "macro_v2.weight",
    "sage_summary_pred.weight", "sage_value_proj.weight", "sage_out_proj.weight",
    "copy_q_proj.weight", "copy_k_proj.weight",
    "pmi_proj_local.weight", "pmi_decode.weight",
)


# Sensitive control tensors kept in fp16 during export (NOT int8). These have high
# behavioral leverage per byte; int8 quantization caused measurable post-roundtrip
# BPB regression in the original training runs.
FP16_KEEP_PATTERNS: tuple[str, ...] = (
    "macro_gate", "q_gain", "attn_scale", "mlp_scale",
    "smear.gate", "depth_gate", "sage_bus_gate",
    "bigram_scales", "phase_clock", "trigram_", "cross_diff",
    "mix_proj", "macro_film_scale", "global_continue_probe", "copy_gate",
)


def _is_qat_weight_name(name: str) -> bool:
    """True if a parameter name is eligible for int4 QAT export."""
    if any(name.endswith(suffix) for suffix in QAT_WEIGHT_SUFFIXES):
        return True
    return name.startswith("mtp_transforms.") and name.endswith(".weight")


# =============================================================================
# Training-time QAT
# =============================================================================

def fake_quantize_4bit(weight: Tensor, group_size: int = 128, noise_scale: float | Tensor = 1.0) -> Tensor:
    """Fake-quantize a weight tensor to 4-bit with per-group absmax scales (STE).

    `noise_scale` (scalar or 0-D tensor) ramps the quantization-error injection
    from 0 (pass-through) to 1 (full QAT). Backward pass is straight-through:
    the rounded values are detached, only the residual flows.

    Returns the weight as floats with quantization noise added (to match
    inference-time numerics). Shape is preserved.
    """
    if torch.is_tensor(noise_scale):
        noise_scale_tensor = noise_scale.to(device=weight.device, dtype=weight.dtype)
    else:
        noise_scale_value = float(noise_scale)
        if noise_scale_value <= 0.0:
            return weight
        noise_scale_tensor = weight.new_tensor(noise_scale_value)
    orig_shape = weight.shape
    w = weight.reshape(-1, group_size)
    scale = w.abs().amax(dim=-1, keepdim=True).clamp(min=1e-10) / 7.0
    w_q = (w / scale).round().clamp(-8, 7)
    w_dq = (w_q * scale).reshape(orig_shape)
    quant_error = (w_dq - weight).detach()
    return weight + noise_scale_tensor * quant_error


class QATLinear(nn.Linear):
    """`nn.Linear` with 4-bit fake quantization applied to the weight.

    The QAT noise scale is driven by `qat_noise_scale_buf` (a non-persistent
    buffer the training loop updates each step). When the buffer is 0, this
    behaves identically to a plain `nn.Linear`.
    """

    def __init__(self, in_features: int, out_features: int, bias: bool = False, group_size: int = 128):
        super().__init__(in_features, out_features, bias=bias)
        self.group_size = group_size
        self.register_buffer(
            "qat_noise_scale_buf",
            torch.tensor(1.0, dtype=torch.float32),
            persistent=False,
        )

    def forward(self, x: Tensor) -> Tensor:
        w = fake_quantize_4bit(self.weight, self.group_size, self.qat_noise_scale_buf)
        bias = self.bias.to(x.dtype) if self.bias is not None else None
        return F.linear(x, w.to(x.dtype), bias)


# =============================================================================
# Export-time INT4 packing / unpacking
# =============================================================================

def quantize_weight_int4(weight: Tensor, group_size: int = 128) -> tuple[Tensor, Tensor]:
    """Plain absmax int4 quantization with per-group fp16 scales.

    Returns `(int8 q, fp16 scale)` where q lives in [-8, 7]. At int4 (16 levels),
    every level matters and outlier clipping (GPTQ-lite-style) destroys outlier
    weights. Plain absmax is the calibrated choice for this regime.
    """
    w = weight.float().reshape(-1, group_size)
    scale = w.abs().amax(dim=-1, keepdim=True).clamp(min=1e-10) / 7.0
    q = (w / scale).round().clamp(-8, 7).to(torch.int8)
    return q.reshape(weight.shape), scale.squeeze(-1).to(torch.float16)


def pack_int4(q: Tensor) -> Tensor:
    """Pack int4 values [-8..7] into uint8 byte pairs. Halves storage."""
    q_uint = (q.to(torch.int16) + 8).to(torch.uint8)  # shift to [0..15]
    assert q_uint.shape[-1] % 2 == 0, f"cols must be even for int4 packing, got {q_uint.shape[-1]}"
    lo = q_uint[..., 0::2]
    hi = q_uint[..., 1::2]
    return (hi << 4 | lo).to(torch.uint8)


def unpack_int4(packed: Tensor, orig_cols: int) -> Tensor:
    """Unpack a uint8 packed int4 tensor back to int8 values in [-8..7]."""
    lo = (packed & 0x0F).to(torch.int8) - 8
    hi = (packed >> 4).to(torch.int8) - 8
    return torch.stack([lo, hi], dim=-1).reshape(*packed.shape[:-1], orig_cols)


# =============================================================================
# Per-tensor int8 quantization for non-sensitive control tensors
# =============================================================================

def _quantize_passthrough_int8(t: Tensor) -> tuple[Tensor, Tensor]:
    """Per-tensor int8 quantization. Saves ~50% vs fp16 for non-sensitive tensors."""
    t32 = t.float()
    amax = t32.abs().max().clamp(min=1e-12)
    scale = (amax / 127.0).to(torch.float16)
    q = torch.clamp(torch.round(t32 / scale.float()), -127, 127).to(torch.int8)
    return q, scale


def _dequantize_passthrough_int8(q: Tensor, scale: Tensor) -> Tensor:
    return (q.float() * scale.float()).contiguous()


# =============================================================================
# Whole state-dict roundtrip
# =============================================================================

def quantize_state_dict_int4(state_dict: dict[str, Tensor], group_size: int = 128):
    """Quantize a full model state-dict for export.

    QAT-eligible weights → packed int4 with fp16 scales.
    Sensitive control tensors → fp16 passthrough.
    Other floating tensors → int8 passthrough with fp16 scale.

    Returns `(obj, stats)` where `obj` is a dict serializable via `torch.save`.
    """
    int4_packed: dict[str, Tensor] = {}
    int4_scales: dict[str, Tensor] = {}
    int4_shapes: dict[str, list[int]] = {}
    int4_orig_cols: dict[str, int] = {}
    passthrough: dict[str, Tensor] = {}
    passthrough_orig_dtypes: dict[str, str] = {}
    stats = {"param_count": 0, "int4_bytes": 0, "passthrough_bytes": 0}

    for name, tensor in state_dict.items():
        t = tensor.detach().cpu().contiguous()
        stats["param_count"] += int(t.numel())

        if _is_qat_weight_name(name) and t.numel() % group_size == 0:
            q, scale = quantize_weight_int4(t, group_size)
            int4_orig_cols[name] = q.shape[-1]
            packed = pack_int4(q)
            int4_packed[name] = packed
            int4_scales[name] = scale
            int4_shapes[name] = list(t.shape)
            stats["int4_bytes"] += packed.numel() + scale.numel() * 2
        else:
            passthrough_orig_dtypes[name] = str(t.dtype).removeprefix("torch.")
            is_sensitive = any(pat in name for pat in FP16_KEEP_PATTERNS)
            if t.is_floating_point() and t.numel() > 1 and not is_sensitive:
                q, s = _quantize_passthrough_int8(t)
                passthrough[name + ".q"] = q
                passthrough[name + ".scale"] = s
                stats["passthrough_bytes"] += q.numel() + 2  # int8 + fp16 scale
            else:
                if t.is_floating_point():
                    t = t.to(torch.float16)
                passthrough[name] = t
                stats["passthrough_bytes"] += int(t.numel()) * int(t.element_size())

    obj: dict[str, object] = {
        "__quant_format__": "int4_transgolf_v2",
        "int4_packed": int4_packed,
        "int4_scales": int4_scales,
        "int4_shapes": int4_shapes,
        "int4_orig_cols": int4_orig_cols,
        "int4_group_size": group_size,
        "passthrough": passthrough,
        "passthrough_orig_dtypes": passthrough_orig_dtypes,
    }
    return obj, stats


def dequantize_state_dict_int4(obj: dict[str, object]) -> dict[str, Tensor]:
    """Dequantize a state-dict produced by `quantize_state_dict_int4`."""
    group_size = obj["int4_group_size"]
    int4_orig_cols = obj.get("int4_orig_cols", {})
    out: dict[str, Tensor] = {}

    for name, packed in obj["int4_packed"].items():
        shape = obj["int4_shapes"][name]
        scale = obj["int4_scales"][name]
        orig_cols = int4_orig_cols.get(name, shape[-1])
        q = unpack_int4(packed, orig_cols).reshape(-1, group_size)
        scale_f = scale.float().unsqueeze(-1)
        w = (q.float() * scale_f).reshape(shape)
        out[name] = w.to(torch.bfloat16)

    passthrough_orig_dtypes = obj.get("passthrough_orig_dtypes", {})
    passthrough = obj["passthrough"]
    for name, orig_dtype_str in passthrough_orig_dtypes.items():
        orig_dtype = getattr(torch, orig_dtype_str) if isinstance(orig_dtype_str, str) else torch.float32
        if name + ".q" in passthrough:
            out[name] = _dequantize_passthrough_int8(
                passthrough[name + ".q"], passthrough[name + ".scale"]
            ).to(orig_dtype)
        elif name in passthrough:
            out_t = passthrough[name].detach().cpu().contiguous()
            if out_t.is_floating_point() and out_t.dtype != orig_dtype:
                out_t = out_t.to(orig_dtype)
            out[name] = out_t

    return out


# =============================================================================
# Post-roundtrip surgery: restore precision where it matters
# =============================================================================

def restore_low_dim_params_to_fp32(module: nn.Module) -> None:
    """Cast 0/1-D parameters and CONTROL_TENSOR_NAME_PATTERNS matches to fp32.

    Run after dequantization to guarantee numerical headroom for low-leverage-
    per-byte-but-high-leverage-overall control parameters.
    """
    with torch.no_grad():
        for name, param in module.named_parameters():
            if (
                param.ndim < 2
                or any(pattern in name for pattern in CONTROL_TENSOR_NAME_PATTERNS)
            ) and param.dtype != torch.float32:
                param.data = param.data.float()


def restore_runtime_linear_modules_to_fp32(module: nn.Module) -> None:
    """Cast all `nn.Linear` (incl. `QATLinear`) submodules to fp32 for inference."""
    with torch.no_grad():
        for _name, child in module.named_modules():
            if isinstance(child, QATLinear):
                child.float()
                continue
            if isinstance(child, nn.Linear):
                child.float()
