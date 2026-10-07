import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.prompts import GLOBAL_SYSTEM_PROMPT
from app.ai.retry import bounded_retry
from app.core.config import Settings
from app.reports.schemas import AIInterpretation
from app.services.contracts import AIRequest, AIResult

logger = logging.getLogger(__name__)


class AIProviderUnavailable(RuntimeError):
    pass


class GeminiBlockedResponse(AIProviderUnavailable):
    pass


class GeminiProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[..., Any] = genai.Client,
    ) -> None:
        self.settings = settings
        self.client_factory = client_factory

    async def generate(self, request: AIRequest) -> AIResult:
        if not self.settings.gemini_enabled or not self.settings.gemini_api_key or not self.settings.gemini_model:
            raise AIProviderUnavailable("Gemini is not configured.")
        client = self.client_factory(api_key=self.settings.gemini_api_key)
        user_content = json.dumps(
            {"task": request.task, "validated_data": request.structured_input},
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        started = time.monotonic()

        async def call() -> AIResult:
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=self.settings.gemini_model,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=GLOBAL_SYSTEM_PROMPT,
                            temperature=self.settings.gemini_temperature,
                            response_mime_type="application/json",
                            response_schema=AIInterpretation,
                            safety_settings=gemini_safety_settings(),
                        ),
                    ),
                    timeout=self.settings.gemini_timeout_seconds,
                )
            except asyncio.TimeoutError as error:
                raise AIProviderUnavailable("Gemini request timed out.") from error
            if _was_blocked(response):
                raise GeminiBlockedResponse("Gemini blocked the report interpretation.")
            text = response.text
            if not text or not text.strip():
                raise AIProviderUnavailable("Gemini returned an empty report interpretation.")
            try:
                structured = AIInterpretation.model_validate_json(text)
            except (ValueError, ValidationError) as error:
                raise AIProviderUnavailable("Gemini returned invalid structured output.") from error
            return AIResult(
                content=structured.model_dump(mode="json"),
                provider="GEMINI",
            )

        def retryable(error: Exception) -> bool:
            if isinstance(error, GeminiBlockedResponse):
                return False
            if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError)):
                return True
            if isinstance(error, AIProviderUnavailable):
                return "invalid structured output" in str(error) or "empty" in str(error)
            return isinstance(error, errors.APIError) and getattr(error, "code", 0) in {429, 500, 502, 503, 504}

        try:
            result = await bounded_retry(
                call,
                attempts=self.settings.gemini_max_retries + 1,
                retryable=retryable,
            )
        except GeminiBlockedResponse:
            logger.info(
                "gemini_interpretation_blocked",
                extra={"model": self.settings.gemini_model},
            )
            raise
        except Exception as error:
            logger.warning(
                "gemini_interpretation_unavailable",
                extra={
                    "model": self.settings.gemini_model,
                    "error_type": type(error).__name__,
                },
            )
            raise AIProviderUnavailable("Gemini interpretation is temporarily unavailable.") from error
        logger.info(
            "gemini_interpretation_completed",
            extra={
                "model": self.settings.gemini_model,
                "latency_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return result


def gemini_safety_settings() -> list[types.SafetySetting]:
    categories = (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    )
    return [
        types.SafetySetting(
            category=category,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        )
        for category in categories
    ]


def _was_blocked(response: Any) -> bool:
    prompt_feedback = getattr(response, "prompt_feedback", None)
    if getattr(prompt_feedback, "block_reason", None):
        return True
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        finish_reason = str(getattr(candidate, "finish_reason", "")).upper()
        if "SAFETY" in finish_reason or "BLOCK" in finish_reason:
            return True
    return False
