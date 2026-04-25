from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.dossier import (
    ArchetypeRecord,
    DossierResponse,
    FormSection,
    GameplanNarrative,
    GameStateRecord,
    GameStateSection,
    IdentitySection,
    MatchFormEntry,
    MatchupSection,
    PlayerCard,
    PlayerCardsSection,
    RefereeSection,
    TacticalIdentityStats,
)


def build_mock_dossier(team_id: int, team_name: str = "CFR Cluj") -> DossierResponse:
    form = FormSection(
        last_5=[
            MatchFormEntry(date="2025-04-12", opponent="FCSB", home_away="H", goals_for=2, goals_against=1, result="W"),
            MatchFormEntry(date="2025-04-05", opponent="Rapid", home_away="A", goals_for=0, goals_against=0, result="D"),
            MatchFormEntry(date="2025-03-29", opponent="Petrolul", home_away="H", goals_for=3, goals_against=1, result="W"),
            MatchFormEntry(date="2025-03-22", opponent="Dinamo", home_away="A", goals_for=1, goals_against=2, result="L"),
            MatchFormEntry(date="2025-03-15", opponent="Sepsi", home_away="H", goals_for=2, goals_against=0, result="W"),
        ],
        last_10=[
            MatchFormEntry(date="2025-04-12", opponent="FCSB", home_away="H", goals_for=2, goals_against=1, result="W"),
            MatchFormEntry(date="2025-04-05", opponent="Rapid", home_away="A", goals_for=0, goals_against=0, result="D"),
            MatchFormEntry(date="2025-03-29", opponent="Petrolul", home_away="H", goals_for=3, goals_against=1, result="W"),
            MatchFormEntry(date="2025-03-22", opponent="Dinamo", home_away="A", goals_for=1, goals_against=2, result="L"),
            MatchFormEntry(date="2025-03-15", opponent="Sepsi", home_away="H", goals_for=2, goals_against=0, result="W"),
            MatchFormEntry(date="2025-03-08", opponent="U Craiova", home_away="A", goals_for=1, goals_against=1, result="D"),
            MatchFormEntry(date="2025-03-01", opponent="Hermannstadt", home_away="H", goals_for=2, goals_against=0, result="W"),
            MatchFormEntry(date="2025-02-22", opponent="Otelul", home_away="A", goals_for=0, goals_against=1, result="L"),
            MatchFormEntry(date="2025-02-15", opponent="Poli Iasi", home_away="H", goals_for=3, goals_against=0, result="W"),
            MatchFormEntry(date="2025-02-08", opponent="Farul", home_away="A", goals_for=1, goals_against=2, result="L"),
        ],
        wins_last5=3,
        draws_last5=1,
        losses_last5=1,
        goals_scored_avg=1.8,
        goals_conceded_avg=0.8,
        form_string="WDWLW",
    )

    identity = IdentitySection(
        stats=TacticalIdentityStats(
            avg_possession=54.2,
            avg_shots=13.4,
            avg_shots_on_target=4.9,
            avg_pass_accuracy=82.1,
            avg_fouls=12.3,
            avg_yellow_cards=2.1,
            avg_corners=5.8,
            preferred_formation="4-3-3",
        ),
        pressing_intensity="medium",
        play_style="Possession-based build-up",
        notes="Comfortable in possession, patient in the final third. Exploits wide channels through fullback overlaps. Defends in a compact 4-4-2 mid-block out of possession.",
    )

    matchups = MatchupSection(
        archetypes=[
            ArchetypeRecord(
                archetype_id=0,
                archetype_name="High-Press Possession",
                archetype_description="Teams that dominate the ball and press aggressively high up the pitch.",
                matches_played=6,
                wins=2,
                draws=1,
                losses=3,
                goals_for=1.33,
                goals_against=1.83,
                xg_diff=-0.42,
            ),
            ArchetypeRecord(
                archetype_id=1,
                archetype_name="Low-Block Counter",
                archetype_description="Teams that sit deep and transition quickly through direct balls.",
                matches_played=8,
                wins=5,
                draws=2,
                losses=1,
                goals_for=2.12,
                goals_against=0.75,
                xg_diff=0.68,
            ),
            ArchetypeRecord(
                archetype_id=2,
                archetype_name="Direct Physical",
                archetype_description="High tempo, direct passing, aerial dominance and set-piece threat.",
                matches_played=5,
                wins=3,
                draws=1,
                losses=1,
                goals_for=1.80,
                goals_against=1.20,
                xg_diff=0.15,
            ),
            ArchetypeRecord(
                archetype_id=3,
                archetype_name="Patient Build-Up",
                archetype_description="Methodical possession play, short passes, slow tempo build from the back.",
                matches_played=7,
                wins=4,
                draws=2,
                losses=1,
                goals_for=1.71,
                goals_against=0.86,
                xg_diff=0.31,
            ),
            ArchetypeRecord(
                archetype_id=4,
                archetype_name="Balanced Mid-Block",
                archetype_description="Compact defensive shape, controlled transitions, medium defensive line.",
                matches_played=4,
                wins=2,
                draws=1,
                losses=1,
                goals_for=1.50,
                goals_against=1.25,
                xg_diff=-0.05,
            ),
        ],
        fcu_archetype_id=1,
        fcu_archetype_name="Low-Block Counter",
        prediction_summary=(
            f"{team_name} struggles against teams that sit deep and counter — exactly how FC U Cluj typically operates. "
            "Expect them to dominate possession but find few clear chances against a disciplined defensive shape."
        ),
        best_archetype_vs_opponent="Low-Block Counter",
    )

    players = PlayerCardsSection(
        key_threats=[
            PlayerCard(
                player_id=101,
                name="Billel Omrani",
                position="Attacker",
                jersey_number=9,
                photo_url=None,
                key_stats={"goals": 11.0, "assists": 4.0, "shots_per_game": 3.2, "dribbles_won": 1.8},
                threat_level="high",
                notes="Clinical finisher in and around the box. Dangerous on the turn. Provide physical cover at centre-back.",
            ),
            PlayerCard(
                player_id=102,
                name="Ciprian Deac",
                position="Midfielder",
                jersey_number=10,
                photo_url=None,
                key_stats={"goals": 5.0, "assists": 9.0, "key_passes": 2.7, "pass_accuracy": 87.0},
                threat_level="high",
                notes="Creative hub. Delivers set-pieces and through-balls. Deny him space between the lines — press his reception.",
            ),
            PlayerCard(
                player_id=103,
                name="Mihai Bordeianu",
                position="Midfielder",
                jersey_number=8,
                photo_url=None,
                key_stats={"goals": 3.0, "assists": 2.0, "tackles": 3.1, "interceptions": 2.4},
                threat_level="medium",
                notes="Box-to-box engine. Covers ground well. Watch his late runs into the box from deep.",
            ),
        ],
        defensive_vulnerabilities=[
            PlayerCard(
                player_id=201,
                name="Andrei Burca",
                position="Defender",
                jersey_number=5,
                photo_url=None,
                key_stats={"fouls": 2.1, "yellow_cards": 0.3, "duels_won_pct": 58.0, "aerial_won_pct": 61.0},
                threat_level="medium",
                notes="Tends to step out aggressively — space opens behind him on quick transitions. Target with runs in behind.",
            ),
            PlayerCard(
                player_id=202,
                name="Camora",
                position="Defender",
                jersey_number=3,
                photo_url=None,
                key_stats={"fouls": 1.8, "yellow_cards": 0.4, "duels_won_pct": 52.0, "crosses_blocked": 0.9},
                threat_level="low",
                notes="Left back who pushes high. Can be exposed on counter-attacks into the channel behind him.",
            ),
        ],
    )

    game_state = GameStateSection(
        records=[
            GameStateRecord(
                state="winning",
                matches=18,
                avg_goals_for=0.61,
                avg_goals_against=0.22,
                defensive_change="Drops into a deep 4-4-2 block, reduces pressing intensity.",
                offensive_change="Prioritises ball retention over chance creation.",
            ),
            GameStateRecord(
                state="drawing",
                matches=9,
                avg_goals_for=1.22,
                avg_goals_against=0.89,
                defensive_change="Maintains shape, waits for opponent mistakes.",
                offensive_change="Increases tempo, introduces a more direct second striker.",
            ),
            GameStateRecord(
                state="losing",
                matches=7,
                avg_goals_for=1.57,
                avg_goals_against=1.71,
                defensive_change="Abandons compact shape, becomes stretched and vulnerable.",
                offensive_change="Goes direct — long balls to the striker, crosses from wide areas.",
            ),
        ],
        tendency_when_losing="Shifts to long-ball direct play; defensive shape breaks down — exploitable on the counter.",
        tendency_when_winning="Extreme low-block; virtually no offensive output — game management priority.",
    )

    referee = RefereeSection(
        referee_name="Istvan Kovacs",
        total_matches=24,
        avg_yellow_cards=3.8,
        avg_red_cards=0.21,
        avg_fouls_called=22.4,
        home_advantage_factor=0.54,
        notes="Generally lenient on physical duels early in matches. Card rate rises significantly after the 60th minute. Consistent with offside calls.",
    )

    gameplan = GameplanNarrative(
        headline=f"Exploit the channels — {team_name} are vulnerable on the counter when chasing the game.",
        body=(
            f"{team_name} are a well-organised side in possession but show clear structural weaknesses when pressed into a losing position. "
            "Their left channel is the primary area of vulnerability — Camora pushes high and leaves space in behind that fast wide forwards can exploit.\n\n"
            "FC U Cluj's low-block counter archetype is historically the most effective style against this opponent. "
            "Sit compact in a 4-4-2 mid-block, absorb their possession-based build-up, and release quickly through the channels on turnovers.\n\n"
            "Key danger areas: Omrani's movement in the box and Deac's delivery from set-pieces. "
            "Deny Deac time on the ball in the half-space — assign a dedicated shadow runner to track his movement."
        ),
        key_actions=[
            "Set up in a compact 4-4-2 mid-block — hold the shape until the ball is won.",
            "Trigger the press only when the ball goes to their centre-backs — not in midfield.",
            "Target Camora's channel with our right winger on transitions — this is the primary counter-attack route.",
            "Assign man-marking on Deac at all set-pieces — he is their primary delivery threat.",
            "When leading: drop to a deep 4-5-1, protect the lead — do not push for a second goal unnecessarily.",
        ],
    )

    return DossierResponse(
        opponent_id=team_id,
        opponent_name=team_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        form=form,
        identity=identity,
        matchups=matchups,
        players=players,
        game_state=game_state,
        referee=referee,
        gameplan=gameplan,
    )
