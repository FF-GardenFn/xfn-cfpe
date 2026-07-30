"""CLI-backed client: routes messages.create through the local `claude` CLI.

Zero-API-key transport for pilot runs: uses the machine's authenticated
Claude Code CLI (subscription auth). Exposes the same ``.messages.create(...)``
surface the harness expects from ``anthropic.Anthropic``, so
``ExperimentRunner`` and ``IntentClassifier`` work unmodified.

Transport caveats (record in any results produced with this client):
- ``max_tokens`` is accepted but not enforceable through the CLI; model
  defaults apply.
- Even with ``--system-prompt`` the CLI adds some scaffolding of its own;
  ``--exclude-dynamic-system-prompt-sections`` minimizes but does not
  eliminate it. Within-run contrasts hold the transport constant, which is
  what the pilot design relies on.
- Tool use is disabled (``--disallowedTools "*"``, ``--max-turns 1``): the
  harness uses a text-based tool protocol and must receive pure generations.

Model provenance: the CLI's JSON envelope has **no top-level model field**. The
model that was actually served appears as the key of the ``modelUsage`` dict
(with ``canonicalModel`` nested inside it). This client captures that key and
exposes it on every response as ``served_model`` / ``canonical_model``, and
accumulates the set on ``CLIClient.served_models``, so a run *observes* which
model answered instead of assuming the requested string was honoured.
"""

import json
import subprocess
import time
from types import SimpleNamespace


def _served_model(data: dict) -> tuple[str | None, str | None]:
    """Extract the served model id from a CLI JSON envelope.

    The envelope carries no top-level model field; usage is reported as
    ``{"modelUsage": {"<served-model-id>": {..., "canonicalModel": ...}}}``.
    Returns ``(served, canonical)``; ``(None, None)`` if absent. If more than
    one model was billed for a single call the ids are joined, so the anomaly
    is visible in the record rather than silently collapsed to the first.
    """
    usage = data.get("modelUsage")
    if not isinstance(usage, dict) or not usage:
        return None, None
    ids = sorted(usage)
    entry = usage[ids[0]] if isinstance(usage[ids[0]], dict) else {}
    canonical = entry.get("canonicalModel")
    return ("+".join(ids) if len(ids) > 1 else ids[0]), canonical


class _Messages:
    def __init__(self, client: "CLIClient"):
        self._c = client

    def create(self, model: str, messages: list, system: str = None,
               max_tokens: int = None, **kwargs):
        prompt = "\n\n".join(
            m["content"] for m in messages if m.get("role") == "user"
        )
        cmd = [
            self._c.claude_bin, "-p", prompt,
            "--model", model,
            "--output-format", "json",
            "--max-turns", "1",
            "--disallowedTools", "*",
        ]
        if system:
            cmd += ["--system-prompt", system,
                    "--exclude-dynamic-system-prompt-sections"]

        last_err = None
        for attempt in range(self._c.retries + 1):
            if self._c.sleep_between:
                time.sleep(self._c.sleep_between)
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=self._c.timeout,
                )
                if proc.returncode != 0:
                    raise RuntimeError(
                        f"claude CLI exit {proc.returncode}: {proc.stderr[:300]}"
                    )
                data = json.loads(proc.stdout)
                if data.get("is_error"):
                    raise RuntimeError(f"claude CLI is_error: {str(data)[:300]}")
                text = data.get("result", "")
                if not isinstance(text, str):
                    raise RuntimeError(f"unexpected result type: {type(text)}")
                self._c.calls += 1
                self._c.total_cost_usd += data.get("total_cost_usd") or 0.0
                served, canonical = _served_model(data)
                if served:
                    self._c.served_models.add(served)
                return SimpleNamespace(
                    content=[SimpleNamespace(text=text)],
                    served_model=served,
                    canonical_model=canonical,
                    requested_model=model,
                )
            except Exception as e:  # noqa: BLE001 - retry then surface
                last_err = e
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"CLI call failed after {self._c.retries + 1} attempts: {last_err}")


class CLIClient:
    """Drop-in stand-in for anthropic.Anthropic backed by `claude -p`."""

    def __init__(self, claude_bin: str = "claude", timeout: int = 180,
                 retries: int = 2, sleep_between: float = 0.0):
        self.claude_bin = claude_bin
        self.timeout = timeout
        self.retries = retries
        self.sleep_between = sleep_between
        self.calls = 0
        self.total_cost_usd = 0.0  # accounting metadata reported by the CLI
        self.served_models: set[str] = set()  # observed, not assumed
        self.messages = _Messages(self)
