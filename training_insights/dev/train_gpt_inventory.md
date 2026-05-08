# `train_gpt.py` Inventory — What Supersedes What

Section-by-section map of the 4587-line monolith against the existing modular codebase in `training_insights/`. Generated 2026-05-06 to support iterative extraction.

The **Muon optimizer** has already been extracted (2026-05-06): the variant-aware system from `train_gpt.py` lines 200–727 is now the engine of `core/optim.py`. The `MuonAdamW`/`DistMuonAdamW` interface is preserved so `quick_train.py`, `scripts/base_train.py` etc. don't break. AOL preconditioner, two orthogonalizer backends (NS polynomial + stabilized Gram-NS with restart), five variants (`standard4/5`, `polar_express5`, `turbo4_aol`, `custom`), fp32 buffers, and `clip_grad_norm_no_sync_` are all available.

A **HYDRA-inspired dual-block** has also been added to `core/gpt.py` (2026-05-06) as opt-in via `GPTConfig.block_kind = "dual"`. The `DualBlock` augments each layer with a span-pooled causal attention path alongside the existing per-token attention — inspired by the local/global split in `train_gpt.py` but adapted to a single-stream trunk rather than a separate stack. The span path is zero-initialized (`span_scale = 0`, `span_attn.c_proj.weight = 0`), so a dual-block GPT starts behaviorally identical to single-block and only diverges as `span_scale` trains. Span attention is automatically bypassed during kv-cache inference (it has no single-token semantics).

What follows are the remaining sections, ordered by extraction priority.

---

## Core Architecture

| Section | Lines | Existing File(s) Superseded | Complexity | Distinctive Improvement |
|---|---:|---|---|---|
| **Hyperparameters** | 34–198 | (config scattered across files) | Moderate | Centralized, env-driven (165+ knobs); covers HYDRA, QAT, Muon, bigram/trigram curriculum |
| **Muon Optimizer** | 457–727 | `core/optim.py` (DONE 2026-05-06) | Major | Variant-aware, AOL preconditioner, stabilized Gram-NS w/ restart, fp32 buffers |
| **Muon Helpers** | 222–455 | `core/optim.py` (DONE) | Major | parse_coeffs, build_config, apply_aol, two orthogonalizer backends, dispatcher |
| **RMSNorm** | 1429–1435 | `core/gpt.py` (`norm` function) | Trivial | Module wrapper of the same operation |
| **Rotary** | 1733–1754 | `core/gpt.py` (rotary inline) | Trivial | Caches cos/sin |
| **QAT/INT4 Quantization** | 981–1107, 1442–1469 | `core/fp8.py` (INT8 focus) | Moderate | 4-bit fake-quant w/ STE, per-group scaling, ramp-in schedule via model buffers |

## HYDRA Architecture (mostly new — not present in existing codebase)

| Section | Lines | Existing | Complexity | Distinctive Improvement |
|---|---:|---|---|---|
| **CausalInterferometer** | 1858–1889 | (entirely new) | New module | Phase mixer for past-lag attention; pairwise attention with 4-dim aggregation |
| **HydraMLP** | 1845–1856 | `core/gpt.py` MLP | Moderate | Gate-up projection + SiLU; uses QAT |
| **HydraLocalSelfAttention** | 1960–2048 | `core/gpt.py` attention | Major | Local sliding-window causal attn, chunked masking, RoPE, QK-norm, GQA-like, interferometer preprocessing |
| **HydraLocalBlock** | 2051–2087 | `core/gpt.py` TransformerBlock | Moderate | Local path: norm→attn+interferometer→norm→MLP w/ learnable residual scales; MLP optional |
| **HydraGlobalSelfAttention** | 1892–1957 | (new) | New module | Pooled global attn w/ latent bottleneck, GQA, XSA-efficient orthogonalization, RoPE |
| **HydraGlobalBlock** | 2184–2225 | (new) | New module | Global path: norm→attn+norm→MLP w/ parallel residual option |
| **SageBus** | 2090–2181 | (new) | New module | Surprise-Anchored Global Echo: bigram-entropy + struct-anchor deterministic routing; cumulative prefix fusion |
| **GPT (model)** | 2232–3330 | `core/gpt.py` GPT | Major | Bifurcated recurrent: shared embed → local (8 blocks) + optional global (1 block, recurrent); SAGE local routing; macro-interval sidechannel; bigram/trigram priors; spine PLATO-SPINE; copy mechanism; MTP future-embed loss |
| **SmearGate** | 1832–? | (new) | New module | Smearing gate for attention/MLP output |

## Data Loading & Preprocessing

| Section | Lines | Existing | Complexity | Distinctive Improvement |
|---|---:|---|---|---|
| **TokenStream** | 1374–1403 | `core/dataloader.py` (basic) | Trivial | Per-file token stream w/ cycling |
| **DistributedTokenLoader** | 1406–1422 | `core/dataloader.py` | Moderate | Distributed token batching; per-rank slicing w/ overlap |
| **load_data_shard** | 1352–1365 | `core/dataset.py` | Trivial | uint16 binary token files w/ 256-int32 header validation |
| **compute_shard_mean_entropy** | 1368–1371 | (new) | New | Bigram entropy per shard for curriculum sorting |
| **build_sentencepiece_luts** | ~3522 | `core/tokenizer.py` | Moderate | Byte/boundary token LUTs from SentencePiece for BPB |
| **build_struct_anchor_lut** | ~3525 | (new) | New | Structural anchor binary vector for SAGE routing |
| **load_validation_tokens** | ~3521 | `core/loss_eval.py` | Moderate | Concatenated validation token stream from glob pattern |

