from app.config.settings import settings
from app.services.llm.base import LLMProvider

_instances: dict[str, LLMProvider] = {}


def get_llm_client(provider_name: str | None = None) -> LLMProvider:
    """
    Return a singleton LLMProvider instance for the given provider.
    Defaults to settings.LLM_PROVIDER if provider_name is None.
    """
    name = provider_name or settings.LLM_PROVIDER

    if name not in _instances:
        _instances[name] = _build(name)

    return _instances[name]


def _build(name: str) -> LLMProvider:
    if name in ("groq_free", "groq_dev", "groq"):
        from app.services.llm.groq_provider import GroqProvider
        return GroqProvider()

    raise ValueError(
        f"Unknown LLM provider: '{name}'. "
        "Valid options: 'groq_free', 'groq_dev'."
    )
