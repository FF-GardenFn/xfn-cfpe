# Prompt Maker Agent

**Status**: Planned

Generates prompt variants for systematic A/B testing.

## Capabilities

- **Ablation**: Remove components to measure contribution
- **Compression**: Minimize tokens while preserving intent
- **Rephrase**: Test alternate framings

## Design Spec

See `/designs/template-writer/DESIGN.md` for full specification.

## Integration

```
prompt-maker → generates → /content/prompts/{variant}.md
                         → tested by → /src/get_responses/
                         → scored by → /agents/LLM-as-judge/
```
