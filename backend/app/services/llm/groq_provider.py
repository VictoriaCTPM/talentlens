import asyncio
import hashlib
import logging
import time

from groq import AsyncGroq, RateLimitError

from app.config.settings import settings
from app.services.llm.base import LLMProvider
from app.utils.rate_limiter import GROQ_FREE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

_rate_limiter = TokenBucketRateLimiter(
    requests_per_minute=GROQ_FREE_LIMITS["rpm"],
    requests_per_day=GROQ_FREE_LIMITS["rpd"],
    tokens_per_minute=GROQ_FREE_LIMITS["tpm"],
    tokens_per_day=GROQ_FREE_LIMITS["tpd"],
)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


class GroqProvider(LLMProvider):
    """LLM provider backed by Groq's API (llama-3.3-70b-versatile)."""

    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return "llama-3.3-70b-versatile"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        estimated_tokens = len(prompt.split()) * 2  # rough estimate

        for attempt in range(_MAX_RETRIES):
            await _rate_limiter.acquire(estimated_tokens)
            start = time.monotonic()
            status = "success"
            input_tokens = output_tokens = None

            try:
                response = await self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                result = response.choices[0].message.content or ""

                self._log(prompt_hash, input_tokens, output_tokens, latency_ms, status)
                return result

            except RateLimitError:
                latency_ms = int((time.monotonic() - start) * 1000)
                status = "rate_limited"
                self._log(prompt_hash, input_tokens, output_tokens, latency_ms, status)

                if attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_BASE ** (attempt + 1)
                    logger.warning("Groq 429 — retrying in %.1fs (attempt %d/%d)", wait, attempt + 1, _MAX_RETRIES)
                    await asyncio.sleep(wait)
                else:
                    raise

            except Exception as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                status = "error"
                self._log(prompt_hash, input_tokens, output_tokens, latency_ms, status)
                logger.error("Groq error: %s", exc)
                raise

        raise RuntimeError("Groq generate() exhausted all retries")

    def _log(
        self,
        prompt_hash: str,
        input_tokens: int | None,
        output_tokens: int | None,
        latency_ms: int,
        status: str,
    ) -> None:
        """Best-effort log to AICallLog. Skips silently on DB errors."""
        try:
            from app.models.database import SessionLocal
            from app.models.database import AICallLog

            cost = None
            if input_tokens and output_tokens:
                # Groq llama-3.3-70b-versatile pricing: $0.59/M input, $0.79/M output
                cost = (input_tokens * 0.59 + output_tokens * 0.79) / 1_000_000

            db = SessionLocal()
            try:
                entry = AICallLog(
                    provider=self.provider_name,
                    model=self.model_name,
                    endpoint="chat/completions",
                    prompt_hash=prompt_hash,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    status=status,
                    cost_estimate=cost,
                )
                db.add(entry)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug("AICallLog write failed (non-fatal): %s", exc)
