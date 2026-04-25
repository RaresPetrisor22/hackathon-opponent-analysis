"""Chat endpoint — answers questions using only the provided dossier data.

The frontend sends the full dossier JSON alongside the user's question.
The LLM is given a strict system prompt that forbids hallucination and
limits answers to the data provided.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.llm.client import _get_llm

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    dossier: dict[str, Any]
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# System prompt — the key to avoiding hallucination
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the FC Universitatea Cluj match‐analysis assistant.

RULES — follow these without exception:
1. You may ONLY use the data provided in the <dossier> block below to answer.
2. If the user asks something that cannot be answered from the dossier data, \
say exactly: "I don't have that information in the current dossier."
3. NEVER invent statistics, player names, scores, dates, or any other facts.
4. Keep answers concise, clear, and professional — suitable for a coaching staff.
5. When citing numbers, use the exact values from the dossier.
6. You may combine data points from different sections to form insights, but \
every claim must be traceable to the dossier.
7. Format your responses in short paragraphs. Use bullet points when listing \
multiple items.
8. Answer in the same language the user asks in.

<dossier>
{dossier_json}
</dossier>
"""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Answer a question about the opponent dossier."""
    try:
        llm = _get_llm()

        dossier_json = json.dumps(req.dossier, ensure_ascii=False, default=str)
        system = SYSTEM_PROMPT.format(dossier_json=dossier_json)

        # Build message list: system + conversation history + new question
        messages: list[tuple[str, str]] = [("system", system)]
        for msg in req.history[-10:]:  # keep last 10 messages for context
            if msg.role == "user":
                messages.append(("human", msg.content))
            elif msg.role == "assistant":
                messages.append(("ai", msg.content))
        messages.append(("human", req.question))

        response = await llm.ainvoke(messages)

        answer = response.content if hasattr(response, "content") else str(response)

        logger.info("Chat answered question=%r answer_len=%d", req.question[:80], len(answer))

        return ChatResponse(answer=answer)

    except Exception as exc:
        logger.exception("Chat endpoint failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
