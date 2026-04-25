"""Chat endpoint — answers questions using only the provided dossier data.

The frontend sends the full dossier JSON alongside the user's question.
The LLM is given a strict system prompt that forbids hallucination and
limits answers to the data provided.
"""
from __future__ import annotations

import json
import logging
import aiosqlite
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.llm.client import _get_llm
from app.config import settings

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
# Database Tools
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite+aiosqlite:///"):
        return url.replace("sqlite+aiosqlite:///", "")
    return url.replace("sqlite:///", "")

@tool
async def get_team_roster(team_name: str) -> str:
    """Get the full roster of players for a specific team."""
    path = _get_db_path()
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            query = """
            SELECT p.name, p.position, p.jersey_number, p.nationality, p.age
            FROM players p
            JOIN teams t ON p.team_id = t.id
            WHERE t.name LIKE ?
            """
            async with db.execute(query, (f"%{team_name}%",)) as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    return f"No roster found for team matching {team_name}."
                results = [dict(row) for row in rows]
                return json.dumps(results, default=str)
    except Exception as e:
        return f"Error: {e}"

@tool
async def get_recent_matches(team_name: str, limit: int = 5) -> str:
    """Get the recent matches played by a specific team, including scores and formations."""
    path = _get_db_path()
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            query = """
            SELECT m.date, m.status, 
                   th.name as home_team, m.home_score, m.formation_home,
                   ta.name as away_team, m.away_score, m.formation_away
            FROM matches m
            JOIN teams th ON m.home_team_id = th.id
            JOIN teams ta ON m.away_team_id = ta.id
            WHERE th.name LIKE ? OR ta.name LIKE ?
            ORDER BY m.date DESC
            LIMIT ?
            """
            async with db.execute(query, (f"%{team_name}%", f"%{team_name}%", limit)) as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    return f"No recent matches found for {team_name}."
                results = [dict(row) for row in rows]
                return json.dumps(results, default=str)
    except Exception as e:
        return f"Error: {e}"

@tool
async def get_referee_profile(referee_name: str) -> str:
    """Get the statistical profile (cards, fouls, home advantage) for a specific referee."""
    path = _get_db_path()
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            query = """
            SELECT name, total_matches, avg_yellow_cards, avg_red_cards, avg_fouls, home_win_pct, home_advantage_factor
            FROM referee_profiles
            WHERE name LIKE ?
            """
            async with db.execute(query, (f"%{referee_name}%",)) as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    return f"No profile found for referee matching {referee_name}."
                results = [dict(row) for row in rows]
                return json.dumps(results, default=str)
    except Exception as e:
        return f"Error: {e}"

TOOLS = [get_team_roster, get_recent_matches, get_referee_profile]

# ---------------------------------------------------------------------------
# System prompt — the key to avoiding hallucination
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the FC Universitatea Cluj match‐analysis assistant — a highly formal, \
serious, and analytical tactical AI built exclusively for the coaching staff.

RULES — follow these without exception:
1. You have access to tools to query the SQLite database for data integrated in our code (team rosters, matches, referees). You also have access to the pre-generated <dossier> block below. Use ONLY these tools or the dossier to answer the user's questions.
2. If the user asks something that cannot be answered from the tools or dossier, \
say exactly: "I don't have that information."
3. NEVER invent statistics, player names, scores, dates, or any other facts.
4. YOU ARE STRICTLY FORBIDDEN from using any external knowledge, internet searches, or your pre-trained data to answer questions about the teams, players, or matches.
5. Keep answers extremely professional, formal, and objective — suitable for a \
serious coaching staff. DO NOT use emojis.
6. When citing numbers, use the exact values from the tools or dossier.
7. Answer in the same language the user asks in.
8. If the user asks short or contextless questions like "Formation?", "Weaknesses?", "Key players?", or "Recent form?", ALWAYS assume they are asking about the opponent team detailed in the <dossier>.

CHAIN OF THOUGHT REASONING:
Before generating your formal response, you MUST output a <thought> block where you plan your answer.
Inside the <thought> block:
- Briefly state what data you need.
- Note any data you retrieved from the dossier or tools.
- Outline the structure of your response.
Your final answer must begin immediately after the closing </thought> tag.

FORMATTING RULES:
- Use **bold** for player names, key stats, and important tactical terms.
- Use bullet points (•) when listing multiple items — never numbered lists.
- DO NOT use markdown headers (like #, ##, ###). Instead, use ALL CAPS bold text for headings (e.g., **LAST 5 MATCHES**).
- DO NOT output any image URLs, photo links, or markdown images (![image]).
- Keep each bullet to 1–2 lines max. Coaching staff skim — be punchy.
- ABSOLUTELY NO EMOJIS in your response. Maintain a strictly formal tone.

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
        llm_with_tools = llm.bind_tools(TOOLS)

        dossier_json = json.dumps(req.dossier, ensure_ascii=False, default=str)
        system = SYSTEM_PROMPT.format(dossier_json=dossier_json)

        # Build message list: system + conversation history + new question
        messages: list[Any] = [SystemMessage(content=system)]
        for msg in req.history[-10:]:  # keep last 10 messages for context
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=req.question))

        # Loop for tool execution
        response = None
        for _ in range(5):
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            
            if not response.tool_calls:
                break
                
            # Execute tools
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                if tool_name == "get_team_roster":
                    tool_result = await get_team_roster.ainvoke(tool_args)
                elif tool_name == "get_recent_matches":
                    tool_result = await get_recent_matches.ainvoke(tool_args)
                elif tool_name == "get_referee_profile":
                    tool_result = await get_referee_profile.ainvoke(tool_args)
                else:
                    tool_result = f"Unknown tool: {tool_name}"
                    
                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                ))

        import re
        answer = response.content if response and hasattr(response, "content") else str(response)
        
        # Remove the <thought> block from the final answer
        answer = re.sub(r'<thought>.*?</thought>', '', answer, flags=re.DOTALL).strip()

        logger.info("Chat answered question=%r answer_len=%d", req.question[:80], len(answer))

        return ChatResponse(answer=answer)

    except Exception as exc:
        logger.exception("Chat endpoint failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
