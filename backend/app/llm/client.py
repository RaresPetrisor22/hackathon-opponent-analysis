from __future__ import annotations

import asyncio
import logging
import time
from typing import TypeVar

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_llm: ChatOpenAI | None = None

_RETRY_DELAYS = [2, 8, 30]  # seconds; exponential-ish, capped at 30


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )
    return _llm


async def invoke_structured(system: str, user: str, schema: type[T]) -> T:
    """Send a chat completion and parse the response into a Pydantic model.

    Uses model.with_structured_output(schema) so the model is constrained to
    return JSON matching the schema — no manual json.loads needed.

    Retries up to 3 times on rate-limit errors with delays: 2s, 8s, 30s.

    Args:
        system: System message content (plain string from prompts.py or inline).
        user: Human message content with all variables already interpolated.
        schema: Pydantic model class the response should be parsed into.

    Returns:
        Validated instance of schema.
    """
    prompt = ChatPromptTemplate.from_messages(
        [("system", system), ("human", user)]
    )
    chain = prompt | _get_llm().with_structured_output(schema)

    # Estimate token count cheaply: 1 token ≈ 4 chars
    token_estimate = (len(system) + len(user)) // 4

    for attempt, delay in enumerate([0, *_RETRY_DELAYS]):
        if delay:
            await asyncio.sleep(delay)
        t0 = time.monotonic()
        try:
            result = await chain.ainvoke({"system": system, "user": user})
            elapsed = time.monotonic() - t0
            logger.info(
                "LLM call succeeded model=%s schema=%s tokens_est=%d elapsed=%.2fs",
                settings.openai_model,
                schema.__name__,
                token_estimate,
                elapsed,
            )
            return result  # type: ignore[return-value]
        except Exception as exc:
            elapsed = time.monotonic() - t0
            is_rate_limit = "rate" in str(exc).lower() or "429" in str(exc)
            logger.warning(
                "LLM call failed attempt=%d/%d model=%s schema=%s elapsed=%.2fs error=%s",
                attempt + 1,
                len(_RETRY_DELAYS) + 1,
                settings.openai_model,
                schema.__name__,
                elapsed,
                exc,
            )
            if not is_rate_limit or attempt == len(_RETRY_DELAYS):
                raise

    raise RuntimeError("invoke_structured: exceeded retries")
