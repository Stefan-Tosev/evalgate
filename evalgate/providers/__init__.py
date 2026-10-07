"""Provider registry.

A provider is anything with `.name`, `.model`, `.complete(...)` and
`.judge(...)`. Adding one means adding a module here — the runner, the
assertions, and the baseline never learn which model they are testing.
"""

from __future__ import annotations


def build_provider(name: str, *, model: str, effort: str = "medium", seed: int | None = None):
    if name == "mock":
        from .mock import MockProvider

        return MockProvider(model=model, effort=effort, seed=seed)

    if name == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(model=model, effort=effort)

    raise ValueError(f"unknown provider {name!r}")
