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
    "reports for the head coach of FC Universitatea Cluj. Your output is factual, "
    "precise, and terse — written for a professional dressing-room briefing, not a "
    "match preview article. Hard rules:\n"
    "  * Never invent statistics. Only reference numbers present in the supplied data.\n"
    "  * No marketing language ('dynamic', 'free-flowing', 'in-form'), no hedging "
    "    ('seems to', 'might be'), no filler ('it is worth noting that').\n"
    "  * Use specific numbers when they make the point (e.g. '56% possession over "
    "    the last 10' beats 'they keep the ball').\n"
    "  * No emoji. No exclamation marks. No questions."
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
            "Recent-form summary for {opponent_name}.\n\n"
            "Write exactly two sentences:\n"
            "  1. State the W/D/L record over the last 5 and the form_string verbatim.\n"
            "  2. Name the single most actionable trend — one of: an unbeaten or "
            "winless run, a defensive collapse, a goalscoring drought, or a clear "
            "home/away split. Cite the specific number that proves it.\n"
            "Do not list every fixture. Do not editorialise.\n\n"
            "Data:\n{form_json}",
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
            "Tactical identity paragraph for {opponent_name}.\n\n"
            "Write one paragraph of 3-4 sentences covering, in order:\n"
            "  1. Build-up and possession profile — anchor in avg_possession and "
            "avg_pass_accuracy.\n"
            "  2. Attacking output — anchor in avg_shots and avg_shots_on_target "
            "(and the on-target ratio if it is unusual).\n"
            "  3. Defensive / pressing posture — anchor in pressing_intensity and "
            "avg_fouls; mention preferred_formation only if it shapes the answer.\n"
            "Banned phrases: 'well-organised', 'dynamic', 'solid', 'compact unit', "
            "'high-quality side'. Replace any urge to use them with the concrete "
            "stat that drives the observation.\n\n"
            "Data:\n{identity_json}",
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
            "Archetype matchup readout. {opponent_name} is being played by FC "
            "Universitatea Cluj, who are classified as the '{fcu_archetype}' "
            "archetype.\n\n"
            "Write 2-3 sentences answering only this question: against opponents "
            "of {opponent_name}'s archetype, where does the '{fcu_archetype}' "
            "profile historically win or lose? Anchor every claim in the W/D/L "
            "and goals_for / goals_against numbers from the supplied records.\n"
            "Do not restate the archetype description. Do not give generic advice. "
            "Pick the one matchup pattern most worth exploiting and name it.\n\n"
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
            "From the {opponent_name} player cards below, produce exactly two lines:\n"
            "  THREAT: one sentence naming the single most dangerous attacker and "
            "the specific way they hurt opponents (e.g. 'left-channel cut-ins' or "
            "'late runs into the box'). Synthesise — do not recite the goals/assists "
            "tally.\n"
            "  WEAKNESS: one sentence naming the single most exploitable defender "
            "and the recurring failure mode (e.g. 'over-commits in 1v1 duels', "
            "'foul-prone under pressure'). Again, synthesise — no raw numbers.\n\n"
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
            "FC Universitatea Cluj face {opponent_name} on {match_date}. The full "
            "structured dossier is below. Produce a tactical gameplan for the "
            "head coach.\n\n"
            "Output requirements:\n\n"
            "1. headline — one imperative sentence, max 12 words. It must name "
            "the single decisive theme of the match. Examples of acceptable form:\n"
            "     - 'Suffocate the double pivot, force them wide'\n"
            "     - 'Win the second ball, attack the right-back's channel'\n"
            "   Examples of unacceptable form:\n"
            "     - 'A big match awaits us in Cluj' (not imperative, no theme)\n"
            "     - 'We need to be ready' (vague, no tactical content)\n\n"
            "2. body — 3 paragraphs, each 3-5 sentences. No more, no fewer. "
            "Order strictly:\n"
            "   Paragraph 1: the chief threat (player or pattern) and the "
            "concrete way to neutralise it. Reference matchup-archetype evidence "
            "or game-state tendencies where relevant.\n"
            "   Paragraph 2: our pressing and defensive shape against their "
            "build-up. Anchor in their identity numbers (possession, pass %, "
            "preferred formation).\n"
            "   Paragraph 3: in-game levers — set-piece risk, the score-state "
            "in which they are weakest, and the substitution window most worth "
            "exploiting. End the paragraph with the referee profile only if it "
            "changes our duel or set-piece approach.\n\n"
            "3. key_actions — 4 to 6 bullets. Each MUST:\n"
            "   * begin with an imperative verb (Press, Force, Cover, Attack, "
            "Double up, Deny, Track, Compress, Recycle...)\n"
            "   * be a single line, no sub-clauses\n"
            "   * be specific enough that a player or unit can execute it\n"
            "   Acceptable: 'Force their right-back inside onto his weaker foot.'\n"
            "   Acceptable: 'Track the no.10's late runs from midfield to box.'\n"
            "   Unacceptable: 'Be focused and aggressive.' (not specific)\n"
            "   Unacceptable: 'Their striker is dangerous.' (not imperative)\n\n"
            "Hard constraints: no preamble, no closing summary, no quoting of "
            "raw JSON, no inventing players or stats not present in the data.\n\n"
            "Dossier data:\n{full_dossier_json}",
        ),
    ]
)
