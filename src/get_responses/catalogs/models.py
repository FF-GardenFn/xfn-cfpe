"""
Central registry of all supported models across providers.
Updated: January 2026 pricing

Usage:
    from catalogs import MODELS, get_model

    model = get_model("haiku")
    print(model.model_id)  # claude-haiku-4-5-20251001
    print(model.provider)  # anthropic
"""
from typing import Dict, List, Optional
from .schemas import ModelConfig, Provider


# =============================================================================
# ANTHROPIC MODELS (Claude) - Jan 2026 Pricing
# =============================================================================

CLAUDE_OPUS = ModelConfig(
    name="opus",
    model_id="claude-opus-4-5-20251101",
    provider=Provider.ANTHROPIC,
    max_output_tokens=16384,
    context_window=200000,
    supports_thinking=True,
    thinking_budget=32000,
    cost_per_input_mtok=5.0,
    cost_per_output_mtok=25.0,
    cost_per_thinking_mtok=5.0,
    supports_vision=True,
)

CLAUDE_SONNET = ModelConfig(
    name="sonnet",
    model_id="claude-sonnet-4-20250514",
    provider=Provider.ANTHROPIC,
    max_output_tokens=16384,
    context_window=200000,
    supports_thinking=True,
    thinking_budget=16000,
    cost_per_input_mtok=0.30,
    cost_per_output_mtok=1.50,
    cost_per_thinking_mtok=0.30,
    supports_vision=True,
)

CLAUDE_HAIKU = ModelConfig(
    name="haiku",
    model_id="claude-haiku-4-5-20251001",
    provider=Provider.ANTHROPIC,
    max_output_tokens=8192,
    context_window=200000,
    supports_thinking=True,
    thinking_budget=8000,
    cost_per_input_mtok=0.25,
    cost_per_output_mtok=1.25,
    cost_per_thinking_mtok=0.25,
    supports_vision=True,
)

CLAUDE_45_SONNET = ModelConfig(
    name="claude-4.5-sonnet",
    model_id="claude-4-5-sonnet-20260115",
    provider=Provider.ANTHROPIC,
    max_output_tokens=16384,
    context_window=200000,
    supports_thinking=True,
    thinking_budget=16000,
    cost_per_input_mtok=3.0,
    cost_per_output_mtok=15.0,
    cost_per_thinking_mtok=3.0,
    supports_vision=True,
)


# =============================================================================
# OPENAI MODELS (GPT-4, GPT-5, o1, o3) - Jan 2026 Pricing
# =============================================================================

GPT4O = ModelConfig(
    name="gpt4o",
    model_id="gpt-4o",
    provider=Provider.OPENAI,
    max_output_tokens=16384,
    context_window=128000,
    supports_thinking=False,
    cost_per_input_mtok=2.50,
    cost_per_output_mtok=10.0,
    supports_vision=True,
)

GPT4O_MINI = ModelConfig(
    name="gpt4o-mini",
    model_id="gpt-4o-mini",
    provider=Provider.OPENAI,
    max_output_tokens=16384,
    context_window=128000,
    supports_thinking=False,
    cost_per_input_mtok=0.15,
    cost_per_output_mtok=0.60,
    supports_vision=True,
)

O1 = ModelConfig(
    name="o1",
    model_id="o1",
    provider=Provider.OPENAI,
    max_output_tokens=100000,
    context_window=200000,
    supports_thinking=False,
    supports_reasoning=True,
    cost_per_input_mtok=15.0,
    cost_per_output_mtok=60.0,
    supports_vision=True,
)

O1_MINI = ModelConfig(
    name="o1-mini",
    model_id="o1-mini",
    provider=Provider.OPENAI,
    max_output_tokens=65536,
    context_window=128000,
    supports_thinking=False,
    supports_reasoning=True,
    cost_per_input_mtok=3.0,
    cost_per_output_mtok=12.0,
    supports_vision=False,
)

O3_MINI = ModelConfig(
    name="o3-mini",
    model_id="o3-mini",
    provider=Provider.OPENAI,
    max_output_tokens=100000,
    context_window=200000,
    supports_thinking=False,
    supports_reasoning=True,
    cost_per_input_mtok=1.10,
    cost_per_output_mtok=4.40,
    supports_vision=False,
)

GPT52 = ModelConfig(
    name="gpt-5.2",
    model_id="gpt-5.2",
    provider=Provider.OPENAI,
    max_output_tokens=32768,
    context_window=400000,
    supports_thinking=False,
    supports_reasoning=True,
    cost_per_input_mtok=5.0,
    cost_per_output_mtok=25.0,
    supports_vision=True,
)

