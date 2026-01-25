# Cross-Provider LLM Testing Framework

A unified evaluation framework for testing system prompts across multiple LLM providers. Supports Anthropic (Claude), OpenAI (GPT/o-series), Google (Gemini), and xAI (Grok) through a clean provider abstraction with extended thinking support, token tracking, and cost estimation. The framework enables A/B comparison between baseline and treatment prompts, with export to JSON/JSONL and XLSX formats.

## Quick Start

```bash
# Set API keys in root .env
# Run comparison
python -m get_responses.cli compare --query "Your question" --treatment dialectica

# Batch test
python -m get_responses.cli batch --queries dialectica_tests --prompts baseline,dialectica
```

## Structure

```
providers/     # LLM provider implementations (anthropic, openai, google, xai)
catalogs/      # Model registry (22 models) with pricing and capabilities
models/        # Pydantic request/response schemas
storage/       # Export handlers (JSON, JSONL, XLSX)
```

## Key Features

- **Multi-provider**: 4 providers, 22 models, unified interface
- **Extended thinking**: Automatic handling for Claude, Gemini 2.0+, o-series
- **Cost estimation**: Per-request cost calculation from model catalog
- **Comparison mode**: Baseline vs treatment with statistical summary
