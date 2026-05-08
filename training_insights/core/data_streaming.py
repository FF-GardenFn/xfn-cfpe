"""
Token-shard streaming and distributed batching.

`load_data_shard` reads a binary token shard with a 256-int32 magic header
followed by uint16 token IDs. `TokenStream` cycles through a list of shards,
serving contiguous token slabs. `DistributedTokenLoader` slices each global
batch into per-rank windows with a one-token overlap for next-token prediction.

Shard format (256-int32 header + uint16 tokens):
    header[0] = 20240520    (magic)
    header[1] = 1           (version)
    header[2] = num_tokens  (count)
    header[3:256] reserved
    tokens... (uint16, little-endian)

Extracted from `train_gpt.py` (Farhat).
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import torch
from torch import Tensor


def load_data_shard(file: Path) -> Tensor:
    """Read a uint16 token shard with a 256-int32 magic header.

    Validates the magic (20240520) and version (1) and the file size against
    the announced num_tokens. Returns a 1-D uint16 tensor of token IDs.
    """
    header_bytes = 256 * np.dtype("<i4").itemsize
    token_bytes = np.dtype("<u2").itemsize
    header = np.fromfile(file, dtype="<i4", count=256)
    if header.size != 256 or int(header[0]) != 20240520 or int(header[1]) != 1:
        raise ValueError(f"Unexpected shard header for {file}")
    num_tokens = int(header[2])
    expected_size = header_bytes + num_tokens * token_bytes
    if file.stat().st_size != expected_size:
        raise ValueError(f"Shard size mismatch for {file}: expected {expected_size} bytes")
    tokens_np = np.fromfile(file, dtype="<u2", count=num_tokens, offset=header_bytes)
    if tokens_np.size != num_tokens:
        raise ValueError(f"Short read for {file}")
    return torch.from_numpy(tokens_np.astype(np.uint16, copy=False))


class TokenStream:
    """Cycles through a list of token shards, serving contiguous token slabs.

    Construction order: explicit `ordered_files` if given, otherwise glob expansion
    of `pattern` in lexical order. Wraps to the first shard at the end (cyclic).
    """

    def __init__(self, pattern: str, ordered_files: list[Path] | None = None):
        if ordered_files is not None:
            self.files = list(ordered_files)
        else:
            self.files = [Path(p) for p in sorted(glob.glob(pattern))]
        if not self.files:
            raise FileNotFoundError(f"No files found for pattern: {pattern}")
        self.file_idx = 0
        self.tokens = load_data_shard(self.files[0])
        self.pos = 0

    def _advance_file(self) -> None:
        self.file_idx = (self.file_idx + 1) % len(self.files)
        self.tokens = load_data_shard(self.files[self.file_idx])
        self.pos = 0

    def take(self, n: int) -> Tensor:
        """Return the next `n` tokens as a 1-D tensor, advancing the cursor."""
        chunks: list[Tensor] = []
        remaining = n
        while remaining > 0:
            avail = self.tokens.numel() - self.pos
            if avail <= 0:
                self._advance_file()
                continue
            k = min(remaining, avail)
            chunks.append(self.tokens[self.pos : self.pos + k])
            self.pos += k
            remaining -= k
        return chunks[0] if len(chunks) == 1 else torch.cat(chunks)


class DistributedTokenLoader:
    """Slice each global batch into per-rank windows for next-token prediction.

    Each rank receives a contiguous slice of the global batch with a one-token
    overlap so that `(x, y)` pairs can be formed by the standard
    `x = local[:-1]; y = local[1:]` shift.

    The `next_batch` contract: caller specifies the global batch size in tokens,
    the sequence length for reshaping, and the gradient-accumulation factor.
    Per-rank tokens = `global_tokens / (world_size * grad_accum_steps)`.
    """

    def __init__(
        self,
        pattern: str,
        rank: int,
        world_size: int,
        device: torch.device,
        ordered_files: list[Path] | None = None,
    ):
        self.rank = rank
        self.world_size = world_size
        self.device = device
        self.stream = TokenStream(pattern, ordered_files=ordered_files)

    def next_batch(
        self,
        global_tokens: int,
        seq_len: int,
        grad_accum_steps: int,
    ) -> tuple[Tensor, Tensor]:
        """Pull the next batch and split into `(x, y)` next-token pairs."""
        local_tokens = global_tokens // (self.world_size * grad_accum_steps)
        per_rank_span = local_tokens + 1
        chunk = self.stream.take(per_rank_span * self.world_size)
        start = self.rank * per_rank_span
        local = chunk[start : start + per_rank_span].to(dtype=torch.int64)
        x = local[:-1].reshape(-1, seq_len)
        y = local[1:].reshape(-1, seq_len)
        return x.to(self.device, non_blocking=True), y.to(self.device, non_blocking=True)


def compute_shard_mean_entropy(shard_path: Path, bigram_entropy: Tensor) -> float:
    """Mean bigram entropy across the shard's tokens.

    CPU-only; used for curriculum-style sort ordering. Caller supplies the
    `bigram_entropy` lookup of size (vocab_size,); the function returns a
    Python float for the shard's mean.
    """
    tokens = load_data_shard(shard_path)
    return float(bigram_entropy[tokens.long()].mean().item())
