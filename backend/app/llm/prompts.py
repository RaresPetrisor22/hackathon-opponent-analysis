from __future__ import annotations

# All LLM prompt strings live here as module-level constants.
# Do not inline prompt strings in orchestrator.py, routes, or analysis modules.

SYSTEM_SCOUTING_ANALYST = """
You are an experienced football tactical analyst producing pre-match scouting reports for
professional coaching staff. Your output is factual, precise, and terse. You do not use
marketing language, hedging, or filler phrases. You never fabricate statistics.
"""

FORM_PROMPT = """
Summarise the following recent-form data for {opponent_name} in 2-3 sentences.
Highlight the most significant trend (e.g. unbeaten run, defensive fragility, home/away split).

Data:
{form_json}
"""
# TODO: refine — specify output format, add examples, tune tone

IDENTITY_PROMPT = """
Given the following seasonal average statistics for {opponent_name}, write a single concise
paragraph describing their tactical identity: how they build up, press, and defend.
Avoid generic phrases like "well-organised" or "dynamic". Be specific to the numbers.

Data:
{identity_json}
"""
# TODO: refine

MATCHUP_PROMPT = """
Based on the archetype analysis below, explain in 2-3 sentences what tactical challenge
{opponent_name} poses for a team classified as "{fcu_archetype}". Focus on the most
exploitable patterns visible in the record data.

Archetype records:
{matchup_json}
"""
# TODO: refine

PLAYERS_PROMPT = """
Given the player stat cards below for {opponent_name}, identify the single most dangerous
attacking threat and the most exploitable defensive weak spot. Write one sentence each.
Do not repeat the raw numbers — synthesise them.

Player cards:
{players_json}
"""
# TODO: refine

GAMEPLAN_PROMPT = """
You are writing the final gameplan narrative for an Opponent Dossier.
FC Universitatea Cluj will face {opponent_name} on {match_date}.

Below is the structured analysis from all seven dossier sections in JSON format.
Write a tactical gameplan with:
1. A one-line headline (imperative, e.g. "Press high in the first 15 minutes to disrupt their build-up").
2. A 3-4 paragraph narrative covering: key threat to neutralise, recommended pressing/defensive structure,
   set-piece awareness, and substitution window to exploit.
3. A bulleted list of 4-6 specific coaching points for the whiteboard session.

Tone: direct, professional, no hedging. Written for a head coach, not a fan.

Dossier data:
{full_dossier_json}
"""
# TODO: refine — add few-shot examples, constrain paragraph length