GPT52_CODEX = ModelConfig(
    name="gpt-5.2-codex",
    model_id="gpt-5.2-codex",
    provider=Provider.OPENAI,
    max_output_tokens=32768,
    context_window=400000,
    supports_thinking=False,
    supports_reasoning=True,
    cost_per_input_mtok=1.75,
    cost_per_output_mtok=14.0,
    supports_vision=False,
)

GPT5_MINI = ModelConfig(
    name="gpt-5-mini",
    model_id="gpt-5-mini",
    provider=Provider.OPENAI,
    max_output_tokens=16384,
    context_window=128000,
    supports_thinking=False,
    cost_per_input_mtok=0.25,
    cost_per_output_mtok=2.0,
    supports_vision=True,
)

GPT5_NANO = ModelConfig(
    name="gpt-5-nano",
    model_id="gpt-5-nano",
    provider=Provider.OPENAI,
    max_output_tokens=8192,
    context_window=128000,
    supports_thinking=False,
    cost_per_input_mtok=0.05,
    cost_per_output_mtok=0.50,
    supports_vision=False,
)


# =============================================================================
# GOOGLE MODELS (Gemini) - Jan 2026 Pricing
# =============================================================================

GEMINI_FLASH = ModelConfig(
    name="gemini-flash",
    model_id="gemini-2.0-flash",
    provider=Provider.GOOGLE,
    max_output_tokens=8192,
    context_window=1000000,
    supports_thinking=True,
    thinking_budget=24576,
    cost_per_input_mtok=0.08,
    cost_per_output_mtok=0.30,
    cost_per_thinking_mtok=0.08,
    supports_vision=True,
)

GEMINI_25_FLASH = ModelConfig(
    name="gemini-2.5-flash",
    model_id="gemini-2.5-flash",
    provider=Provider.GOOGLE,
    max_output_tokens=8192,
    context_window=1000000,
    supports_thinking=True,
    thinking_budget=24576,
    cost_per_input_mtok=0.10,
    cost_per_output_mtok=0.40,
    cost_per_thinking_mtok=0.10,
    supports_vision=True,
)

GEMINI_PRO = ModelConfig(
    name="gemini-pro",
    model_id="gemini-1.5-pro",
    provider=Provider.GOOGLE,
    max_output_tokens=8192,
    context_window=2000000,
    supports_thinking=True,
    thinking_budget=32768,
    cost_per_input_mtok=2.50,
    cost_per_output_mtok=10.0,
    cost_per_thinking_mtok=2.50,
    supports_vision=True,
)

GEMINI_3_PRO = ModelConfig(
    name="gemini-3-pro",
    model_id="gemini-3-pro",
    provider=Provider.GOOGLE,
    max_output_tokens=16384,
    context_window=1000000,
    supports_thinking=True,
    thinking_budget=32768,
    cost_per_input_mtok=2.0,
    cost_per_output_mtok=12.0,
    cost_per_thinking_mtok=2.0,
    supports_vision=True,
)


# =============================================================================
# XAI MODELS (Grok) - Jan 2026 Pricing
# =============================================================================

GROK_2 = ModelConfig(
    name="grok-2",
    model_id="grok-2-1212",
    provider=Provider.XAI,
    max_output_tokens=131072,
    context_window=131072,
    supports_thinking=False,
    cost_per_input_mtok=2.0,
    cost_per_output_mtok=10.0,
    supports_vision=True,
)

GROK_3 = ModelConfig(
    name="grok-3",
    model_id="grok-3",
    provider=Provider.XAI,
    max_output_tokens=131072,
    context_window=256000,
    supports_thinking=False,
    cost_per_input_mtok=3.0,
    cost_per_output_mtok=15.0,
    supports_vision=True,
)

GROK_4 = ModelConfig(
    name="grok-4",
    model_id="grok-4",
    provider=Provider.XAI,
    max_output_tokens=131072,
    context_window=256000,
    supports_thinking=False,
    cost_per_input_mtok=3.0,
    cost_per_output_mtok=15.0,
    supports_vision=True,
)

GROK_41_FAST = ModelConfig(
    name="grok-4.1-fast",
    model_id="grok-4.1-fast",
    provider=Provider.XAI,
    max_output_tokens=131072,
    context_window=2000000,  # 2M context!
    supports_thinking=False,
    cost_per_input_mtok=0.20,
    cost_per_output_mtok=0.50,
    supports_vision=True,
)

GROK_5 = ModelConfig(
    name="grok-5",
    model_id="grok-5",
    provider=Provider.XAI,
    max_output_tokens=131072,
    context_window=256000,
    supports_thinking=False,
    cost_per_input_mtok=5.0,
    cost_per_output_mtok=25.0,
    supports_vision=True,
)


