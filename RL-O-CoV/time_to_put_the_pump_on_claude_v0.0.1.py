import torch
import torch.nn as nn
import torch.nn.functional as F
import re
from typing import Dict, Any, Optional, List, Tuple
import contextlib

# --- CONFIGURATION ---
MORPHEMIC_CONFIG = {
    "max_sequence_length": 1024,
    "analysis_layer": 16,  # Deeper layers capture abstract reasoning
    "learning_rate": 1e-6,  # Conservative LR for stability
    "beta_threshold": 0.1,
    "drift_penalty_weight": 0.5,
    "generation_max_new_tokens": 512,
    "temperature": 1.0,  # High temperature for exploration in RL
    "device": "cuda" if torch.cuda.is_available() else "cpu"
}


# --- THREAD-SAFE SEMANTIC CAPTURE ---
class SemanticCaptureContext:
    """
    Context manager to grab hidden states from specific layers
    without modifying the model architecture.
    """

    def __init__(self, model, layer_idx):
        self.model = model
        self.layer_idx = layer_idx
        self.captured_embeddings = None
        self.hook_handle = None

    def _hook_fn(self, module, input, output):
        # Handle HuggingFace tuple outputs vs raw tensors
        if isinstance(output, tuple):
            self.captured_embeddings = output[0]
        else:
            self.captured_embeddings = output

    def __enter__(self):
        # Robust layer detection for Llama, GPT, Mistral, etc.
        # at moment anthropic no open weight model
        if hasattr(self.model, 'model') and hasattr(self.model.model, 'layers'):
            target_layer = self.model.model.layers[self.layer_idx]
        elif hasattr(self.model, 'transformer') and hasattr(self.model.transformer, 'h'):
            target_layer = self.model.transformer.h[self.layer_idx]
        elif hasattr(self.model, 'layers'):  # Generic sequential
            target_layer = self.model.layers[self.layer_idx]
        else:
            # Fallback: attempt to access by index from children
            target_layer = list(self.model.children())[self.layer_idx]

        self.hook_handle = target_layer.register_forward_hook(self._hook_fn)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.hook_handle:
            self.hook_handle.remove()


