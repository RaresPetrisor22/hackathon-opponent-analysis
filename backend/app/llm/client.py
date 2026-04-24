from __future__ import annotations

import asyncio
import json
from typing import Any, TypeVar, overload

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model="gpt-4o",
            api_key=settings.openai_api_key,
            temperature=0.3,
        )
    return _llm


@overload
async def call_llm(
    system: str,
    user: str,
    response_schema: type[T],
) -> T: ...


@overload
async def call_llm(
    system: str,
    user: str,
    response_schema: None = None,
) -> str: ...


async def call_llm(
    system: str,
    user: str,
    response_schema: type[T] | None = None,
) -> T | str:
    """Send a chat completion request through LangChain/OpenAI.

    If response_schema is provided, the model is instructed to return JSON
    conforming to the schema and the result is parsed into that Pydantic model.

    Retries up to 3 times on rate-limit errors with exponential backoff.

    Args:
        system: System prompt string (from prompts.py).
        user: User message string.
        response_schema: Optional Pydantic model class to parse the response into.

    Returns:
        Parsed Pydantic model if response_schema given, else raw string.
    """
    llm = _get_llm()
    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    if response_schema is not None:
        schema_hint = json.dumps(response_schema.model_json_schema(), indent=2)
        messages[0] = SystemMessage(
            content=system
            + f"\n\nRespond with valid JSON matching this schema:\n{schema_hint}"
        )

    for attempt in range(3):
        try:
            response = await llm.ainvoke(messages)
            text: str = response.content  # type: ignore[assignment]
            if response_schema is not None:
                raw = json.loads(text)
                return response_schema.model_validate(raw)
            return text
        except Exception as exc:
            if "rate" in str(exc).lower() and attempt < 2:
                await asyncio.sleep(2 ** attempt * 5)
                continue
            raise

    raise RuntimeError("LLM call failed after retries")


async def call_llm_raw(system: str, user: str) -> str:
    """Convenience wrapper returning plain string."""
    return await call_llm(system, user, response_schema=None)
