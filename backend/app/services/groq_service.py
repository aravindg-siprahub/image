import re
import json
import asyncio
from datetime import date
from groq import AsyncGroq, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    retry_if_exception,
)
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Quota-exhaustion 429s often carry Retry-After of many minutes; do not burn retries.
QUOTA_RETRY_AFTER_LIMIT_S = 10.0


class QuotaExhaustedError(Exception):
    """Non-retryable: Groq returned a long Retry-After 429 (daily/quota exhaustion)."""

    def __init__(self, message: str, retry_after_s: float | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


def _parse_retry_after_from_message(msg: str) -> float | None:
    """Parse Groq body text like 'Please try again in 15m47.376s'."""
    m = re.search(r"try again in\s+(?:(\d+)m)?(\d+(?:\.\d+)?)s", msg, re.I)
    if not m:
        return None
    minutes = float(m.group(1) or 0)
    seconds = float(m.group(2))
    return minutes * 60.0 + seconds


def _extract_retry_after_seconds(exc: BaseException) -> float | None:
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers is not None:
            raw = headers.get("retry-after") or headers.get("Retry-After")
            if raw is not None:
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    pass
    return _parse_retry_after_from_message(str(exc))


def _is_retryable_groq_error(exc: BaseException) -> bool:
    # QuotaExhaustedError must not be retried by tenacity.
    return not isinstance(exc, QuotaExhaustedError)


class GroqClientManager:
    def __init__(self):
        self.clients = []
        if settings.GROQ_API_KEY:
            self.clients.append(AsyncGroq(api_key=settings.GROQ_API_KEY))
        if settings.GROQ_API_KEY_2:
            self.clients.append(AsyncGroq(api_key=settings.GROQ_API_KEY_2))
            
        if not self.clients:
            logger.warning("No Groq API keys found. Vision analysis will fail.")
            
        self.current_client_index = 0
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(settings.GROQ_MAX_CONCURRENCY)
        # Soft in-process daily token tracker (single Railway instance).
        self._usage_day: date = date.today()
        self._tokens_used_today: int = 0

    def _maybe_reset_daily_usage(self) -> None:
        today = date.today()
        if today != self._usage_day:
            self._usage_day = today
            self._tokens_used_today = 0

    def _remaining_tokens(self) -> int:
        self._maybe_reset_daily_usage()
        return max(0, settings.GROQ_DAILY_TOKEN_BUDGET - self._tokens_used_today)

    def _record_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            # Fallback estimate when SDK omits usage
            self._tokens_used_today += settings.GROQ_TOKEN_RESERVE_PER_IMAGE
            return
        total = getattr(usage, "total_tokens", None)
        if total is None:
            prompt_t = getattr(usage, "prompt_tokens", 0) or 0
            completion_t = getattr(usage, "completion_tokens", 0) or 0
            total = prompt_t + completion_t
        try:
            self._tokens_used_today += int(total)
        except (TypeError, ValueError):
            self._tokens_used_today += settings.GROQ_TOKEN_RESERVE_PER_IMAGE

    def _ensure_token_budget(self) -> None:
        remaining = self._remaining_tokens()
        if remaining < settings.GROQ_TOKEN_RESERVE_PER_IMAGE:
            raise QuotaExhaustedError(
                f"quota exhausted, try later "
                f"(remaining_tokens={remaining}, "
                f"need>={settings.GROQ_TOKEN_RESERVE_PER_IMAGE})",
                retry_after_s=None,
            )

    async def get_next_client(self) -> AsyncGroq:
        async with self.lock:
            if not self.clients:
                raise ValueError("No Groq clients available.")
            client = self.clients[self.current_client_index]
            self.current_client_index = (self.current_client_index + 1) % len(self.clients)
            return client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception(_is_retryable_groq_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def analyze_image_with_retry(self, image_url: str) -> dict:
        # Pre-flight soft budget check — avoid calling Groq when daily tokens are gone.
        self._ensure_token_budget()

        client = await self.get_next_client()
        
        # We pass the proxy URL directly to Groq.
        prompt = """You are a professional photo quality analyst. Analyze this image and score ONLY what you can directly observe.

Return ONLY valid JSON with these exact fields:

{
  "sharpness": <0-100, how sharp/in-focus the main subject is. 100=razor sharp, 0=completely soft>,
  "blur": <0-100, amount of motion blur or defocus blur present. 100=extremely blurry, 0=no blur at all>,
  "exposure": <0-100, where 0=completely black/underexposed, 50-70=well-exposed, 100=completely blown out/overexposed>,
  "lighting": <0-100, quality of light. 100=beautiful directional/golden-hour light, 0=harsh flat or no light>,
  "composition": <0-100, rule of thirds, framing, leading lines, subject placement. 100=professional composition>,
  "subject_clarity": <0-100, how clearly visible and unobstructed the main subject is. 100=perfectly clear>,
  "face_quality": <0-100 IF human faces are present and visible, null if NO faces in image>,
  "visual_appeal": <0-100, overall aesthetic and emotional impact of the image>,
  "technical_quality": <0-100, overall technical execution: focus, noise, chromatic aberration, distortion>,
  "is_usable": <true if image is usable for any purpose, false ONLY if image is corrupted/completely unusable>,
  "reason": "<one concise sentence explaining the most important quality characteristic of this image>"
}

IMPORTANT RULES:
- Score sharpness and blur INDEPENDENTLY (a photo can have low blur but still be soft)
- face_quality MUST be null (not 0) when no faces are present
- is_usable = false ONLY for corrupted files or pitch-black images, NOT for stylistic choices
- Do not invent scores; score only what you can see
- reason should mention the single most impactful positive or negative quality"""

        try:
            response = await client.chat.completions.create(
                model=settings.GROQ_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1024,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            self._record_usage(response)
            
            content = response.choices[0].message.content
            # JSON mode is requested via response_format; keep light cleanup for safety
            try:
                # Basic cleanup if model surrounds it with markdown ```json ... ```
                cleaned = content.replace("```json", "").replace("```", "").strip()
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from Qwen: {content}")
                raise ValueError("Invalid JSON from Groq vision model")
        except RateLimitError as e:
            ra = _extract_retry_after_seconds(e)
            logger.error(
                f"Groq 429 on model {settings.GROQ_VISION_MODEL}: "
                f"retry_after_s={ra} error={e}"
            )
            # Long/unknown Retry-After = quota exhaustion — fail immediately, do not retry.
            if ra is None or ra > QUOTA_RETRY_AFTER_LIMIT_S:
                raise QuotaExhaustedError(
                    f"Groq quota exhausted (retry_after_s={ra})",
                    retry_after_s=ra,
                ) from e
            # Short 429 — allow tenacity retry
            raise
        except QuotaExhaustedError:
            raise
        except Exception as e:
            logger.error(f"Groq API error on model {settings.GROQ_VISION_MODEL}: {e}")
            raise e

    async def analyze_image(self, image_url: str) -> dict:
        async with self.semaphore:
            return await self.analyze_image_with_retry(image_url)

groq_manager = GroqClientManager()