# --- THE RL-O-CoV TRAINER ---
class RLOCovTrainer:
    def __init__(self, model, tokenizer):
        self.model = model.to(MORPHEMIC_CONFIG["device"])
        self.tokenizer = tokenizer
        # Freeze early layers to preserve linguistic competence
        # We only want to train the "Reasoning" capability
        for name, param in self.model.named_parameters():
            if "layers.0." in name or "layers.1." in name or "embeddings" in name:
                param.requires_grad = False

        self.optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=MORPHEMIC_CONFIG["learning_rate"]
        )

    def _get_sentence_embedding(self, text: str):
        """
        Extracts semantic vector for drift detection.
        Uses mean pooling of the analysis layer.
        """
        if not text: return torch.zeros(self.model.config.hidden_size).to(self.model.device)

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True,
                                max_length=MORPHEMIC_CONFIG["max_sequence_length"]).to(self.model.device)

        with SemanticCaptureContext(self.model, MORPHEMIC_CONFIG["analysis_layer"]) as capturer:
            with torch.no_grad():
                self.model(**inputs)

            # [Batch, Seq, Dim] -> [Dim] (Mean Pool)
            if capturer.captured_embeddings is not None:
                embeddings = capturer.captured_embeddings.squeeze(0)
                return torch.mean(embeddings, dim=0)
            return torch.zeros(self.model.config.hidden_size).to(self.model.device)

    def calculate_reward(self, full_generation: str, expected_answer: str, problem_context_vec: torch.Tensor):
        """
        Computes the O-CoV Reward: Accuracy + Structure + Resonance - Drift
        """
        # Parse: Assume format "... SYNTHESIS: <Answer>" or simple text
        # Robust splitting to separate "Reasoning" from "Final Answer"
        if "SYNTHESIS" in full_generation:
            parts = full_generation.split("SYNTHESIS")
            trace_content = parts[0]
            final_answer = parts[-1]
        else:
            trace_content = full_generation
            final_answer = full_generation

        # 1. Terminal Accuracy
        # Using simple inclusion for now; replace with specific parser for math/code
        acc_reward = 2.0 if expected_answer.lower() in final_answer.lower() else -1.0

        # 2. Structural Integrity
        phases = ["DETECT", "HYPOTHESIZE", "OSCILLATION", "SYNTHESIZE"]
        found_phases = sum(1 for p in phases if p in full_generation)
        struct_reward = (found_phases / len(phases)) * 1.5

        # 3. Resonance (Self-Consistency)
        ## HOW YOU LIKE ME NOW?
        res_reward = 0.0
        if "OSCILLATION" in trace_content and "HYPOTHESIZE" in trace_content:
            # Check if Oscillation (Antithesis) vector relates to Hypothesis (Thesis)
            try:
                hyp_text = trace_content.split("HYPOTHESIZE")[1].split("OSCILLATION")[0]
                osc_text = trace_content.split("OSCILLATION")[1].split("SYNTHESIZE")[0]

                hyp_vec = self._get_sentence_embedding(hyp_text)
                osc_vec = self._get_sentence_embedding(osc_text)

                # We want them to NOT be identical (Process check) but semantically related
                sim = F.cosine_similarity(hyp_vec, osc_vec, dim=0).item()
                # Reward "Tension" (0.3 < sim < 0.8) - not too close, not irrelevant
                if 0.3 < sim < 0.8:
                    res_reward = 1.0
            except:
                pass

        # 4. Hallucination (Drift)
        full_trace_vec = self._get_sentence_embedding(full_generation)
        drift = 1.0 - F.cosine_similarity(full_trace_vec, problem_context_vec, dim=0).item()
        drift_penalty = drift * MORPHEMIC_CONFIG["drift_penalty_weight"]

        return acc_reward + struct_reward + res_reward - drift_penalty

    def train_step(self, problem: str, expected_answer: str):
        """
        Full REINFORCE Step: Generate -> Evaluate -> Update
        """
        self.model.train()
        self.optimizer.zero_grad()

        # A. PREPARE INPUTS
        input_ids = self.tokenizer.encode(problem, return_tensors="pt").to(self.model.device)

        # B. GENERATE TRAJECTORY (Policy Execution)
        # We need gradients, but .generate() is usually non-differentiable.
        # We sample first, then re-compute log_probs for the specific sampled path.
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids,
                max_new_tokens=MORPHEMIC_CONFIG["generation_max_new_tokens"],
                do_sample=True,
                temperature=MORPHEMIC_CONFIG["temperature"],
                pad_token_id=self.tokenizer.eos_token_id
            )

        # Extract generated tokens (exclude prompt)
        generated_ids = output_ids[0][input_ids.shape[1]:]
        generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        # C. COMPUTE REWARD
        # Calculate context vector for drift detection
        with torch.no_grad():
            problem_context_vec = self._get_sentence_embedding(problem)

        reward = self.calculate_reward(generated_text, expected_answer, problem_context_vec)

        # D. COMPUTE POLICY GRADIENT
        # We re-run the forward pass on the full sequence (prompt + generation)
        # to get the differentiable logits for the tokens we just chose.
        outputs = self.model(output_ids)
        logits = outputs.logits  # [1, Seq_Len, Vocab]

        # Shift logits and labels for Causal LM training
        # Logits: predict next token. Labels: the actual next token.
        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = output_ids[..., 1:].contiguous()

        # E. MASKING (Critical)
        # We must ignore the loss from the prompt tokens. We only reinforce the generation.
        # Create a mask of -100 (PyTorch ignore_index)
        prompt_len = input_ids.shape[1]
        labels = shift_labels.clone()
        labels[:, :prompt_len - 1] = -100  # Mask prompt

        # Calculate Cross Entropy (Negative Log Likelihood per token)
        # reduction='none' gives us loss per token
        loss_fct = nn.CrossEntropyLoss(reduction='none')
        token_losses = loss_fct(shift_logits.view(-1, shift_logits.size(-1)), labels.view(-1))

        # The Policy Gradient Loss: Loss = -Reward * log(p(action))
        # Since token_loss IS -log(p), we just multiply by Reward.
        # We sum losses over the generated sequence.

        # Note: If reward is positive, we minimize (Loss * -1) -> Maximize Prob
        # If reward is negative, we minimize (Loss * 1) -> Minimize Prob
        policy_loss = torch.sum(token_losses * -reward)

        # F. BACKPROPAGATION
        policy_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        return {
            "loss": policy_loss.item(),
            "reward": reward,
            "trace": generated_text[:50] + "..."  # Log snippet
        }