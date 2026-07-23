from .anthropic import AnthropicProvider
from .openai_compatible import OpenAICompatibleProvider


def create_provider(name: str, **kwargs):
    if name.lower() in {"claude", "anthropic"}:
        return AnthropicProvider(**kwargs)
    return OpenAICompatibleProvider(provider_name=name, **kwargs)


__all__ = ["AnthropicProvider", "OpenAICompatibleProvider", "create_provider"]
