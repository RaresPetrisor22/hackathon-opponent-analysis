"""Smoke tests for backend/app/llm/client.py.

Run with:
    cd backend
    uv run pytest tests/test_llm_client.py -v

No real API calls are made — the ChatOpenAI chain is fully mocked.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from unittest.mock import AsyncMock, MagicMock, patch


class _SampleSchema(BaseModel):
    headline: str
    score: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chain_mock(return_value: BaseModel) -> MagicMock:
    """Return a mock chain whose ainvoke returns return_value."""
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=return_value)
    return chain


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoke_structured_returns_pydantic_model() -> None:
    """invoke_structured should return a validated instance of the schema."""
    expected = _SampleSchema(headline="Test", score=42)

    with patch("app.llm.client._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Patch ChatPromptTemplate so the full chain resolves to our mock
        with patch("app.llm.client.ChatPromptTemplate") as mock_tpl:
            chain_mock = _make_chain_mock(expected)
            mock_tpl.from_messages.return_value.__or__ = MagicMock(return_value=chain_mock)

            from app.llm.client import invoke_structured
            result = await invoke_structured("sys", "user", _SampleSchema)

    assert isinstance(result, _SampleSchema)
    assert result.headline == "Test"
    assert result.score == 42


@pytest.mark.asyncio
async def test_invoke_structured_retries_on_rate_limit() -> None:
    """invoke_structured should retry up to 3 times on rate-limit errors."""
    expected = _SampleSchema(headline="Retry success", score=1)
    call_count = 0

    async def _flaky_invoke(_input: dict) -> _SampleSchema:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("rate limit exceeded (429)")
        return expected

    with patch("app.llm.client._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.llm.client.ChatPromptTemplate") as mock_tpl:
            chain_mock = MagicMock()
            chain_mock.ainvoke = AsyncMock(side_effect=_flaky_invoke)
            mock_tpl.from_messages.return_value.__or__ = MagicMock(return_value=chain_mock)

            # Patch asyncio.sleep so tests don't actually wait
            with patch("app.llm.client.asyncio.sleep", new_callable=AsyncMock):
                from app.llm.client import invoke_structured
                result = await invoke_structured("sys", "user", _SampleSchema)

    assert result.headline == "Retry success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_invoke_structured_raises_after_max_retries() -> None:
    """invoke_structured should re-raise after exhausting all retries."""
    async def _always_rate_limit(_input: dict) -> None:
        raise Exception("rate limit exceeded (429)")

    with patch("app.llm.client._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.llm.client.ChatPromptTemplate") as mock_tpl:
            chain_mock = MagicMock()
            chain_mock.ainvoke = AsyncMock(side_effect=_always_rate_limit)
            mock_tpl.from_messages.return_value.__or__ = MagicMock(return_value=chain_mock)

            with patch("app.llm.client.asyncio.sleep", new_callable=AsyncMock):
                from app.llm.client import invoke_structured
                with pytest.raises(Exception, match="rate limit"):
                    await invoke_structured("sys", "user", _SampleSchema)
