from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """e.g. 'groq', 'gemini'"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """e.g. 'llama-3.3-70b-versatile'"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a text completion.

        Args:
            prompt: The user message / instruction.
            system_prompt: Optional system-level instruction.
            temperature: Sampling temperature (lower = more deterministic).
            max_tokens: Maximum tokens in the response.

        Returns:
            The model's text response.
        """