# =============================================================================
# MASTER CATALOG
# =============================================================================

MODELS: Dict[str, ModelConfig] = {
    # Anthropic
    "opus": CLAUDE_OPUS,
    "sonnet": CLAUDE_SONNET,
    "haiku": CLAUDE_HAIKU,
    "claude-4.5-sonnet": CLAUDE_45_SONNET,

    # OpenAI
    "gpt4o": GPT4O,
    "gpt4o-mini": GPT4O_MINI,
    "o1": O1,
    "o1-mini": O1_MINI,
    "o3-mini": O3_MINI,
    "gpt-5.2": GPT52,
    "gpt-5.2-codex": GPT52_CODEX,
    "gpt-5-mini": GPT5_MINI,
    "gpt-5-nano": GPT5_NANO,

    # Google
    "gemini-flash": GEMINI_FLASH,
    "gemini-2.5-flash": GEMINI_25_FLASH,
    "gemini-pro": GEMINI_PRO,
    "gemini-3-pro": GEMINI_3_PRO,

    # xAI
    "grok-2": GROK_2,
    "grok-3": GROK_3,
    "grok-4": GROK_4,
    "grok-4.1-fast": GROK_41_FAST,
    "grok-5": GROK_5,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_model(name: str) -> ModelConfig:
    """Get model config by name.

    Args:
        name: Model nickname (haiku, gpt4o, gemini-flash, grok-2)

    Returns:
        ModelConfig instance

    Raises:
        ValueError: If model not found
    """
    if name not in MODELS:
        available = ", ".join(sorted(MODELS.keys()))
        raise ValueError(f"Unknown model: {name}. Available: {available}")
    return MODELS[name]


def get_models_by_provider(provider: Provider) -> Dict[str, ModelConfig]:
    """Get all models for a specific provider."""
    return {k: v for k, v in MODELS.items() if v.provider == provider}


def list_models(provider: Optional[Provider] = None) -> List[str]:
    """List available model names, optionally filtered by provider."""
    if provider:
        return [k for k, v in MODELS.items() if v.provider == provider]
    return list(MODELS.keys())


def estimate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0
) -> float:
    """Estimate cost for a single request.

    Args:
        model_name: Model nickname
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        thinking_tokens: Number of thinking tokens (if applicable)

    Returns:
        Estimated cost in USD
    """
    model = get_model(model_name)

    input_cost = (input_tokens / 1_000_000) * model.cost_per_input_mtok
    output_cost = (output_tokens / 1_000_000) * model.cost_per_output_mtok

    thinking_cost = 0.0
    if thinking_tokens > 0 and model.cost_per_thinking_mtok:
        thinking_cost = (thinking_tokens / 1_000_000) * model.cost_per_thinking_mtok

    return input_cost + output_cost + thinking_cost


def get_cheapest_models(n: int = 5, with_thinking: bool = False) -> List[str]:
    """Get the N cheapest models by output cost.

    Args:
        n: Number of models to return
        with_thinking: If True, only include models with thinking support
    """
    models = MODELS.items()
    if with_thinking:
        models = [(k, v) for k, v in models if v.supports_thinking]

    sorted_models = sorted(models, key=lambda x: x[1].cost_per_output_mtok)
    return [k for k, v in sorted_models[:n]]


def compare_models(*model_names: str) -> str:
    """Generate comparison table for models.

    Usage:
        print(compare_models("haiku", "gpt4o-mini", "gemini-flash"))
    """
    if not model_names:
        model_names = tuple(MODELS.keys())

    lines = [
        "| Model | Provider | Context | Max Out | Input $/M | Output $/M | Thinking |",
        "|-------|----------|---------|---------|-----------|------------|----------|",
    ]

    for name in model_names:
        m = get_model(name)
        thinking = "Yes" if m.supports_thinking else ("Reasoning" if m.supports_reasoning else "No")
        provider_str = m.provider.value if hasattr(m.provider, 'value') else m.provider
        ctx = f"{m.context_window // 1000}K" if m.context_window < 1000000 else f"{m.context_window // 1000000}M"
        lines.append(
            f"| {name} | {provider_str} | {ctx} | {m.max_output_tokens:,} | "
            f"${m.cost_per_input_mtok:.2f} | ${m.cost_per_output_mtok:.2f} | {thinking} |"
        )

    return "\n".join(lines)


# Quick reference when module is run directly
if __name__ == "__main__":
    print("=== MODEL CATALOG (Jan 2026) ===")
    print(compare_models())
    print()
    print(f"Total: {len(MODELS)} models across {len(Provider)} providers")
    print()
    print("Cheapest models:", get_cheapest_models(5))
    print("Cheapest with thinking:", get_cheapest_models(5, with_thinking=True))
