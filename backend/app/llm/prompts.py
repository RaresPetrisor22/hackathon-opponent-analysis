from __future__ import annotations

# All prompt templates live here as module-level ChatPromptTemplate constants.
# Do NOT inline prompt strings in orchestrator.py, routes, or analysis modules.
#
# Usage in a chain:
#   chain = FORM_PROMPT | llm.with_structured_output(SomeSchema)
#   result = await chain.ainvoke({"opponent_name": "...", "form_json": "..."})

from langchain_core.prompts import ChatPromptTemplate

_SYSTEM = (
    "You are an experienced football tactical analyst producing pre-match scouting "
    "reports for professional coaching staff. Your output is factual, precise, and "
    "terse. You do not use marketing language, hedging, or filler phrases. "
    "You never fabricate statistics."
)

# ---------------------------------------------------------------------------
# FORM_PROMPT
# input_variables: opponent_name (str), form_json (str — serialised FormSection)
# ---------------------------------------------------------------------------
FORM_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        (
            "human",
            # TODO: refine — specify output format, add few-shot examples, tune tone
            "Summarise the following recent-form data for {opponent_name} in 2-3 sentences.\n"
            "Highlight the most significant trend (e.g. unbeaten run, defensive fragility, "
            "home/away split).\n\nData:\n{form_json}",
        ),
    ]
)

# ---------------------------------------------------------------------------
# IDENTITY_PROMPT
# input_variables: opponent_name (str), identity_json (str — serialised IdentitySection)
# ---------------------------------------------------------------------------
IDENTITY_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        (
            "human",
            # TODO: refine — avoid generic phrases, enforce paragraph length
            "Given the following seasonal average statistics for {opponent_name}, write a "
            "single concise paragraph describing their tactical identity: how they build up, "
            "press, and defend. Avoid generic phrases like 'well-organised' or 'dynamic'. "
            "Be specific to the numbers.\n\nData:\n{identity_json}",
        ),
    ]
)

# ---------------------------------------------------------------------------
# MATCHUP_PROMPT
# input_variables: opponent_name (str), fcu_archetype (str), matchup_json (str)
# ---------------------------------------------------------------------------
MATCHUP_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        (
            "human",
            # TODO: refine — focus output on exploitable patterns, add archetype label context
            "Based on the archetype analysis below, explain in 2-3 sentences what tactical "
            "challenge {opponent_name} poses for a team classified as '{fcu_archetype}'. "
            "Focus on the most exploitable patterns visible in the record data.\n\n"
            "Archetype records:\n{matchup_json}",
        ),
    ]
)

# ---------------------------------------------------------------------------
# PLAYERS_PROMPT
# input_variables: opponent_name (str), players_json (str — serialised PlayerCardsSection)
# ---------------------------------------------------------------------------
PLAYERS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        (
            "human",
            # TODO: refine — one sentence per card, no raw number repetition
            "Given the player stat cards below for {opponent_name}, identify the single most "
            "dangerous attacking threat and the most exploitable defensive weak spot. "
            "Write one sentence each. Do not repeat the raw numbers — synthesise them.\n\n"
            "Player cards:\n{players_json}",
        ),
    ]
)

# ---------------------------------------------------------------------------
# GAMEPLAN_PROMPT
# input_variables: opponent_name (str), match_date (str), full_dossier_json (str)
# ---------------------------------------------------------------------------
GAMEPLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        (
            "human",
            # TODO: refine — add few-shot examples, constrain paragraph length,
            #       enforce key_actions as imperative verb phrases
            "FC Universitatea Cluj will face {opponent_name} on {match_date}.\n\n"
            "Below is the structured analysis from all dossier sections in JSON format.\n"
            "Write a tactical gameplan with:\n"
            "1. A one-line headline (imperative).\n"
            "2. A 3-4 paragraph narrative: key threat to neutralise, pressing/defensive "
            "structure, set-piece awareness, substitution window to exploit.\n"
            "3. A list of 4-6 specific coaching points for the whiteboard session.\n\n"
            "Tone: direct, professional, no hedging. Written for a head coach.\n\n"
            "Dossier data:\n{full_dossier_json}",
        ),
    ]
)