## Bigram & Trigram Priors (entirely new)

| Section | Lines | Existing | Complexity | Notes |
|---|---:|---|---|---|
| **load_bigram_prior** | 1188–1255 | (new) | New | Full or low-rank factorized bigram log-prior; centering; entropy; int8 quantization for export |
| **prepare_bigram_for_export** | 1257–1267 | (new) | New | Quantize to int8 per-row pre-export |
| **clear_bigram_runtime** | 1270–1279 | (new) | New | Zero runtime buffers for deterministic export |
| **restore_bigram_from_int8** | 1282–1302 | (new) | New | Dequantize int8 bigram post-export for inference |
| **load_trigram_prior** | 1305–1340 | (new) | New | CP-decomposed trigram residual (u, v, w tensors); rank-limited slicing |
| **restore_trigram_from_buffers** | 1340–1351 | (new) | New | Reconstruct trigram from buffer tensors |

These should likely land as new files: `core/bigram_prior.py` and `core/trigram_prior.py`.

## Evaluation & Validation

| Section | Lines | Existing | Complexity | Distinctive Improvement |
|---|---:|---|---|---|
| **eval_val** | 903–981 | `core/core_eval.py` / `core/loss_eval.py` | Major | Distributed val loss + BPB; bigram entropy weighting; stride-based; cross-rank synchronized |

## Training-Loop Utilities

| Section | Lines | Existing | Complexity | Notes |
|---|---:|---|---|---|
| **launch/finish_bucketed_allreduce_grads** | 790–838 | (new) | New | Generic bucketed all-reduce; useful for non-Muon non-AdamW cross-rank averaging |
| **clip_grad_norm_no_sync_** | 730–786 | `core/optim.py` (DONE) | Done | No host sync; foreach when available |
| **wallclock_fraction / aux_obf_scale / qat_noise_scale / transformer_gate_scale** | 1763–1829 | (new) | New | Step- and wallclock-driven ramps for QAT, OBF, gate floors |
| **build_optimizer_groups** | 1473–1571 | (no equivalent) | New | Explicit param taxonomy (embed/head/route/aux_adam/small_matrix_adam/scalar/muon) — defends against accidental routing of bias/norm/head into Muon |
| **assert_no_bad_muon_params** | 1574–1602 | (no equivalent) | New | Forbid-list guard against routing tok_emb/lm_head/local_head/global_head/bias/norm into Muon |
| **freeze_unused_local_only_params / freeze_spine_fallback_params** | 1678–1701 | (new) | New | Freeze spine fallback paths; needed for the local-only rescue and spine-frozen modes |
| **state_dict_for_export / restore_low_dim_params_to_fp32 / restore_runtime_linear_modules_to_fp32** | 1703–1731 | (new) | New | Export-side state-dict surgery for QAT/INT4 deployment |
| **main()** | 3332–4587 | `__main__.py` / scripts | Major | Full distributed training harness; warmup; route stability; nonfinite guards; curriculum loading |

## Recommended Extraction Order

For subsequent sessions, in priority order (each builds on prior):

1. **`build_optimizer_groups` + `assert_no_bad_muon_params`** → `core/optim_groups.py` (or `core/optim.py`). These pair naturally with the Muon work just done; the existing codebase has no analog.
2. **`clip_grad_norm_no_sync_`** → already in `core/optim.py` as of 2026-05-06.
3. **Bigram/trigram priors** → new files `core/bigram_prior.py`, `core/trigram_prior.py`. Self-contained; no existing equivalent.
4. **Scaling/ramp utilities** → new file `core/scheduling.py` (`wallclock_fraction`, `aux_obf_scale`, `qat_noise_scale`, `transformer_gate_scale`).
5. **QAT/INT4 helpers** → `core/quant.py` or fold into `core/fp8.py`. Adds 4-bit alongside the existing INT8.
6. **Data loading**: replace `core/dataloader.py` with `TokenStream` + `DistributedTokenLoader`; add `load_data_shard`, `compute_shard_mean_entropy`.
7. **Validation**: replace `core/loss_eval.py` / `core/core_eval.py` with `eval_val` + `load_validation_tokens` + `build_sentencepiece_luts`.
8. **HYDRA architecture wholesale** → `core/gpt.py` becomes a re-export of HydraLocalBlock/HydraGlobalBlock/SageBus/CausalInterferometer/HydraMLP/RMSNorm/Rotary + the bifurcated GPT class. This is the largest replacement (~1100 lines moved).
9. **Hyperparameters**: tackle last; touches everything.
10. **`main()`**: do not extract directly; use as reference for refactoring `__main__.py` and `scripts/base_train.py` once everything else is in place.

## Notes

- The HYDRA architecture is the **central distinctive contribution** — it does not exist in the existing modular codebase and represents a fundamentally different design (bifurcated local/global with SAGE routing and bigram/trigram priors as additive log-prior terms).
- Bigram/trigram priors integrate into the model as auxiliary log-prior contributions to logits — they are **architectural**, not just curriculum hints.
- `build_optimizer_groups` pairs naturally with the Muon work: the existing codebase routes params heuristically; the monolith's explicit taxonomy + assert guard would prevent regressions.
